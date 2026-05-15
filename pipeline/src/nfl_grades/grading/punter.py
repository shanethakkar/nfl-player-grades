"""P v1 grading pipeline (ADR-0024).

Flow:
    1. ``extract_features``: reads ``punter_stats`` (ingested by
       ``ingest/punter.py``), filters to punters with min punts,
       computes per-punt rate metrics in Python.
    2. ``compute_grades``: shrink → z-score → NaN neutralization →
       composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Data begins 2016. Earlier seasons return empty results.

Qualification is punt-count based: 25 punts to appear, 40 qualified,
60 full confidence.
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
    P_COMPONENT_INSIDE_20_RATE,
    P_COMPONENT_NET_AVG,
    P_V1_CONFIDENCE_FULL_PUNTS,
    P_V1_MIN_PUNTS_TO_GRADE,
    P_V1_QUALIFIED_MIN_PUNTS,
    P_V1_RAW_VALUE_COLS,
    P_V1_SAMPLE_SIZE_COLS,
    P_V1_SHRINKAGE_K,
    P_V1_WEIGHTS,
)
from nfl_grades.ingest.punter import PUNTER_STATS_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "P"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_punters_total: int
    n_punters_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    if season < PUNTER_STATS_MIN_SEASON:
        logger.warning(
            "P grading requires season >= %d; got %d — skipping",
            PUNTER_STATS_MIN_SEASON, season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:p", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no P players found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_punters_total=len(graded),
            n_punters_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"punters_total={result.n_punters_total} "
            f"punters_qualified={result.n_punters_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        ps.player_id,
        p.full_name,
        p.gsis_id,
        COALESCE(ps.punts, 0)         AS punts,
        COALESCE(ps.gross_yards, 0)   AS gross_yards,
        COALESCE(ps.return_yards, 0)  AS return_yards,
        COALESCE(ps.net_yards, 0)     AS net_yards,
        COALESCE(ps.inside_20, 0)     AS inside_20,
        COALESCE(ps.touchbacks, 0)    AS touchbacks,
        COALESCE(ps.blocked, 0)       AS blocked,
        ps.long_punt
    FROM punter_stats ps
    JOIN players p ON p.player_id = ps.player_id
    WHERE ps.season = :season
      AND COALESCE(ps.punts, 0) >= :min_punts
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_punts": P_V1_MIN_PUNTS_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = (
        "punts", "gross_yards", "return_yards", "net_yards",
        "inside_20", "touchbacks", "blocked",
    )
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)
    df["long_punt"] = df["long_punt"].astype("Float64").astype(float)

    punts_safe = df["punts"].astype(float).clip(lower=1)
    df["net_avg"] = df["net_yards"] / punts_safe
    df["gross_avg"] = df["gross_yards"] / punts_safe
    df["inside_20_rate"] = df["inside_20"] / punts_safe
    df["touchback_rate"] = df["touchbacks"] / punts_safe
    df["blocked_rate"] = df["blocked"] / punts_safe

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    df["qualified"] = df["punts"] >= P_V1_QUALIFIED_MIN_PUNTS
    df["confidence"] = (
        df["punts"].astype(float) / P_V1_CONFIDENCE_FULL_PUNTS
    ).clip(upper=1.0)

    data_tier, data_tier_reason = _era_tier_for_season(season)
    df["data_tier"] = data_tier
    df["data_tier_reason"] = data_tier_reason

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in P_V1_RAW_VALUE_COLS.items():
        n_col = P_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = P_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, P_V1_WEIGHTS)
    df["grade"] = sigmoid.to_grade(df["composite_z"].to_numpy())

    qualified_grades = df.loc[df["qualified"], "grade"].sort_values().to_numpy()
    if len(qualified_grades) >= 2:
        df["percentile"] = df["grade"].apply(
            lambda g: (
                100.0 * np.searchsorted(qualified_grades, g, side="right") / len(qualified_grades)
                if not pd.isna(g)
                else np.nan
            )
        )
    else:
        df["percentile"] = 50.0
    df.loc[df["grade"].isna(), "percentile"] = np.nan

    return df


# ---------------------------------------------------------------------------
# 3. Write results
# ---------------------------------------------------------------------------

_DELETE_STAT_COMPONENTS = text("""
    DELETE FROM stat_components
    WHERE season = :season
      AND component_name LIKE 'p_%'
""")

_DELETE_SEASON_GRADES = text("""
    DELETE FROM season_grades
    WHERE season = :season AND position = :position
""")

_INSERT_STAT_COMPONENTS = text("""
    INSERT INTO stat_components
        (player_id, season, component_name, raw_value, adjusted_value,
         z_score, sample_size, used_in_composite)
    VALUES
        (:player_id, :season, :component_name, :raw_value, :adjusted_value,
         :z_score, :sample_size, :used_in_composite)
""")

_INSERT_SEASON_GRADES = text("""
    INSERT INTO season_grades
        (player_id, season, position, composite_grade, composite_z,
         percentile, confidence, data_tier, qualified, role, data_tier_reason)
    VALUES
        (:player_id, :season, :position, :composite_grade, :composite_z,
         :percentile, :confidence, :data_tier, :qualified, :role,
         :data_tier_reason)
""")


def write_results(conn: Connection, graded: pd.DataFrame, season: int) -> tuple[int, int]:
    components = list(P_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = P_V1_SAMPLE_SIZE_COLS[component]
        for _, r in graded.iterrows():
            raw = r[f"raw_{component}"]
            adj = r[f"adjusted_{component}"]
            z = r[f"z_{component}"]
            component_rows.append({
                "player_id":      int(r["player_id"]),
                "season":         season,
                "component_name": component,
                "raw_value":      None if pd.isna(raw) else float(raw),
                "adjusted_value": None if pd.isna(adj) else float(adj),
                "z_score":        None if pd.isna(z) else float(z),
                "sample_size":    int(r[n_col]) if not pd.isna(r[n_col]) else 0,
                "used_in_composite": True,
            })

    conn.execute(_DELETE_STAT_COMPONENTS, {"season": season})
    if component_rows:
        conn.execute(_INSERT_STAT_COMPONENTS, component_rows)

    grade_rows: list[dict[str, object]] = []
    for _, r in graded.iterrows():
        if pd.isna(r["grade"]):
            continue
        reason = r["data_tier_reason"]
        reason_out: str | None = None if (
            reason is None or (isinstance(reason, float) and pd.isna(reason))
        ) else str(reason)
        grade_rows.append({
            "player_id":      int(r["player_id"]),
            "season":         season,
            "position":       POSITION,
            "composite_grade": float(r["grade"]),
            "composite_z":    float(r["composite_z"]),
            "percentile":     float(r["percentile"]) if not pd.isna(r["percentile"]) else 50.0,
            "confidence":     float(r["confidence"]),
            "data_tier":      int(r["data_tier"]),
            "qualified":      bool(r["qualified"]),
            "role":           None,
            "data_tier_reason": reason_out,
        })

    conn.execute(_DELETE_SEASON_GRADES, {"season": season, "position": POSITION})
    if grade_rows:
        conn.execute(_INSERT_SEASON_GRADES, grade_rows)

    return len(component_rows), len(grade_rows)


__all__ = [
    "POSITION",
    "RunResult",
    "compute_grades",
    "extract_features",
    "run",
    "write_results",
]
