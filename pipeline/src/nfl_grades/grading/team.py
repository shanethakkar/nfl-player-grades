"""Team-level overall grading (ADR-0026).

Two-stage aggregation of *existing* player grades into team grades:

  Stage 1 — within a position: snap-weighted average of every player's
    composite_z value at that position on the team. OL is exempt — its
    team-level z-score (team_ol_grades.composite_z) is plugged in directly.

  Stage 2 — across positions in a phase: position-weighted sum of
    Stage 1 z-scores → phase composite z. Standardized within the
    season's 32-team cohort, then sigmoided to a 0-100 phase grade.

  Overall composite = phase-weighted sum of phase z-scores, standardized
    + sigmoided the same way.

Position + phase weights are empirically derived; see ADR-0026 §Position
Weights and the audit at docs/grading/audits/2026-05-25-team-weights.md.

There is no new ingest. All inputs come from already-populated tables
(season_grades, team_ol_grades, player_seasons).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.grading import sigmoid
from nfl_grades.grading.weights import (
    TEAM_V1_OFFENSE_WEIGHTS,
    TEAM_V1_DEFENSE_WEIGHTS,
    TEAM_V1_ST_WEIGHTS,
    TEAM_V1_PHASE_WEIGHTS,
)

logger = logging.getLogger(__name__)

PHASES: dict[str, dict[str, float]] = {
    "offense": TEAM_V1_OFFENSE_WEIGHTS,
    "defense": TEAM_V1_DEFENSE_WEIGHTS,
    "st": TEAM_V1_ST_WEIGHTS,
}

# Which snap column per position. Defensive players get their defense
# snaps even if they touched ST; ST grade uses snaps_special.
SNAP_COL_OFFENSE = {"QB", "RB", "WR", "TE"}  # OL handled separately
SNAP_COL_DEFENSE = {"EDGE", "iDL", "LB", "CB", "S"}
SNAP_COL_ST = {"K", "P"}


@dataclass(frozen=True)
class RunResult:
    season: int
    n_teams: int
    n_components: int


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_player_position_data(conn: Connection, season: int) -> pd.DataFrame:
    """One row per (team_id, season, position, player_id) with the player's
    composite_z and the snap count from player_seasons for the right phase."""
    sql = text(
        """
        SELECT
            ps.team_id,
            sg.season,
            sg.position,
            sg.player_id,
            sg.composite_z,
            sg.composite_grade,
            ps.snaps_offense,
            ps.snaps_defense,
            ps.snaps_special
        FROM season_grades sg
        JOIN player_seasons ps
          ON ps.player_id = sg.player_id AND ps.season = sg.season
        WHERE sg.season = :season
          AND sg.position IN ('QB','RB','WR','TE','EDGE','iDL','LB','CB','S','K','P')
        """
    )
    df = pd.read_sql(sql, conn, params={"season": season})

    # Pick the right snap column per position.
    def snaps_for(row: pd.Series) -> int:
        if row["position"] in SNAP_COL_OFFENSE:
            return int(row["snaps_offense"] or 0)
        if row["position"] in SNAP_COL_DEFENSE:
            return int(row["snaps_defense"] or 0)
        if row["position"] in SNAP_COL_ST:
            return int(row["snaps_special"] or 0)
        return 0

    df["snaps"] = df.apply(snaps_for, axis=1)
    df = df[df["snaps"] > 0].copy()
    return df


def _load_ol_grades(conn: Connection, season: int) -> pd.DataFrame:
    """One row per team_id with the OL composite_z + composite_grade."""
    sql = text(
        """
        SELECT
            team_id,
            composite_z   AS ol_z,
            composite_grade AS ol_grade
        FROM team_ol_grades
        WHERE season = :season
        """
    )
    return pd.read_sql(sql, conn, params={"season": season})


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_per_position(
    player_df: pd.DataFrame, ol_df: pd.DataFrame
) -> pd.DataFrame:
    """Stage 1: snap-weighted per-(team, position) z-score and grade.

    Returns one row per (team_id, position) with:
      position_z    — snap-weighted mean of player composite_z
      position_grade — snap-weighted mean of player composite_grade (for UI)
      total_snaps   — denominator
      n_players     — distinct players contributing
    OL is appended directly from team_ol_grades (no aggregation).
    """
    grp = player_df.groupby(["team_id", "position"])

    def _agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "position_z": float(
                    np.average(g["composite_z"], weights=g["snaps"])
                ),
                "position_grade": float(
                    np.average(g["composite_grade"], weights=g["snaps"])
                ),
                "total_snaps": int(g["snaps"].sum()),
                "n_players": int(len(g)),
            }
        )

    per_pos = grp.apply(_agg, include_groups=False).reset_index()

    # OL: plug in team_ol_grades directly.
    ol_rows = ol_df.assign(
        position="OL",
        position_z=ol_df["ol_z"],
        position_grade=ol_df["ol_grade"],
        total_snaps=0,
        n_players=5,  # nominal — an OL is 5 players, no per-player attribution
    )[["team_id", "position", "position_z", "position_grade", "total_snaps", "n_players"]]

    return pd.concat([per_pos, ol_rows], ignore_index=True)


def compute_phase_z(per_pos: pd.DataFrame, phase_weights: dict[str, float]) -> pd.Series:
    """Stage 2 (z-score path): position-weighted sum of per-position z-scores
    for a single phase. Returns a Series indexed by team_id.

    Falls back to weight redistribution if a team is missing a position
    in the phase (rare — typically a one-off K/P injury wipeout)."""
    positions = list(phase_weights.keys())
    sub = per_pos[per_pos["position"].isin(positions)].copy()
    wide = sub.pivot(index="team_id", columns="position", values="position_z")

    teams = wide.index
    out = pd.Series(0.0, index=teams, dtype=float)
    for team_id in teams:
        row = wide.loc[team_id]
        present = {p: phase_weights[p] for p in positions if p in row.index and pd.notna(row[p])}
        if not present:
            out.loc[team_id] = np.nan
            continue
        # Renormalize the weights of the present positions so they sum to 1
        # (handles the rare missing-position case cleanly).
        total = sum(present.values())
        out.loc[team_id] = sum(row[p] * (w / total) for p, w in present.items())
    return out


def _standardize(s: pd.Series) -> pd.Series:
    """Z-standardize a Series (mean 0, SD 1, ddof=1). Constant inputs return 0s."""
    valid = s.dropna()
    if len(valid) < 2:
        return s * 0.0
    mu = float(valid.mean())
    sd = float(valid.std(ddof=1))
    if sd == 0:
        return s * 0.0
    return (s - mu) / sd


# ---------------------------------------------------------------------------
# Top-level run
# ---------------------------------------------------------------------------


def compute_grades(
    player_df: pd.DataFrame, ol_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (team_grades_df, components_df).

    team_grades_df columns:
      team_id, overall_grade, offense_grade, defense_grade, st_grade,
      overall_z, offense_z, defense_z, st_z,
      overall_percentile, offense_percentile, defense_percentile, st_percentile,
      data_tier_reason

    components_df columns:
      team_id, phase, position, position_grade, weight, n_players, total_snaps
    """
    per_pos = aggregate_per_position(player_df, ol_df)

    # Stage 2 per phase: raw phase z = position-weighted sum of position z's.
    phase_raw = {}
    for phase, weights in PHASES.items():
        phase_raw[phase] = compute_phase_z(per_pos, weights)

    # Standardize each phase's raw composite within the 32-team cohort,
    # then sigmoid to a 0-100 phase grade.
    team_ids = pd.Index(sorted(set().union(*[s.index for s in phase_raw.values()])))
    out = pd.DataFrame(index=team_ids)
    for phase, raw in phase_raw.items():
        z = _standardize(raw.reindex(team_ids))
        out[f"{phase}_z"] = z
        out[f"{phase}_grade"] = sigmoid.to_grade(z.values)
        out[f"{phase}_percentile"] = z.rank(pct=True) * 100.0

    # Overall: phase-weighted sum of phase z-scores → standardize → sigmoid.
    overall_raw = sum(
        out[f"{phase}_z"] * w for phase, w in TEAM_V1_PHASE_WEIGHTS.items()
    )
    overall_z = _standardize(overall_raw)
    out["overall_z"] = overall_z
    out["overall_grade"] = sigmoid.to_grade(overall_z.values)
    out["overall_percentile"] = overall_z.rank(pct=True) * 100.0

    out["data_tier_reason"] = None  # populated below if any team had a missing position
    out = out.reset_index().rename(columns={"index": "team_id"})

    # Build the components DataFrame.
    rows = []
    for phase, weights in PHASES.items():
        for pos, w in weights.items():
            sub = per_pos[per_pos["position"] == pos]
            for _, r in sub.iterrows():
                rows.append(
                    {
                        "team_id": int(r["team_id"]),
                        "phase": phase,
                        "position": pos,
                        "position_grade": float(r["position_grade"]),
                        "weight": float(w),
                        "n_players": int(r["n_players"]),
                        "total_snaps": int(r["total_snaps"]),
                    }
                )
    components = pd.DataFrame(rows)
    return out, components


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


