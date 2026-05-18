"""Pixelated player headshot generator.

Pipeline:
    1. Resolve target players (from DB filter: position, season, qualified)
    2. Look up each player's nflverse headshot URL (cached players parquet)
    3. Call Replicate `fofr/face-to-many` with the Variant G recipe
       (instant_id_strength=0.85, control_depth_strength=0.6, weighted
       skin/hair anchors, eye-artifact negatives) and a prompt that
       interpolates the player's position + team color descriptor.
    4. Pipe result through `851-labs/background-remover` for transparency.
    5. Square-crop to 736×736 (the model's natural output dimension after
       crop) and save to web/public/headshots/{player_id}.png.
    6. Append metadata to web/public/headshots/manifest.json for export.

Idempotent: skips players whose target PNG already exists unless
`force=True`. Throttled: 12s between API calls (Replicate's free-tier
rate limit while account credit is below $5).

See `/headshot-preview` (during development) for the variant ladder
(A through G) that landed on this recipe.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.config import settings
from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)

# --- Constants --------------------------------------------------------------

FACE_TO_MANY = (
    "fofr/face-to-many:"
    "35cea9c3164d9fb7fbd48b51503eabdb39c9d04fdaef9a68f368bed8087ec5f9"
)
BG_REMOVER = (
    "851-labs/background-remover:"
    "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
)

# Replicate rate-limits new accounts (< $5 credit) to 6 predictions/min.
# 12s gives us 5 req/min with margin; safer than tight 10s.
THROTTLE_SECONDS = 12

# Output: web/public/headshots/ is sibling to the pipeline/.
# settings.repo_root resolves correctly even when run from any cwd.
HEADSHOTS_DIR = Path(__file__).resolve().parents[4] / "web" / "public" / "headshots"
MANIFEST_PATH = HEADSHOTS_DIR / "manifest.json"


# --- Prompt templating -----------------------------------------------------

# Natural-language team color descriptors. Hand-curated rather than derived
# from teams.primary_color hex codes because SDXL prompts work better with
# color names ("navy blue and red") than RGB triplets. Tuple = (jersey
# primary, accent/stripe descriptor).
TEAM_PROMPT_COLORS: dict[str, tuple[str, str]] = {
    "ARI": ("red and white", "white shoulder accents"),
    "ATL": ("red and black", "white shoulder accents"),
    "BAL": ("purple and black", "gold shoulder accents"),
    "BUF": ("navy blue and red", "white shoulder stripes"),
    "CAR": ("light blue and black", "white shoulder accents"),
    "CHI": ("navy blue and orange", "white shoulder accents"),
    "CIN": ("orange and black", "black tiger stripes"),
    "CLE": ("brown and orange", "white shoulder accents"),
    "DAL": ("navy blue and silver", "white shoulder stripes"),
    "DEN": ("navy blue and orange", "white shoulder accents"),
    "DET": ("light blue and silver", "white shoulder accents"),
    "GB":  ("dark green and gold", "white shoulder accents"),
    "HOU": ("navy blue and red", "white shoulder accents"),
    "IND": ("royal blue and white", "white shoulder accents"),
    "JAX": ("teal and black", "gold shoulder accents"),
    "KC":  ("red and gold", "white shoulder stripes"),
    "LA":  ("royal blue and yellow", "white shoulder accents"),
    "LAC": ("powder blue and yellow", "white shoulder accents"),
    "LV":  ("black and silver", "silver shoulder accents"),
    "MIA": ("aqua teal and orange", "white shoulder accents"),
    "MIN": ("purple and gold", "white shoulder accents"),
    "NE":  ("navy blue and red", "white shoulder stripes"),
    "NO":  ("black and gold", "gold shoulder accents"),
    "NYG": ("royal blue and red", "white shoulder accents"),
    "NYJ": ("dark green and white", "white shoulder accents"),
    "PHI": ("dark green and silver", "white shoulder accents"),
    "PIT": ("black and gold", "yellow shoulder accents"),
    "SEA": ("navy blue and bright green", "white shoulder accents"),
    "SF":  ("red and gold", "white shoulder stripes"),
    "TB":  ("red and pewter", "orange shoulder accents"),
    "TEN": ("navy blue and light blue", "white shoulder accents"),
    "WAS": ("burgundy and gold", "white shoulder accents"),
}

POSITION_NAMES: dict[str, str] = {
    "QB":   "quarterback",
    "RB":   "running back",
    "WR":   "wide receiver",
    "TE":   "tight end",
    "OL":   "offensive lineman",
    "CB":   "cornerback",
    "S":    "safety",
    "EDGE": "edge rusher",
    "iDL":  "interior defensive lineman",
    "LB":   "linebacker",
    "K":    "kicker",
    "P":    "punter",
}

PROMPT_VERSION = "G"

NEGATIVE_PROMPT = (
    "collared shirt, dress shirt, photograph, photorealistic, blurry, "
    "deformed teeth, weird smile, thin neck, extra fingers, low quality, "
    "dyed hair, colored hair, tinted skin, painted face, face paint, "
    "body paint, color bleed, color tint, color spill, gradient face"
)


def _build_prompt(position_label: str, team_abbr: str) -> str:
    position_name = POSITION_NAMES.get(position_label, position_label.lower())
    colors, accent = TEAM_PROMPT_COLORS.get(
        team_abbr, ("team colors", "team-color shoulder accents")
    )
    return (
        f"16-bit pixel art portrait of an NFL {position_name}, head and "
        "shoulders, retro video game character art, (natural skin tone:1.3), "
        f"(natural hair color:1.3). Football jersey colored {colors} with "
        f"{accent}. Plain background."
    )


# --- Player resolution -----------------------------------------------------


@dataclass(frozen=True)
class HeadshotTarget:
    player_id: int
    full_name: str
    position: str
    team_abbr: str | None
    gsis_id: str
    source_url: str


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _load_targets(
    conn: Connection,
    *,
    position: str | None,
    season: int,
    qualified_only: bool,
    player_id: int | None,
) -> list[HeadshotTarget]:
    """Resolve which players to generate, joined with their nflverse
    headshot URL from the cached players parquet. Players without a URL
    are dropped (logged at WARNING)."""
    where = ["sg.season = :season"]
    params: dict[str, object] = {"season": season}
    if position is not None:
        where.append("sg.position = :position")
        params["position"] = position
    if qualified_only:
        where.append("sg.qualified = TRUE")
    if player_id is not None:
        where.append("p.player_id = :player_id")
        params["player_id"] = player_id

    sql = f"""
        SELECT DISTINCT
            p.player_id, p.full_name, p.gsis_id,
            sg.position,
            t.abbr AS team_abbr
        FROM season_grades sg
        JOIN players p ON p.player_id = sg.player_id
        LEFT JOIN player_seasons ps
          ON ps.player_id = p.player_id AND ps.season = sg.season
        LEFT JOIN teams t ON t.team_id = ps.team_id
        WHERE {" AND ".join(where)}
        ORDER BY p.full_name
    """
    rows = conn.execute(text(sql), params).mappings().all()
    if not rows:
        return []

    # Map gsis_id → headshot URL via the cached players parquet (single read,
    # not per-player). This avoids a network call inside the per-player loop.
    players_df = cache_or_fetch("players")
    if hasattr(players_df, "to_pandas"):
        players_df = players_df.to_pandas()
    url_by_gsis: dict[str, str] = {}
    for _, pr in players_df[["gsis_id", "headshot"]].dropna().iterrows():
        url_by_gsis[str(pr["gsis_id"])] = str(pr["headshot"])

    targets: list[HeadshotTarget] = []
    missing_url = 0
    for r in rows:
        gsis = r["gsis_id"]
        if not gsis:
            missing_url += 1
            continue
        url = url_by_gsis.get(str(gsis))
        if not url:
            logger.warning("no nflverse headshot for %s (gsis=%s)", r["full_name"], gsis)
            missing_url += 1
            continue
        targets.append(
            HeadshotTarget(
                player_id=int(r["player_id"]),
                full_name=str(r["full_name"]),
                position=str(r["position"]),
                team_abbr=r["team_abbr"],
                gsis_id=str(gsis),
                source_url=url,
            )
        )
    if missing_url:
        logger.warning("dropped %d players with no resolvable headshot URL", missing_url)
    return targets


# --- Image processing ------------------------------------------------------


def _square_crop(img: Image.Image, top_bias: float = 0.10) -> Image.Image:
    """Crop to a square with a slight upward bias (face occupies the
    upper-third of NFL headshots; pure-center crop wastes pixels on chest)."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = max(0, int((h - side) * (0.5 - top_bias)))
    return img.crop((left, top, left + side, top + side))


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _to_url(replicate_output: object) -> str:
    """Replicate returns either a FileOutput object, a list of them, or
    a plain URL string depending on model + version. Normalize."""
    if isinstance(replicate_output, list):
        return str(replicate_output[0])
    return str(replicate_output)


