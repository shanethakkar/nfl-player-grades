"""Ingest end-of-regular-season depth charts.

V1 scope: one snapshot per team per season, stored as ``week=99`` (per the
schema comment in 0001_init.sql which reserves 99 for the end-of-season
snapshot). We use the latest available depth-chart data as the snapshot.

Two source schemas — nflverse changed formats starting in 2025:

    **Old (<=2024)**  per-week rows:
        season, club_code, week, game_type, depth_team, formation,
        gsis_id, position, depth_position, ...

    **New (2025+)**  timestamp-keyed rows:
        dt, team, gsis_id, pos_grp, pos_abb, pos_slot, pos_rank

We normalize both into a common intermediate shape (club_code, gsis_id,
position, depth_order) and select the latest-available snapshot from
whichever format applies.

Position label:
    Normalized from ``depth_position`` / ``pos_abb``. Specific enough for
    a depth-chart explorer (RG / LCB / LT rather than G / CB / T).

Why week=99 and not the real week number:
    So consumers can write ``WHERE week = 99`` for "current depth chart"
    queries without needing to know what the last played week was.
    A future enhancement can also store per-week depth charts at
    weeks 1..18 without colliding.

See also:
    - db/migrations/0001_init.sql   -- schema
    - ingest/_cache.py              -- nflreadpy entry point
    - docs/exploration/2026-04-23-snaps-depth.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.ingest._cache import cache_or_fetch

logger = logging.getLogger(__name__)

SNAPSHOT_WEEK = 99


@dataclass(frozen=True)
class RunResult:
    season: int
    source_format: str  # 'week-keyed' (<=2024) or 'timestamp-keyed' (2025+)
    source_label: str  # e.g. 'week=19' or 'dt=2026-03-14T07:32:09Z'
    rows_inserted: int  # rows written to depth_charts
    skipped_unknown_team: int
    skipped_unknown_player: int
    skipped_non_integer_depth: int
    skipped_duplicate: int


def run(season: int, *, refresh: bool = False) -> RunResult:
    """Build the end-of-season depth-chart snapshot for ``season``.

    Requires: rosters.run(season) has populated the players table so that
    every gsis_id on the source depth chart can be joined back to a
    player_id. Missing players are silently skipped (most often PS /
    waived players who didn't finish the season).
    """
    if season < 2001:
        raise ValueError(f"depth_charts coverage begins ~2001; got {season}")

    df_all = cache_or_fetch("depth_charts", season=season, refresh=refresh)
    df_snap, source_format, source_label = _select_snapshot(df_all, season)
    logger.info(
        "using %s %s (%d rows) for season %d",
        source_format,
        source_label,
        len(df_snap),
        season,
    )

    engine = get_engine()
    with pipeline_run("ingest:depth_charts", season=season) as handle:
        with engine.begin() as conn:
            team_lookup = _team_abbr_to_id(conn)
            gsis_to_player_id = _gsis_to_player_id(conn)

            rows, skipped = _transform(df_snap, team_lookup, gsis_to_player_id, season)
            inserted = _replace_snapshot(conn, rows, season)

        result = RunResult(
            season=season,
            source_format=source_format,
            source_label=source_label,
            rows_inserted=inserted,
            skipped_unknown_team=skipped["team"],
            skipped_unknown_player=skipped["player"],
            skipped_non_integer_depth=skipped["depth"],
            skipped_duplicate=skipped["duplicate"],
        )
        handle.rows_written = inserted
        handle.note(
            f"source={source_format}:{source_label} inserted={inserted} "
            f"skipped_team={skipped['team']} "
            f"skipped_player={skipped['player']} "
            f"skipped_depth={skipped['depth']} "
            f"skipped_dup={skipped['duplicate']}"
        )
    return result


# ---------------------------------------------------------------------------
# Schema normalization (handles the 2024 vs 2025+ format change)
# ---------------------------------------------------------------------------


def _select_snapshot(df_all: pd.DataFrame, season: int) -> tuple[pd.DataFrame, str, str]:
    """Pick the latest-available snapshot and normalize column names.

    Returns (normalized_df, source_format, source_label). The normalized
    DataFrame has these columns:
        club_code, gsis_id, position, depth_order_raw
    """
    # --- Old format (<=2024): week-keyed with game_type + depth_team -----
    if "game_type" in df_all.columns and "week" in df_all.columns:
        df_reg = df_all[df_all["game_type"] == "REG"].copy()
        df_reg = df_reg[df_reg["week"].notna()].copy()
        if df_reg.empty:
            raise RuntimeError(f"no REG depth-chart rows for season {season}")
        df_reg["week"] = df_reg["week"].astype(int)
        source_week = int(df_reg["week"].max())
        snap = df_reg[df_reg["week"] == source_week].copy()

        # Normalize position: prefer depth_position, fall back to position.
        def _pos(r: pd.Series) -> str | None:
            dp = r.get("depth_position")
            if isinstance(dp, str) and dp.strip():
                return dp.strip()
            p = r.get("position")
            return p.strip() if isinstance(p, str) and p.strip() else None

        snap = snap.assign(
            _position_norm=snap.apply(_pos, axis=1),
            _depth_order_raw=snap["depth_team"],
        )
        out = snap.rename(columns={"club_code": "club_code"})[
            ["club_code", "gsis_id", "_position_norm", "_depth_order_raw"]
        ].rename(columns={"_position_norm": "position", "_depth_order_raw": "depth_order_raw"})
        return out, "week-keyed", f"week={source_week}"

    # --- New format (2025+): timestamp-keyed with pos_abb + pos_rank ------
    if "dt" in df_all.columns and "pos_abb" in df_all.columns:
        if df_all.empty:
            raise RuntimeError(f"no depth-chart rows for season {season}")
        latest_dt = df_all["dt"].max()
        snap = df_all[df_all["dt"] == latest_dt].copy()
        out = snap.rename(
            columns={
                "team": "club_code",
                "pos_abb": "position",
                "pos_rank": "depth_order_raw",
            }
        )[["club_code", "gsis_id", "position", "depth_order_raw"]]
        return out, "timestamp-keyed", f"dt={latest_dt}"

    raise RuntimeError(
        f"unrecognized depth-chart schema for season {season}; columns={sorted(df_all.columns)}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _team_abbr_to_id(conn: Connection) -> dict[str, int]:
    rows = conn.execute(text("SELECT alias, team_id FROM team_aliases")).all()
    if not rows:
        raise RuntimeError("team_aliases is empty; run migrate --seeds first.")
    return {alias: team_id for alias, team_id in rows}


def _gsis_to_player_id(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT gsis_id, player_id FROM players WHERE gsis_id IS NOT NULL")
    ).all()
    return {gsis: pid for gsis, pid in rows}


def _resolve_depth(raw: object) -> int | None:
    """Parse '1'/'2'/'3' or int 1/2/3 into an integer depth_order."""
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _transform(
    df: pd.DataFrame,
    team_abbr_to_id: dict[str, int],
    gsis_to_player_id: dict[str, int],
    season: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Map the normalized depth-chart snapshot to depth_charts rows.

    Expects ``df`` to have columns: club_code, gsis_id, position,
    depth_order_raw (produced by ``_select_snapshot``).

    Returns (rows, counters_dict).
    """
    rows: list[dict[str, object]] = []
    seen: set[tuple[int, str, int]] = set()  # (team_id, position, depth_order)
    skipped = {"team": 0, "player": 0, "depth": 0, "duplicate": 0}

    for _, r in df.iterrows():
        club = r.get("club_code")
        if not isinstance(club, str) or not club:
            skipped["team"] += 1
            continue
        team_id = team_abbr_to_id.get(club)
        if team_id is None:
            skipped["team"] += 1
            continue

        gsis = r.get("gsis_id")
        if not isinstance(gsis, str) or not gsis:
            skipped["player"] += 1
            continue
        player_id = gsis_to_player_id.get(gsis)
        if player_id is None:
            skipped["player"] += 1
            continue

        pos = r.get("position")
        if not isinstance(pos, str) or not pos.strip():
            skipped["player"] += 1
            continue
        pos = pos.strip()

        depth_order = _resolve_depth(r.get("depth_order_raw"))
        if depth_order is None:
            skipped["depth"] += 1
            continue

        key = (team_id, pos, depth_order)
        if key in seen:
            # Same (team, position, depth_order) from another formation or
            # a duplicate source row — schema PK would reject it. Keep
            # first occurrence.
            skipped["duplicate"] += 1
            continue
        seen.add(key)

        rows.append(
            {
                "team_id": team_id,
                "season": season,
                "week": SNAPSHOT_WEEK,
                "position": pos,
                "depth_order": depth_order,
                "player_id": player_id,
            }
        )

    return rows, skipped


def _replace_snapshot(conn: Connection, rows: list[dict[str, object]], season: int) -> int:
    """Delete any existing snapshot rows for (season, week=99) and bulk
    INSERT the new rows. Idempotent."""
    conn.execute(
        text("DELETE FROM depth_charts WHERE season = :s AND week = :w"),
        {"s": season, "w": SNAPSHOT_WEEK},
    )
    if not rows:
        return 0
    conn.execute(
        text(
            """
            INSERT INTO depth_charts (
                team_id, season, week, position, depth_order, player_id
            )
            VALUES (
                :team_id, :season, :week, :position, :depth_order, :player_id
            )
            """
        ),
        rows,
    )
    return len(rows)
