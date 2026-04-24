"""Ingest rosters and the player master into Postgres.

Pipeline:

    nflreadpy.load_players()    --(_cache)--> df_players_master  (24k rows, all-time)
    nflreadpy.load_rosters([s]) --(_cache)--> df_rosters         (~3k rows for one season)
                                                  |
                                                  v
                          UPSERT players          (gsis_id-keyed)
                                                  |
                                                  v
                          UPSERT player_seasons   ((player_id, season, team_id))

This module owns:
    - players              -- master, refreshed every run from load_players()
    - player_seasons       -- per-season skeleton (team, position_played).
                              Snap counts and games come from a separate
                              ingest module (snap_counts) that fills in
                              the remaining columns by player_id+season.

End-of-season grain is intentional in v1 — see
``docs/exploration/2026-04-23-rosters.md`` "Trade handling (deferred to v1.5)"
for why we don't split traded players across multiple ``player_seasons`` rows
yet. ``load_rosters`` shows each player exactly once per season (their
end-of-season team).

This module follows ADR 0007: it does I/O. The grading layer is pure; this
layer is the "ingest glue" that's allowed to read DataFrames and write SQL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch
from nfl_grades.ingest._positions import (
    CanonicalPosition,
    UnknownPositionError,
    canonical_position,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """Outcome of one ingest run, used to populate ``pipeline_runs`` and CLI logs."""

    season: int
    players_upserted: int       # rows touched in `players` (insert + update combined)
    player_seasons_upserted: int
    rows_skipped_no_gsis: int   # rosters rows dropped because gsis_id was null
    rows_skipped_unknown_pos: int  # dropped because canonical_position raised
    rows_skipped_unknown_team: int  # dropped because team abbr didn't resolve via team_aliases


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Ingest rosters + player master for one season.

    Idempotent. See module docstring for details.
    """
    if season < 2002:
        raise ValueError(f"season {season} predates our coverage (>=2002)")

    df_players = cache_or_fetch("players", season=None, refresh=refresh)
    df_rosters = cache_or_fetch("rosters", season=season, refresh=refresh)

    # Filter rosters to this season only (load_rosters is season-keyed but
    # the cache file may have additional rows in some upstream versions).
    df_rosters = df_rosters[df_rosters["season"] == season].copy()

    skipped_no_gsis = int(df_rosters["gsis_id"].isna().sum())
    df_rosters = df_rosters[df_rosters["gsis_id"].notna()].copy()

    engine = get_engine()
    with pipeline_run("ingest:rosters", season=season) as handle:
        with engine.begin() as conn:
            team_lookup = _team_abbr_to_id(conn)

            players_rows, skipped_unknown_pos_p = _transform_players(
                df_players, df_rosters, team_lookup
            )
            players_n = _upsert_players(conn, players_rows)

            gsis_to_player_id = _read_gsis_to_player_id(conn)

            ps_rows, skipped_unknown_pos_r, skipped_unknown_team = (
                _transform_player_seasons(
                    df_rosters, season, team_lookup, gsis_to_player_id
                )
            )
            ps_n = _upsert_player_seasons(conn, ps_rows, season)

        result = RunResult(
            season=season,
            players_upserted=players_n,
            player_seasons_upserted=ps_n,
            rows_skipped_no_gsis=skipped_no_gsis,
            rows_skipped_unknown_pos=skipped_unknown_pos_p + skipped_unknown_pos_r,
            rows_skipped_unknown_team=skipped_unknown_team,
        )
        handle.rows_written = ps_n
        handle.note(
            f"players_upserted={result.players_upserted} "
            f"player_seasons_upserted={result.player_seasons_upserted} "
            f"skipped_no_gsis={result.rows_skipped_no_gsis} "
            f"skipped_unknown_pos={result.rows_skipped_unknown_pos} "
            f"skipped_unknown_team={result.rows_skipped_unknown_team}"
        )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _team_abbr_to_id(conn: Connection) -> dict[str, int]:
    """Build alias -> team_id lookup from team_aliases (see ADR 0004)."""
    rows = conn.execute(text("SELECT alias, team_id FROM team_aliases")).all()
    if not rows:
        raise RuntimeError(
            "team_aliases is empty; run `nflgrades migrate --seeds` first."
        )
    return {alias: team_id for alias, team_id in rows}


def _read_gsis_to_player_id(conn: Connection) -> dict[str, int]:
    """Read the post-upsert (gsis_id -> player_id) lookup."""
    rows = conn.execute(
        text("SELECT gsis_id, player_id FROM players WHERE gsis_id IS NOT NULL")
    ).all()
    return {gsis_id: player_id for gsis_id, player_id in rows}