# --- Replicate calls -------------------------------------------------------


DEFAULT_SEED = 99


def _stylize_and_remove_bg(
    replicate_client,
    source_url: str,
    position: str,
    team_abbr: str | None,
    seed: int = DEFAULT_SEED,
) -> Image.Image:
    """One full Variant G generation: face-to-many → bg removal. Returns
    a square-cropped PIL Image at ~736x736 RGBA. Throttles before each
    API call to stay under Replicate's free-tier rate limit.

    `seed` is exposed because the model is stochastic — when a player's
    initial generation has artifacts (bad bg removal, weird eyes), the
    standard fix is to re-roll with a different seed before changing
    the recipe.
    """
    team_for_prompt = team_abbr or "NE"  # arbitrary fallback if team unknown
    prompt = _build_prompt(position, team_for_prompt)

    logger.info("  face-to-many...")
    stylized = replicate_client.run(
        FACE_TO_MANY,
        input={
            "image": source_url,
            "style": "Pixels",
            "prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "prompt_strength": 4.5,
            "denoising_strength": 0.65,
            "instant_id_strength": 0.85,
            "control_depth_strength": 0.6,
            "seed": seed,
        },
    )
    stylized_url = _to_url(stylized)

    logger.info("  throttling %ds...", THROTTLE_SECONDS)
    time.sleep(THROTTLE_SECONDS)

    logger.info("  background-remover...")
    bg_out = replicate_client.run(BG_REMOVER, input={"image": stylized_url})
    bg_url = _to_url(bg_out)
    img = Image.open(BytesIO(_download(bg_url))).convert("RGBA")
    return _square_crop(img)


