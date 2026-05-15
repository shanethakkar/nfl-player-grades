"""OL (offensive line unit) v1 grading pipeline (ADR-0025).

Team-level grading. The entity is (team_id, season), not (player_id, season).
Writes to dedicated team_ol_components / team_ol_grades tables.

Flow:
    1. ``extract_features``: reads ``team_ol_stats`` for the season,
       computes per-play rate metrics in Python.
    2. ``compute_grades``: shrink → z-score → composite → sigmoid → percentile.
    3. ``write_results``: idempotent upsert to team_ol_components +
       team_ol_grades.

Data begins 2018 (PFR rush stats start there; YBC needs PFR).

There is no qualification threshold — every team that played a season is
graded (32 teams × N seasons). Confidence is fixed at 1.0 because every
team has full-season volume on both denominators (rushes and dropbacks).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine, pipeline_run
from nfl_grades.grading import composite, empirical_bayes, sigmoid, zscore
from nfl_grades.grading.era_tier import _era_tier_for_season
from nfl_grades.grading.weights import (
    OL_COMPONENT_PRESSURE_PROXY,
    OL_COMPONENT_YBC_PER_CARRY,
    OL_V1_RAW_VALUE_COLS,
    OL_V1_SAMPLE_SIZE_COLS,
    OL_V1_SHRINKAGE_K,
    OL_V1_WEIGHTS,
)
from nfl_grades.ingest.team_ol import TEAM_OL_STATS_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "OL"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_teams_total: int
    n_teams_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    if season < TEAM_OL_STATS_MIN_SEASON:
        logger.warning(
            "OL grading requires season >= %d; got %d — skipping",
            TEAM_OL_STATS_MIN_SEASON, season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:ol", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no OL data for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_teams_total=len(graded),
            n_teams_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"teams_total={result.n_teams_total} "
            f"teams_qualified={result.n_teams_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        ts.team_id,
        t.abbr,
        COALESCE(ts.dropbacks, 0)            AS dropbacks,
        COALESCE(ts.sacks_allowed, 0)        AS sacks_allowed,
        COALESCE(ts.qb_hits_allowed, 0)      AS qb_hits_allowed,
        COALESCE(ts.rushes, 0)               AS rushes,
        COALESCE(ts.rush_yards, 0)           AS rush_yards,
        COALESCE(ts.yards_before_contact, 0) AS yards_before_contact,
        ts.rush_epa_total
    FROM team_ol_stats ts
    JOIN teams t ON t.team_id = ts.team_id
    WHERE ts.season = :season
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = conn.execute(_FEATURES_SQL, {"season": season}).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = ("dropbacks", "sacks_allowed", "qb_hits_allowed",
                "rushes", "rush_yards", "yards_before_contact")
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)

    rushes = df["rushes"].astype(float).clip(lower=1)
    drops = df["dropbacks"].astype(float).clip(lower=1)

    df["ybc_per_carry"] = df["yards_before_contact"].astype(float) / rushes
    df["pressure_proxy_per_dropback"] = (
        df["sacks_allowed"].astype(float) + df["qb_hits_allowed"].astype(float)
    ) / drops

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    # Every team is qualified — no per-player snap threshold concept here.
    df["qualified"] = True
    df["confidence"] = 1.0

    data_tier, data_tier_reason = _era_tier_for_season(season)
    df["data_tier"] = data_tier
    df["data_tier_reason"] = data_tier_reason

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in OL_V1_RAW_VALUE_COLS.items():
        n_col = OL_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = OL_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, OL_V1_WEIGHTS)
    df["grade"] = sigmoid.to_grade(df["composite_z"].to_numpy())

    grades_sorted = df["grade"].sort_values().to_numpy()
    if len(grades_sorted) >= 2:
        df["percentile"] = df["grade"].apply(
            lambda g: 100.0 * np.searchsorted(grades_sorted, g, side="right") / len(grades_sorted)
        )
    else:
        df["percentile"] = 50.0

    return df


# ---------------------------------------------------------------------------
# 3. Write results — to team_ol_* tables, not season_grades / stat_components
# ---------------------------------------------------------------------------

_DELETE_COMPONENTS = text("DELETE FROM team_ol_components WHERE season = :season")
_DELETE_GRADES = text("DELETE FROM team_ol_grades WHERE season = :season")

_INSERT_COMPONENTS = text("""
    INSERT INTO team_ol_components
        (team_id, season, component_name, raw_value, adjusted_value,
         z_score, sample_size, used_in_composite)
    VALUES
        (:team_id, :season, :component_name, :raw_value, :adjusted_value,
         :z_score, :sample_size, :used_in_composite)
""")

_INSERT_GRADES = text("""
    INSERT INTO team_ol_grades
        (team_id, season, composite_grade, composite_z, percentile,
         confidence, data_tier, qualified, data_tier_reason)
    VALUES
        (:team_id, :season, :composite_grade, :composite_z, :percentile,
         :confidence, :data_tier, :qualified, :data_tier_reason)
""")


def write_results(conn: Connection, graded: pd.DataFrame, season: int) -> tuple[int, int]:
    components = list(OL_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = OL_V1_SAMPLE_SIZE_COLS[component]
        for _, r in graded.iterrows():
            raw = r[f"raw_{component}"]
            adj = r[f"adjusted_{component}"]
            z = r[f"z_{component}"]
            component_rows.append({
                "team_id":          int(r["team_id"]),
                "season":           season,
                "component_name":   component,
                "raw_value":        None if pd.isna(raw) else float(raw),
                "adjusted_value":   None if pd.isna(adj) else float(adj),
                "z_score":          None if pd.isna(z) else float(z),
                "sample_size":      int(r[n_col]) if not pd.isna(r[n_col]) else 0,
                "used_in_composite": True,
            })

    conn.execute(_DELETE_COMPONENTS, {"season": season})
    if component_rows:
        conn.execute(_INSERT_COMPONENTS, component_rows)

    grade_rows: list[dict[str, object]] = []
    for _, r in graded.iterrows():
        if pd.isna(r["grade"]):
            continue
        reason = r["data_tier_reason"]
        reason_out: str | None = None if (
            reason is None or (isinstance(reason, float) and pd.isna(reason))
        ) else str(reason)
        grade_rows.append({
            "team_id":          int(r["team_id"]),
            "season":           season,
            "composite_grade":  float(r["grade"]),
            "composite_z":      float(r["composite_z"]),
            "percentile":       float(r["percentile"]),
            "confidence":       float(r["confidence"]),
            "data_tier":        int(r["data_tier"]),
            "qualified":        bool(r["qualified"]),
            "data_tier_reason": reason_out,
        })

    conn.execute(_DELETE_GRADES, {"season": season})
    if grade_rows:
        conn.execute(_INSERT_GRADES, grade_rows)

    return len(component_rows), len(grade_rows)


__all__ = [
    "POSITION",
    "RunResult",
    "compute_grades",
    "extract_features",
    "run",
    "write_results",
]