def _safe_canonical(group: object, pos: object) -> CanonicalPosition | None:
    """Wrap canonical_position so unknowns yield None (caller logs + counts)."""
    g = None if pd.isna(group) else str(group)
    p = None if pd.isna(pos) else str(pos)
    try:
        return canonical_position(g, p)
    except UnknownPositionError:
        return None


def _to_int_or_none(x: object) -> int | None:
    """Convert a numeric-or-NaN value to int or None."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(x: object) -> str | None:
    if x is None:
        return None
    if isinstance(x, float) and np.isnan(x):
        return None
    if isinstance(x, pd.Timestamp) and pd.isna(x):
        return None
    s = str(x).strip()
    if not s or s == "NaT" or s.lower() == "nan":
        return None
    return s


def _to_date_or_none(x: object) -> str | None:
    """Coerce to ISO date string or None. Handles pandas Timestamp + NaT."""
    if x is None:
        return None
    if isinstance(x, float) and np.isnan(x):
        return None
    if isinstance(x, pd.Timestamp):
        if pd.isna(x):
            return None
        return x.date().isoformat()
    s = str(x).strip()
    if not s or s == "NaT" or s.lower() == "nan":
        return None
    # Strip any time component just in case.
    return s.split("T")[0].split(" ")[0]


def _transform_players(
    df_players_master: pd.DataFrame,
    df_rosters: pd.DataFrame,
    team_abbr_to_id: dict[str, int],
) -> tuple[list[dict[str, object]], int]:
    """Reshape ``load_players()`` (filtered to current season's gsis_ids) into
    ``players`` table rows. Falls back to rosters fields for any gsis_id
    present in rosters but missing from the master.

    Returns a list of dicts (not a DataFrame) so we don't lose None vs NaN
    distinction during the round-trip — pandas promotes int columns with
    nulls to float64-with-NaN, and Postgres rejects NaN in INTEGER columns.

    Returns:
        (list of row dicts ready to upsert, count of rows skipped due to unknown position)
    """
    season_gsis = set(df_rosters["gsis_id"].dropna().astype(str))

    rich = df_players_master[df_players_master["gsis_id"].isin(season_gsis)].copy()

    have = set(rich["gsis_id"].astype(str))
    missing_gsis = season_gsis - have
    if missing_gsis:
        logger.info("%d gsis_ids in rosters missing from load_players", len(missing_gsis))
    fallback = df_rosters[df_rosters["gsis_id"].isin(missing_gsis)].copy()

    rows: list[dict[str, object]] = []
    skipped_unknown_pos = 0

    for _, r in rich.iterrows():
        pos = _safe_canonical(r.get("position_group"), r.get("position"))
        if pos is None:
            skipped_unknown_pos += 1
            continue
        team_abbr = _to_str_or_none(r.get("latest_team"))
        team_id = team_abbr_to_id.get(team_abbr) if team_abbr else None
        rows.append({
            "gsis_id": str(r["gsis_id"]),
            "pfr_id": _to_str_or_none(r.get("pfr_id")),
            "full_name": _to_str_or_none(r.get("display_name")) or "Unknown",
            "position": pos,
            "birth_date": _to_date_or_none(r.get("birth_date")),
            "height_inches": _to_int_or_none(r.get("height")),
            "weight_lbs": _to_int_or_none(r.get("weight")),
            "draft_year": _to_int_or_none(r.get("draft_year")),
            "draft_round": _to_int_or_none(r.get("draft_round")),
            "draft_pick": _to_int_or_none(r.get("draft_pick")),
            "current_team_id": team_id,
        })

    # Fallback rows use load_rosters schema — note column-name swap:
    # rosters.position == load_players.position_group;
    # rosters.depth_chart_position == load_players.position.
    for _, r in fallback.iterrows():
        pos = _safe_canonical(r.get("position"), r.get("depth_chart_position"))
        if pos is None:
            skipped_unknown_pos += 1
            continue
        team_abbr = _to_str_or_none(r.get("team"))
        team_id = team_abbr_to_id.get(team_abbr) if team_abbr else None
        rows.append({
            "gsis_id": str(r["gsis_id"]),
            "pfr_id": _to_str_or_none(r.get("pfr_id")),   # rosters has pfr_id too
            "full_name": _to_str_or_none(r.get("full_name")) or "Unknown",
            "position": pos,
            "birth_date": _to_date_or_none(r.get("birth_date")),
            "height_inches": _to_int_or_none(r.get("height")),
            "weight_lbs": _to_int_or_none(r.get("weight")),
            "draft_year": _to_int_or_none(r.get("entry_year")),
            "draft_round": None,  # rosters has draft_number only
            "draft_pick": _to_int_or_none(r.get("draft_number")),
            "current_team_id": team_id,
        })

    return rows, skipped_unknown_pos


def _transform_player_seasons(
    df_rosters: pd.DataFrame,
    season: int,
    team_abbr_to_id: dict[str, int],
    gsis_to_player_id: dict[str, int],
) -> tuple[list[dict[str, object]], int, int]:
    """Reshape ``load_rosters([season])`` into ``player_seasons`` rows.

    Returns:
        (list of row dicts ready to insert, skipped_unknown_pos, skipped_unknown_team)
    """
    rows: list[dict[str, object]] = []
    seen_keys: set[tuple[int, int, int]] = set()
    skipped_unknown_pos = 0
    skipped_unknown_team = 0
    dropped_dupes = 0

    for _, r in df_rosters.iterrows():
        gsis = str(r["gsis_id"])
        player_id = gsis_to_player_id.get(gsis)
        if player_id is None:
            # gsis_id was in rosters but didn't make it into players (e.g.
            # was skipped for unknown position). Skip silently — already
            # counted by _transform_players.
            continue

        team_abbr = _to_str_or_none(r.get("team"))
        team_id = team_abbr_to_id.get(team_abbr) if team_abbr else None
        if team_id is None:
            skipped_unknown_team += 1
            continue

        # Note the column-name swap in load_rosters: 'position' is the broad
        # group, 'depth_chart_position' is the specific label.
        pos = _safe_canonical(r.get("position"), r.get("depth_chart_position"))
        if pos is None:
            skipped_unknown_pos += 1
            continue

        key = (player_id, season, team_id)
        if key in seen_keys:
            dropped_dupes += 1
            continue
        seen_keys.add(key)

        rows.append({
            "player_id": player_id,
            "season": season,
            "team_id": team_id,
            "position_played": pos,
            "games": 0,
            "games_started": 0,
            "snaps_offense": 0,
            "snaps_defense": 0,
            "snaps_special": 0,
        })

    if dropped_dupes:
        logger.warning(
            "dropped %d duplicate player_seasons rows for season=%d",
            dropped_dupes, season,
        )
    return rows, skipped_unknown_pos, skipped_unknown_team


def _upsert_players(conn: Connection, rows: list[dict[str, object]]) -> int:
    """UPSERT into players keyed on gsis_id."""
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO players (
            gsis_id, pfr_id, full_name, position, birth_date, height_inches, weight_lbs,
            draft_year, draft_round, draft_pick, current_team_id, last_updated
        )
        VALUES (
            :gsis_id, :pfr_id, :full_name, :position, :birth_date, :height_inches, :weight_lbs,
            :draft_year, :draft_round, :draft_pick, :current_team_id, NOW()
        )
        ON CONFLICT (gsis_id) DO UPDATE SET
            pfr_id          = COALESCE(EXCLUDED.pfr_id, players.pfr_id),
            full_name       = EXCLUDED.full_name,
            position        = EXCLUDED.position,
            birth_date      = EXCLUDED.birth_date,
            height_inches   = EXCLUDED.height_inches,
            weight_lbs      = EXCLUDED.weight_lbs,
            draft_year      = EXCLUDED.draft_year,
            draft_round     = EXCLUDED.draft_round,
            draft_pick      = EXCLUDED.draft_pick,
            current_team_id = EXCLUDED.current_team_id,
            last_updated    = NOW()
        """
    )
    conn.execute(sql, rows)
    return len(rows)


def _upsert_player_seasons(
    conn: Connection, rows: list[dict[str, object]], season: int
) -> int:
    """DELETE existing rows for season, then bulk INSERT.

    Idempotent and simpler than per-row ON CONFLICT for our PK
    (player_id, season, team_id). Wrapped in the same transaction as
    _upsert_players so a partial failure rolls back.
    """
    conn.execute(
        text("DELETE FROM player_seasons WHERE season = :s"),
        {"s": season},
    )
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO player_seasons (
            player_id, season, team_id, position_played,
            games, games_started, snaps_offense, snaps_defense, snaps_special
        )
        VALUES (
            :player_id, :season, :team_id, :position_played,
            :games, :games_started, :snaps_offense, :snaps_defense, :snaps_special
        )
        """
    )
    conn.execute(sql, rows)
    return len(rows)