def write_results(
    conn: Connection,
    team_grades: pd.DataFrame,
    components: pd.DataFrame,
    season: int,
) -> tuple[int, int]:
    """Idempotent — delete-then-insert for the season."""
    conn.execute(text("DELETE FROM team_grade_components WHERE season = :s"), {"s": season})
    conn.execute(text("DELETE FROM team_grades WHERE season = :s"), {"s": season})

    n_grades = 0
    for _, row in team_grades.iterrows():
        conn.execute(
            text(
                """
                INSERT INTO team_grades (
                    team_id, season,
                    overall_grade, offense_grade, defense_grade, st_grade,
                    overall_z, offense_z, defense_z, st_z,
                    overall_percentile, offense_percentile, defense_percentile, st_percentile,
                    data_tier_reason
                ) VALUES (
                    :team_id, :season,
                    :overall_grade, :offense_grade, :defense_grade, :st_grade,
                    :overall_z, :offense_z, :defense_z, :st_z,
                    :overall_percentile, :offense_percentile, :defense_percentile, :st_percentile,
                    :data_tier_reason
                )
                """
            ),
            {
                "team_id": int(row["team_id"]),
                "season": season,
                "overall_grade": float(row["overall_grade"]),
                "offense_grade": float(row["offense_grade"]),
                "defense_grade": float(row["defense_grade"]),
                "st_grade": float(row["st_grade"]),
                "overall_z": float(row["overall_z"]),
                "offense_z": float(row["offense_z"]),
                "defense_z": float(row["defense_z"]),
                "st_z": float(row["st_z"]),
                "overall_percentile": float(row["overall_percentile"]),
                "offense_percentile": float(row["offense_percentile"]),
                "defense_percentile": float(row["defense_percentile"]),
                "st_percentile": float(row["st_percentile"]),
                "data_tier_reason": row["data_tier_reason"],
            },
        )
        n_grades += 1

    n_components = 0
    for _, row in components.iterrows():
        conn.execute(
            text(
                """
                INSERT INTO team_grade_components (
                    team_id, season, phase, position,
                    position_grade, weight, n_players, total_snaps
                ) VALUES (
                    :team_id, :season, :phase, :position,
                    :position_grade, :weight, :n_players, :total_snaps
                )
                """
            ),
            {
                "team_id": int(row["team_id"]),
                "season": season,
                "phase": row["phase"],
                "position": row["position"],
                "position_grade": float(row["position_grade"]),
                "weight": float(row["weight"]),
                "n_players": int(row["n_players"]),
                "total_snaps": int(row["total_snaps"]),
            },
        )
        n_components += 1

    return n_grades, n_components


def run(season: int) -> RunResult:
    """Grade every team for one season. Idempotent."""
    engine = get_engine()
    with pipeline_run("grading:team", season=season) as handle:
        with engine.begin() as conn:
            player_df = _load_player_position_data(conn, season)
            ol_df = _load_ol_grades(conn, season)
            if player_df.empty or ol_df.empty:
                logger.warning(
                    "team grading: missing data for season %d "
                    "(player rows=%d, ol rows=%d) — skipping",
                    season, len(player_df), len(ol_df),
                )
                return RunResult(season=season, n_teams=0, n_components=0)

            team_grades, components = compute_grades(player_df, ol_df)
            n_grades, n_components = write_results(conn, team_grades, components, season)

        handle.rows_written = n_grades
        handle.note(f"teams_graded={n_grades} components={n_components}")

    return RunResult(season=season, n_teams=n_grades, n_components=n_components)


__all__ = ["RunResult", "run", "compute_grades", "aggregate_per_position"]
