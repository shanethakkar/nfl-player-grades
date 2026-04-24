"""Parquet cache + manifest for raw nflreadpy pulls.

This is the **only** module in the codebase allowed to ``import nflreadpy``.
Every other ingest module gets DataFrames from ``cache_or_fetch(source, season)``
without knowing or caring whether the data came from disk or the network.

See ADR 0009 (parquet caching strategy) and ADR 0010 (nflreadpy choice).

## Layout on disk

    PIPELINE_CACHE_DIR/
        raw/
            manifest.json
            players/
                all.parquet            # season-agnostic master
            rosters/
                2024.parquet
                2025.parquet
            pbp/
                2024.parquet
                ...

## Manifest format

    {
        "version": 1,
        "entries": {
            "rosters/2024": {
                "fetched_at":        "2026-04-23T19:45:00+00:00",
                "nflreadpy_version": "0.1.5",
                "row_count":         3216,
                "sha256":            "abc123...",
                "bytes":             482133
            },
            "players/all": { ... }
        }
    }

Atomic writes: write to ``manifest.json.tmp`` then ``os.replace`` to avoid
half-written manifests on Ctrl-C.

## NFLREADPY built-in cache

Disabled at import time (``NFLREADPY_CACHE=off``) so we control the only
caching layer. Two cache layers would be confusing and would make the
manifest unreliable about "when did we actually pull from the network."
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

# Disable nflreadpy's built-in cache *before* importing it. This must run
# before any other module imports nflreadpy.
os.environ.setdefault("NFLREADPY_CACHE", "off")
os.environ.setdefault("NFLREADPY_VERBOSE", "False")

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

import pandas as pd

from nfl_grades.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SourceName = Literal[
    "players",  # season-agnostic master
    "rosters",  # end-of-season per-team rosters
    "rosters_weekly",  # weekly rosters (trade tracking)
    "pbp",  # play-by-play
    "depth_charts",  # depth charts
    "snap_counts",  # offensive/defensive/ST snaps
    "ngs_passing",
    "ngs_rushing",
    "ngs_receiving",
    "ftn",  # FTN charting
]


@dataclass(frozen=True)
class SourceSpec:
    """How to fetch one nflreadpy source.

    Attributes:
        season_keyed: True for sources fetched per season (most). False for
            season-agnostic sources (currently only ``players``).
        fetch: Callable that takes ``season: int | None`` and returns a
            polars DataFrame. Lives in this module because it's the only
            place allowed to import nflreadpy.
    """

    season_keyed: bool
    fetch: Callable[
        [int | None], object
    ]  # returns polars.DataFrame; typed loosely to avoid forcing a polars import in every consumer


_SOURCES_CACHE: dict[str, SourceSpec] | None = None


def _build_registry() -> dict[str, SourceSpec]:
    """Build the source -> SourceSpec registry.

    Imports ``nflreadpy`` lazily so ``import nfl_grades.ingest._cache`` is
    cheap when no fetching is happening (e.g. during unit tests for other
    modules).
    """
    import nflreadpy as nfl

    return {
        "players": SourceSpec(
            season_keyed=False,
            fetch=lambda _season: nfl.load_players(),
        ),
        "rosters": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_rosters(seasons=[s]),
        ),
        "rosters_weekly": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_rosters_weekly(seasons=[s]),
        ),
        "pbp": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_pbp(seasons=[s]),
        ),
        "depth_charts": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_depth_charts(seasons=[s]),
        ),
        "snap_counts": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_snap_counts(seasons=[s]),
        ),
        "ngs_passing": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_nextgen_stats(stat_type="passing", seasons=[s]),
        ),
        "ngs_rushing": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_nextgen_stats(stat_type="rushing", seasons=[s]),
        ),
        "ngs_receiving": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_nextgen_stats(stat_type="receiving", seasons=[s]),
        ),
        "ftn": SourceSpec(
            season_keyed=True,
            fetch=lambda s: nfl.load_ftn_charting(seasons=[s]),
        ),
    }


def _get_sources() -> dict[str, SourceSpec]:
    """Lazy accessor for the source registry."""
    global _SOURCES_CACHE
    if _SOURCES_CACHE is None:
        _SOURCES_CACHE = _build_registry()
    return _SOURCES_CACHE


# Backwards-compatible empty SOURCES (the public name from the skeleton).
SOURCES: Final[dict[str, SourceSpec]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheEntry:
    """One row in the manifest, also returned by ``cache_or_fetch`` for logging."""

    source: str
    season: int | None
    path: Path
    fetched_at: datetime
    nflreadpy_version: str
    row_count: int
    sha256: str
    bytes: int

    @property
    def manifest_key(self) -> str:
        """Stable key used in ``manifest.json`` ('rosters/2024' or 'players/all')."""
        return f"{self.source}/{self.season if self.season is not None else 'all'}"

    def to_manifest_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["path"] = str(self.path)
        d["fetched_at"] = self.fetched_at.isoformat()
        d.pop("source")
        d.pop("season")
        return d


def _raw_root() -> Path:
    return settings.pipeline_cache_dir / "raw"


def cache_path(source: SourceName, season: int | None = None) -> Path:
    """Return the absolute parquet path for ``(source, season)``.

    Useful for logging, manual inspection, and tests. Does NOT check whether
    the file exists.
    """
    name = f"{season}.parquet" if season is not None else "all.parquet"
    return _raw_root() / source / name


def manifest_path() -> Path:
    """Return the absolute path to the manifest JSON file."""
    return _raw_root() / "manifest.json"


def read_manifest() -> dict[str, CacheEntry]:
    """Load the manifest from disk, returning an empty dict if missing."""
    p = manifest_path()
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    entries: dict[str, CacheEntry] = {}
    for key, payload in raw.get("entries", {}).items():
        source, season_str = key.split("/", 1)
        season = None if season_str == "all" else int(season_str)
        entries[key] = CacheEntry(
            source=source,
            season=season,
            path=Path(payload["path"]),
            fetched_at=datetime.fromisoformat(payload["fetched_at"]),
            nflreadpy_version=payload["nflreadpy_version"],
            row_count=int(payload["row_count"]),
            sha256=payload["sha256"],
            bytes=int(payload["bytes"]),
        )
    return entries


def _write_manifest(entries: dict[str, CacheEntry]) -> None:
    """Atomic write: serialize to .tmp then os.replace."""
    payload = {
        "version": 1,
        "entries": {key: e.to_manifest_dict() for key, e in entries.items()},
    }
    p = manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _nflreadpy_version() -> str:
    try:
        from importlib.metadata import version

        return version("nflreadpy")
    except Exception:
        return "unknown"


def cache_or_fetch(
    source: SourceName,
    season: int | None = None,
    *,
    refresh: bool = False,
) -> pd.DataFrame:
    """Get a DataFrame for ``(source, season)``, using the parquet cache.

    See module docstring for full behavior.
    """
    sources = _get_sources()
    if source not in sources:
        raise ValueError(f"Unknown source {source!r}; known: {sorted(sources)}")
    spec = sources[source]
    if spec.season_keyed and season is None:
        raise ValueError(f"source {source!r} requires a season")
    if not spec.season_keyed and season is not None:
        raise ValueError(f"source {source!r} is season-agnostic; pass season=None")

    path = cache_path(source, season)

    if path.exists() and not refresh:
        logger.debug("cache hit: %s", path)
        return pd.read_parquet(path)

    logger.info("cache miss; fetching %s season=%s", source, season)
    polars_df = spec.fetch(season)
    df: pd.DataFrame = polars_df.to_pandas()  # type: ignore[union-attr]

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

    entry = CacheEntry(
        source=source,
        season=season,
        path=path,
        fetched_at=datetime.now(UTC),
        nflreadpy_version=_nflreadpy_version(),
        row_count=len(df),
        sha256=_sha256_file(path),
        bytes=path.stat().st_size,
    )
    entries = read_manifest()
    entries[entry.manifest_key] = entry
    _write_manifest(entries)
    logger.info("wrote %s (%d rows, %.1f KB)", path, entry.row_count, entry.bytes / 1024)
    return df


def stale_entries() -> list[CacheEntry]:
    """Return manifest entries fetched with a different ``nflreadpy`` version."""
    current = _nflreadpy_version()
    return [e for e in read_manifest().values() if e.nflreadpy_version != current]