# --- Manifest --------------------------------------------------------------


def _load_manifest() -> dict[str, dict[str, object]]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _save_manifest(manifest: dict[str, dict[str, object]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def _update_manifest_entry(
    manifest: dict[str, dict[str, object]], target: HeadshotTarget
) -> None:
    manifest[str(target.player_id)] = {
        "full_name": target.full_name,
        "slug": _slugify(target.full_name),
        "position": target.position,
        "team_abbr": target.team_abbr,
        "gsis_id": target.gsis_id,
        "source_headshot_url": target.source_url,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
    }


# --- Public entrypoint -----------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    targeted: int
    generated: int
    skipped_existing: int
    skipped_no_url: int
    failed: int


def run(
    *,
    position: str | None = None,
    season: int = 2025,
    qualified_only: bool = True,
    player_id: int | None = None,
    force: bool = False,
    seed: int = DEFAULT_SEED,
) -> RunResult:
    """Generate pixel headshots for the targeted players. See module docstring."""
    import replicate  # imported here so the module is cheap to load even
                      # when only used for `--help`

    if not settings.replicate_api_token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN not set in .env — add it before running."
        )
    replicate_client = replicate.Client(api_token=settings.replicate_api_token)

    HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()

    engine = get_engine()
    with pipeline_run(
        "ingest:pixel_headshots",
        season=season,
    ) as handle:
        with engine.connect() as conn:
            targets = _load_targets(
                conn,
                position=position,
                season=season,
                qualified_only=qualified_only,
                player_id=player_id,
            )

        if not targets:
            logger.warning("no targets matched filters")
            return RunResult(0, 0, 0, 0, 0)

        logger.info("targeted=%d players", len(targets))

        generated = 0
        skipped_existing = 0
        failed = 0
        first_call = True
        for i, t in enumerate(targets, 1):
            out_path = HEADSHOTS_DIR / f"{t.player_id}.png"
            if out_path.exists() and not force:
                logger.info("[%d/%d] %s — skip (exists)", i, len(targets), t.full_name)
                skipped_existing += 1
                # Make sure manifest still has the entry
                if str(t.player_id) not in manifest:
                    _update_manifest_entry(manifest, t)
                continue

            logger.info("[%d/%d] %s (%s, %s)", i, len(targets), t.full_name, t.position, t.team_abbr)

            # Throttle before the first call too (in case a previous run
            # used up the burst window).
            if not first_call:
                logger.info("  throttling %ds before next player...", THROTTLE_SECONDS)
                time.sleep(THROTTLE_SECONDS)
            first_call = False

            try:
                img = _stylize_and_remove_bg(replicate_client, t.source_url, t.position, t.team_abbr, seed=seed)
                img.save(out_path)
                _update_manifest_entry(manifest, t)
                _save_manifest(manifest)
                generated += 1
                logger.info("  saved %s", out_path.name)
            except Exception as exc:  # noqa: BLE001 — log + continue
                logger.exception("  FAILED for %s: %s", t.full_name, exc)
                failed += 1

        result = RunResult(
            targeted=len(targets),
            generated=generated,
            skipped_existing=skipped_existing,
            skipped_no_url=0,  # counted inside _load_targets warnings
            failed=failed,
        )
        handle.rows_written = generated
        handle.note(
            f"generated={generated} skipped_existing={skipped_existing} "
            f"failed={failed} prompt_version={PROMPT_VERSION}"
        )

    return result


__all__ = ["RunResult", "run", "PROMPT_VERSION"]
