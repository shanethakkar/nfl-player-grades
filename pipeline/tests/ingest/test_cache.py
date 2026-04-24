"""Unit tests for the parquet cache layer.

We monkeypatch ``_get_sources`` so we never actually call nflreadpy.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from nfl_grades.ingest import _cache
from nfl_grades.ingest._cache import (
    CacheEntry,
    SourceSpec,
    cache_or_fetch,
    cache_path,
    manifest_path,
    read_manifest,
)


@pytest.fixture
def tmp_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the cache root to tmp_path/raw and return that root."""
    raw_root = tmp_path / "raw"
    monkeypatch.setattr(_cache, "_raw_root", lambda: raw_root)
    return raw_root


@pytest.fixture
def fake_sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[int]]:
    """Replace the registry with a fake season-keyed source.

    Returns a call-count dict so tests can assert cache hits don't refetch.
    """
    calls: dict[str, list[int]] = {"season_keyed": [], "season_agnostic": []}

    def fake_season_fetch(season: int | None) -> pl.DataFrame:
        calls["season_keyed"].append(season or -1)
        return pl.DataFrame({"season": [season] * 3, "x": [1, 2, 3]})

    def fake_agnostic_fetch(_season: int | None) -> pl.DataFrame:
        calls["season_agnostic"].append(0)
        return pl.DataFrame({"id": ["a", "b", "c", "d"]})

    fake_registry = {
        "rosters": SourceSpec(season_keyed=True, fetch=fake_season_fetch),
        "players": SourceSpec(season_keyed=False, fetch=fake_agnostic_fetch),
    }
    monkeypatch.setattr(_cache, "_get_sources", lambda: fake_registry)
    return calls


class TestCacheOrFetch:
    def test_first_call_writes_parquet_and_manifest(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        df = cache_or_fetch("rosters", season=2024)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert cache_path("rosters", 2024).exists()
        assert manifest_path().exists()

        manifest = read_manifest()
        assert "rosters/2024" in manifest
        entry = manifest["rosters/2024"]
        assert entry.row_count == 3
        assert entry.bytes > 0
        assert entry.sha256  # non-empty
        assert fake_sources["season_keyed"] == [2024]

    def test_second_call_hits_cache(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        cache_or_fetch("rosters", season=2024)
        cache_or_fetch("rosters", season=2024)
        assert fake_sources["season_keyed"] == [2024]  # only one fetch

    def test_refresh_bypasses_cache(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        cache_or_fetch("rosters", season=2024)
        cache_or_fetch("rosters", season=2024, refresh=True)
        assert fake_sources["season_keyed"] == [2024, 2024]

    def test_season_agnostic_source(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        df = cache_or_fetch("players")
        assert len(df) == 4
        assert cache_path("players").name == "all.parquet"

    def test_season_required_for_keyed_source(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        with pytest.raises(ValueError, match="requires a season"):
            cache_or_fetch("rosters")

    def test_season_rejected_for_agnostic_source(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        with pytest.raises(ValueError, match="season-agnostic"):
            cache_or_fetch("players", season=2024)

    def test_unknown_source(
        self, tmp_cache: Path, fake_sources: dict[str, list[int]]
    ) -> None:
        with pytest.raises(ValueError, match="Unknown source"):
            cache_or_fetch("does_not_exist", season=2024)  # type: ignore[arg-type]


class TestManifest:
    def test_empty_when_missing(self, tmp_cache: Path) -> None:
        assert read_manifest() == {}

    def test_roundtrip(self, tmp_cache: Path, fake_sources: dict[str, list[int]]) -> None:
        cache_or_fetch("rosters", season=2024)
        cache_or_fetch("rosters", season=2025)
        cache_or_fetch("players")

        manifest = read_manifest()
        assert set(manifest.keys()) == {"rosters/2024", "rosters/2025", "players/all"}
        for entry in manifest.values():
            assert isinstance(entry, CacheEntry)
            assert entry.path.exists()
