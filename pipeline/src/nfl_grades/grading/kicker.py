"""K v1 grading pipeline (ADR-0023).

Flow:
    1. ``extract_features``: reads ``kicker_stats`` (ingested by
       ``ingest/kicker.py``), filters to kickers with min FG attempts,
       computes per-attempt rate metrics in Python.
    2. ``compute_grades``: shrink → z-score → NaN neutralization →
       composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Data begins 2016. Earlier seasons return empty results.

Qualification is FG-attempt based: 10 FG att to appear, 20 qualified,
30 full confidence. K is the only graded position not snap-based —
kickers have no useful snap count (kicking specialists).
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
    K_COMPONENT_FG_LONG,
    K_COMPONENT_FG_PCT,
    K_COMPONENT_FG_PCT_40_PLUS,
    K_COMPONENT_PAT_PCT,
    K_V1_CONFIDENCE_FULL_FG_ATT,
    K_V1_MIN_FG_ATT_TO_GRADE,
    K_V1_QUALIFIED_MIN_FG_ATT,
    K_V1_RAW_VALUE_COLS,
    K_V1_SAMPLE_SIZE_COLS,
    K_V1_SHRINKAGE_K,
    K_V1_WEIGHTS,
)
from nfl_grades.ingest.kicker import KICKER_STATS_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "K"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_kickers_total: int
    n_kickers_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    if season < KICKER_STATS_MIN_SEASON:
        logger.warning(
            "K grading requires season >= %d; got %d — skipping",
            KICKER_STATS_MIN_SEASON, season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:k", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no K players found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_kickers_total=len(graded),
            n_kickers_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"kickers_total={result.n_kickers_total} "
            f"kickers_qualified={result.n_kickers_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        ks.player_id,
        p.full_name,
        p.gsis_id,
        ks.games,
        COALESCE(ks.fg_att, 0)            AS fg_att,
        COALESCE(ks.fg_made, 0)           AS fg_made,
        ks.fg_long,
        COALESCE(ks.fg_att_40_49, 0)      AS fg_att_40_49,
        COALESCE(ks.fg_made_40_49, 0)     AS fg_made_40_49,
        COALESCE(ks.fg_att_50_59, 0)      AS fg_att_50_59,
        COALESCE(ks.fg_made_50_59, 0)     AS fg_made_50_59,
        COALESCE(ks.fg_att_60_plus, 0)    AS fg_att_60_plus,
        COALESCE(ks.fg_made_60_plus, 0)   AS fg_made_60_plus,
        COALESCE(ks.pat_att, 0)           AS pat_att,
        COALESCE(ks.pat_made, 0)          AS pat_made
    FROM kicker_stats ks
    JOIN players p ON p.player_id = ks.player_id
    WHERE ks.season = :season
      AND COALESCE(ks.fg_att, 0) >= :min_fg_att
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_fg_att": K_V1_MIN_FG_ATT_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = (
        "fg_att", "fg_made",
        "fg_att_40_49", "fg_made_40_49",
        "fg_att_50_59", "fg_made_50_59",
        "fg_att_60_plus", "fg_made_60_plus",
        "pat_att", "pat_made",
        "games",
    )
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)
    # fg_long is nullable (kicker with no FG attempts has no long).
    df["fg_long"] = df["fg_long"].astype("Float64").astype(float)

    # Compute rate features.
    fg_att = df["fg_att"].astype(float).clip(lower=1)
    df["fg_pct"] = df["fg_made"] / fg_att

    fg_att_40p = (
        df["fg_att_40_49"] + df["fg_att_50_59"] + df["fg_att_60_plus"]
    ).astype(float)
    fg_made_40p = (
        df["fg_made_40_49"] + df["fg_made_50_59"] + df["fg_made_60_plus"]
    ).astype(float)
    df["fg_att_40_plus"] = fg_att_40p.astype(int)
    df["fg_pct_40_plus"] = fg_made_40p / fg_att_40p.replace(0, np.nan)

    pat_att = df["pat_att"].astype(float).clip(lower=1)
    df["pat_pct"] = df["pat_made"] / pat_att

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    df["qualified"] = df["fg_att"] >= K_V1_QUALIFIED_MIN_FG_ATT
    df["confidence"] = (
        df["fg_att"].astype(float) / K_V1_CONFIDENCE_FULL_FG_ATT
    ).clip(upper=1.0)

    data_tier, data_tier_reason = _era_tier_for_season(season)
    df["data_tier"] = data_tier
    df["data_tier_reason"] = data_tier_reason

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in K_V1_RAW_VALUE_COLS.items():
        n_col = K_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = K_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, K_V1_WEIGHTS)
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
      AND component_name LIKE 'k_%'
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
    components = list(K_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = K_V1_SAMPLE_SIZE_COLS[component]
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
