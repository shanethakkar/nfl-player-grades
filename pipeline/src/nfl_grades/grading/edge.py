"""EDGE v1 grading pipeline (ADR-0020).

Flow:
    1. ``extract_features``: reads ``pfr_def_pass_rush`` (ingested by
       ``ingest/pfr_dl.py``) + ``player_seasons`` (for snaps_defense),
       filters to EDGE players, computes per-snap rate metrics in Python.
    2. ``compute_grades``: shrink → z-score → NaN neutralization →
       composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Data available from 2018. Earlier seasons return empty results.

Qualification is snap-based: 200 snaps to appear, 400 snaps qualified,
700 snaps full confidence.

NOTE: nflvs def_tackles_for_loss is reported separately from sacks
(confirmed: a player with 9 sacks had only 8 TFL, i.e. sacks are NOT
counted in TFL). No double-count risk between edge_sack_rate and
edge_tfl_rate.
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
    EDGE_COMPONENT_MISSED_TACKLE_RATE,
    EDGE_COMPONENT_PRESSURE_RATE,
    EDGE_COMPONENT_SACK_RATE,
    EDGE_COMPONENT_TFL_RATE,
    EDGE_V1_CONFIDENCE_FULL_SNAPS,
    EDGE_V1_MIN_SNAPS_TO_GRADE,
    EDGE_V1_QUALIFIED_MIN_SNAPS,
    EDGE_V1_RAW_VALUE_COLS,
    EDGE_V1_SAMPLE_SIZE_COLS,
    EDGE_V1_SHRINKAGE_K,
    EDGE_V1_WEIGHTS,
)
from nfl_grades.ingest.pfr_dl import PFR_DEF_PASS_RUSH_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "EDGE"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_edges_total: int
    n_edges_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    if season < PFR_DEF_PASS_RUSH_MIN_SEASON:
        logger.warning(
            "EDGE grading requires season >= %d; got %d — skipping",
            PFR_DEF_PASS_RUSH_MIN_SEASON, season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:edge", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no EDGE players found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_edges_total=len(graded),
            n_edges_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"edges_total={result.n_edges_total} "
            f"edges_qualified={result.n_edges_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        pr.player_id,
        p.full_name,
        p.gsis_id,
        COALESCE(ps.snaps_defense, 0)   AS snaps_defense,
        COALESCE(pr.pressures, 0)        AS pressures,
        COALESCE(pr.sacks, 0)            AS sacks,
        COALESCE(pr.comb_tackles, 0)     AS comb_tackles,
        pr.missed_tackles,
        pr.tfl
    FROM pfr_def_pass_rush pr
    JOIN players p ON p.player_id = pr.player_id
    LEFT JOIN (
        SELECT DISTINCT ON (player_id) player_id, snaps_defense, team_id, position_played
        FROM player_seasons
        WHERE season = :season
        ORDER BY player_id, snaps_defense DESC
    ) ps ON ps.player_id = pr.player_id
    WHERE pr.season = :season
      AND ps.position_played = 'EDGE'
      AND COALESCE(ps.snaps_defense, 0) >= :min_snaps
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_snaps": EDGE_V1_MIN_SNAPS_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = ("snaps_defense", "pressures", "comb_tackles")
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)

    float_cols = ("sacks", "missed_tackles", "tfl")
    for col in float_cols:
        df[col] = df[col].astype("Float64").astype(float)

    # Compute rate features.
    snaps = df["snaps_defense"].astype(float).clip(lower=1)
    df["pressure_rate"] = df["pressures"] / snaps
    df["sack_rate"] = df["sacks"] / snaps
    df["tfl_rate"] = df["tfl"].fillna(0.0) / snaps

    tackle_att = (df["comb_tackles"] + df["missed_tackles"].fillna(0)).clip(lower=1)
    df["missed_tackle_rate"] = df["missed_tackles"].fillna(0.0) / tackle_att
    df["tackle_attempts"] = (df["comb_tackles"] + df["missed_tackles"].fillna(0)).astype(int)

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    df["qualified"] = df["snaps_defense"] >= EDGE_V1_QUALIFIED_MIN_SNAPS
    df["confidence"] = (
        df["snaps_defense"].astype(float) / EDGE_V1_CONFIDENCE_FULL_SNAPS
    ).clip(upper=1.0)

    data_tier, data_tier_reason = _era_tier_for_season(season)
    df["data_tier"] = data_tier
    df["data_tier_reason"] = data_tier_reason

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in EDGE_V1_RAW_VALUE_COLS.items():
        n_col = EDGE_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = EDGE_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, EDGE_V1_WEIGHTS)
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
      AND component_name LIKE 'edge_%'
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
    components = list(EDGE_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = EDGE_V1_SAMPLE_SIZE_COLS[component]
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
