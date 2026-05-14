"""LB v1 grading pipeline (ADR-0022).

Flow:
    1. ``extract_features``: reads ``pfr_def_lb`` + ``player_seasons``,
       filters to off-ball LBs (def_targets >= 20 — excludes 3-4 OLB pass
       rushers misclassified as LB in nflverse roster data), computes
       per-snap/per-target rates.
    2. ``compute_grades``: shrink → z-score → NaN neutralization →
       composite → sigmoid → percentile.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Data available from 2018. Earlier seasons return empty results.

Qualification: snap-based (200 to grade, 400 qualified, 700 full conf).
Off-ball role filter: def_targets >= 20 (see ADR-0022 OLB gap section).
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
    LB_COMPONENT_MISSED_TACKLE_RATE,
    LB_COMPONENT_PASSER_RATING_ALLOWED,
    LB_COMPONENT_PBU_RATE,
    LB_COMPONENT_PRESSURE_RATE,
    LB_COMPONENT_TACKLE_RATE,
    LB_COMPONENT_TFL_RATE,
    LB_V1_CONFIDENCE_FULL_SNAPS,
    LB_V1_MIN_SNAPS_TO_GRADE,
    LB_V1_MIN_TARGET_RATE_FOR_OFFBALL,
    LB_V1_MIN_TARGETS_FOR_OFFBALL,
    LB_V1_QUALIFIED_MIN_SNAPS,
    LB_V1_RAW_VALUE_COLS,
    LB_V1_SAMPLE_SIZE_COLS,
    LB_V1_SHRINKAGE_K,
    LB_V1_WEIGHTS,
)
from nfl_grades.ingest.pfr_lb import PFR_DEF_LB_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "LB"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_lbs_total: int
    n_lbs_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    if season < PFR_DEF_LB_MIN_SEASON:
        logger.warning(
            "LB grading requires season >= %d; got %d — skipping",
            PFR_DEF_LB_MIN_SEASON, season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:lb", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no LB players found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_lbs_total=len(graded),
            n_lbs_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"lbs_total={result.n_lbs_total} "
            f"lbs_qualified={result.n_lbs_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        lb.player_id,
        p.full_name,
        p.gsis_id,
        COALESCE(ps.snaps_defense, 0)        AS snaps_defense,
        COALESCE(lb.comb_tackles, 0)         AS comb_tackles,
        lb.missed_tackles,
        lb.tfl,
        COALESCE(lb.pressures, 0)            AS pressures,
        COALESCE(lb.sacks, 0)                AS sacks,
        COALESCE(lb.targets, 0)              AS targets,
        COALESCE(lb.completions_allowed, 0)  AS completions_allowed,
        COALESCE(lb.yards_allowed, 0)        AS yards_allowed,
        COALESCE(lb.tds_allowed, 0)          AS tds_allowed,
        COALESCE(lb.ints, 0)                 AS ints,
        COALESCE(lb.pbu, 0)                  AS pbu
    FROM pfr_def_lb lb
    JOIN players p ON p.player_id = lb.player_id
    LEFT JOIN (
        SELECT DISTINCT ON (player_id) player_id, snaps_defense, team_id, position_played
        FROM player_seasons
        WHERE season = :season
        ORDER BY player_id, snaps_defense DESC
    ) ps ON ps.player_id = lb.player_id
    WHERE lb.season = :season
      AND ps.position_played = 'LB'
      AND COALESCE(ps.snaps_defense, 0) >= :min_snaps
      AND COALESCE(lb.targets, 0) >= :min_targets
      AND COALESCE(lb.targets, 0)::float / GREATEST(COALESCE(ps.snaps_defense, 1), 1) >= :min_target_rate
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {
                "season": season,
                "min_snaps": LB_V1_MIN_SNAPS_TO_GRADE,
                "min_targets": LB_V1_MIN_TARGETS_FOR_OFFBALL,
                "min_target_rate": LB_V1_MIN_TARGET_RATE_FOR_OFFBALL,
            },
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = ("snaps_defense", "comb_tackles", "pressures", "targets",
                "completions_allowed", "tds_allowed", "ints", "pbu")
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)

    float_cols = ("missed_tackles", "tfl", "sacks", "yards_allowed")
    for col in float_cols:
        df[col] = df[col].astype("Float64").astype(float)

    snaps = df["snaps_defense"].astype(float).clip(lower=1)
    targets = df["targets"].astype(float).clip(lower=1)

    df["tackle_rate"] = df["comb_tackles"] / snaps
    df["tfl_rate"] = df["tfl"].fillna(0.0) / snaps
    df["pressure_rate"] = df["pressures"] / snaps
    df["pbu_rate"] = df["pbu"].astype(float) / targets

    # NFL passer rating allowed when targeted. Standard formula:
    #   a = clamp((comp%  - 0.30) * 5,           0, 2.375)
    #   b = clamp((yds/att - 3.0)  * 0.25,       0, 2.375)
    #   c = clamp((td_pct)          * 20,        0, 2.375)
    #   d = clamp(2.375 - (int_pct * 25),        0, 2.375)
    #   rating = (a + b + c + d) / 6 * 100
    comp_pct = df["completions_allowed"].astype(float) / targets
    ypa = df["yards_allowed"] / targets
    td_pct = df["tds_allowed"].astype(float) / targets
    int_pct = df["ints"].astype(float) / targets
    a = ((comp_pct - 0.30) * 5).clip(lower=0.0, upper=2.375)
    b = ((ypa - 3.0) * 0.25).clip(lower=0.0, upper=2.375)
    c = (td_pct * 20).clip(lower=0.0, upper=2.375)
    d = (2.375 - int_pct * 25).clip(lower=0.0, upper=2.375)
    df["passer_rating_allowed"] = ((a + b + c + d) / 6.0 * 100.0).astype(float)

    tackle_att = (df["comb_tackles"] + df["missed_tackles"].fillna(0)).clip(lower=1)
    df["missed_tackle_rate"] = df["missed_tackles"].fillna(0.0) / tackle_att
    df["tackle_attempts"] = (df["comb_tackles"] + df["missed_tackles"].fillna(0)).astype(int)

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    df["qualified"] = df["snaps_defense"] >= LB_V1_QUALIFIED_MIN_SNAPS
    df["confidence"] = (
        df["snaps_defense"].astype(float) / LB_V1_CONFIDENCE_FULL_SNAPS
    ).clip(upper=1.0)

    data_tier, data_tier_reason = _era_tier_for_season(season)
    df["data_tier"] = data_tier
    df["data_tier_reason"] = data_tier_reason

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in LB_V1_RAW_VALUE_COLS.items():
        n_col = LB_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = LB_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, LB_V1_WEIGHTS)
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
      AND component_name LIKE 'lb_%'
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
    components = list(LB_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = LB_V1_SAMPLE_SIZE_COLS[component]
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
                "sample_size":    int(r[n_col]),
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
            "player_id":       int(r["player_id"]),
            "season":          season,
            "position":        POSITION,
            "composite_grade": float(r["grade"]),
            "composite_z":     float(r["composite_z"]),
            "percentile":      float(r["percentile"]) if not pd.isna(r["percentile"]) else 50.0,
            "confidence":      float(r["confidence"]),
            "data_tier":       int(r["data_tier"]),
            "qualified":       bool(r["qualified"]),
            "role":            None,
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
