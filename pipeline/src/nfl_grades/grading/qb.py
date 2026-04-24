"""QB v1 grading pipeline (ADR-0013).

Flow:
    1. ``extract_features``: SQL against ``plays`` to get per-player raw
       aggregates (EPA/db, CPOE, success rate) + sample sizes.
    2. ``compute_grades``: pure-python pipeline —
         shrink → z-score → composite → sigmoid → percentile rank.
    3. ``write_results``: upsert stat_components + season_grades rows.

Public entry point: ``run(season)``.
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
from nfl_grades.grading.filters import QB_DROPBACK_FILTER_SQL
from nfl_grades.grading.weights import (
    QB_V1_CONFIDENCE_FULL_DROPBACKS,
    QB_V1_QUALIFIED_MIN_DROPBACKS,
    QB_V1_SHRINKAGE_K,
    QB_V1_WEIGHTS,
)

logger = logging.getLogger(__name__)

POSITION = "QB"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_qbs_total: int
    n_qbs_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    """Run the full QB v1 grading pipeline for one season.

    Idempotent: re-writes all stat_components and season_grades rows
    that belong to (season, position='QB').
    """
    engine = get_engine()
    with pipeline_run("grading:qb", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no QB dropbacks found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features)

            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_qbs_total=len(graded),
            n_qbs_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(f"qbs_total={result.n_qbs_total} qbs_qualified={result.n_qbs_qualified}")
    return result


# ---------------------------------------------------------------------------
# 1. Extract features from plays
# ---------------------------------------------------------------------------

# Filter ``players.position = 'QB'`` so non-QB passers (WRs/RBs throwing
# trick-play passes, emergency wildcat snaps, etc.) don't end up graded
# as quarterbacks. Without this, the home-page "low-volume passers"
# section fills up with single-dropback gadget throwers.

_FEATURES_SQL = text(f"""
    SELECT
        pl.passer_player_id                      AS gsis_id,
        p.player_id                              AS player_id,
        p.full_name                              AS full_name,
        COUNT(*)                                 AS n_dropbacks,
        COUNT(*) FILTER (WHERE pl.pass_attempt AND pl.cpoe IS NOT NULL) AS n_pass_attempts,
        AVG(pl.epa)                              AS epa_per_dropback,
        AVG(pl.cpoe) FILTER (WHERE pl.pass_attempt AND pl.cpoe IS NOT NULL) AS cpoe,
        AVG(pl.success::int)                     AS success_rate
    FROM plays pl
    JOIN players p ON p.gsis_id = pl.passer_player_id
    WHERE pl.season = :season
      AND p.position = 'QB'
      AND {QB_DROPBACK_FILTER_SQL}
    GROUP BY pl.passer_player_id, p.player_id, p.full_name
    HAVING COUNT(*) >= 1
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    """Pull per-QB raw components from ``plays``.

    Returns a DataFrame with columns:
        player_id, gsis_id, full_name,
        n_dropbacks, n_pass_attempts,
        epa_per_dropback, cpoe, success_rate
    """
    rows = conn.execute(_FEATURES_SQL, {"season": season}).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Cast the decimal-typed aggregates to plain floats so numpy math works.
    for col in ("epa_per_dropback", "cpoe", "success_rate"):
        df[col] = df[col].astype(float)
    for col in ("n_dropbacks", "n_pass_attempts"):
        df[col] = df[col].astype(int)
    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------


# Map (component_name -> (raw_value_col, sample_size_col)).
_COMPONENT_SPECS: dict[str, tuple[str, str]] = {
    "qb_epa_per_dropback": ("epa_per_dropback", "n_dropbacks"),
    "qb_cpoe": ("cpoe", "n_pass_attempts"),
    "qb_success_rate": ("success_rate", "n_dropbacks"),
}


def compute_grades(features: pd.DataFrame) -> pd.DataFrame:
    """Apply shrinkage, z-score, composite, sigmoid, percentile rank.

    Input:  one row per player, columns per ``extract_features``.
    Output: same rows plus columns:
        - raw_<component>, adjusted_<component>, z_<component>
        - composite_z, grade, percentile
        - qualified, confidence
    """
    df = features.copy()
    df["qualified"] = df["n_dropbacks"] >= QB_V1_QUALIFIED_MIN_DROPBACKS
    df["confidence"] = (df["n_dropbacks"].astype(float) / QB_V1_CONFIDENCE_FULL_DROPBACKS).clip(
        upper=1.0
    )

    # --- per-component: shrink + z-score ---
    z_frame = pd.DataFrame(index=df.index)
    for component, (raw_col, n_col) in _COMPONENT_SPECS.items():
        raw = df[raw_col]
        n = df[n_col]
        k = QB_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk  # v1 has no opp adjustment so adjusted == shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z

    # --- composite + sigmoid ---
    df["composite_z"] = composite.combine(z_frame, QB_V1_WEIGHTS)
    df["grade"] = sigmoid.to_grade(df["composite_z"].to_numpy())

    # --- percentile within this position+season, qualified-only ranking
    #     but all rows receive a percentile (based on their grade vs the
    #     qualified distribution). Unqualified QBs get their percentile
    #     against the qualified cohort too — "if you played starter
    #     reps, here's where you'd stack."
    qualified_grades = df.loc[df["qualified"], "grade"].sort_values().to_numpy()
    if len(qualified_grades) >= 2:
        df["percentile"] = df["grade"].apply(
            lambda g: (
                100.0 * np.searchsorted(qualified_grades, g, side="right") / len(qualified_grades)
            )
        )
    else:
        df["percentile"] = 50.0
    df.loc[df["grade"].isna(), "percentile"] = np.nan

    return df


# ---------------------------------------------------------------------------
# 3. Write to stat_components + season_grades
# ---------------------------------------------------------------------------


_DELETE_STAT_COMPONENTS = text("""
    DELETE FROM stat_components
    WHERE season = :season
      AND component_name = ANY(:components)
""")

_DELETE_SEASON_GRADES = text("""
    DELETE FROM season_grades
    WHERE season = :season AND position = :position
""")

_INSERT_STAT_COMPONENTS = text("""
    INSERT INTO stat_components
        (player_id, season, component_name, raw_value, adjusted_value, z_score, sample_size,
         used_in_composite)
    VALUES
        (:player_id, :season, :component_name, :raw_value, :adjusted_value, :z_score, :sample_size,
         :used_in_composite)
""")

_INSERT_SEASON_GRADES = text("""
    INSERT INTO season_grades
        (player_id, season, position, composite_grade, composite_z,
         percentile, confidence, data_tier, qualified, role, data_tier_reason)
    VALUES
        (:player_id, :season, :position, :composite_grade, :composite_z,
         :percentile, :confidence, :data_tier, :qualified, :role, :data_tier_reason)
""")


def write_results(conn: Connection, graded: pd.DataFrame, season: int) -> tuple[int, int]:
    """Upsert stat_components + season_grades. Returns (n_components, n_grades)."""
    components = list(_COMPONENT_SPECS.keys())
    era_tier, era_reason = _era_tier_for_season(season)

    # --- stat_components rows (wide -> long) ---
    component_rows: list[dict[str, object]] = []
    for component, (_raw_col, n_col) in _COMPONENT_SPECS.items():
        for _, r in graded.iterrows():
            raw = r[f"raw_{component}"]
            adj = r[f"adjusted_{component}"]
            z = r[f"z_{component}"]
            component_rows.append(
                {
                    "player_id": int(r["player_id"]),
                    "season": season,
                    "component_name": component,
                    "raw_value": None if pd.isna(raw) else float(raw),
                    "adjusted_value": None if pd.isna(adj) else float(adj),
                    "z_score": None if pd.isna(z) else float(z),
                    "sample_size": int(r[n_col]),
                    "used_in_composite": True,
                }
            )

    conn.execute(_DELETE_STAT_COMPONENTS, {"season": season, "components": components})
    if component_rows:
        conn.execute(_INSERT_STAT_COMPONENTS, component_rows)

    # --- season_grades rows ---
    grade_rows: list[dict[str, object]] = []
    for _, r in graded.iterrows():
        if pd.isna(r["grade"]):
            # A QB with insufficient data to compute any z-score wouldn't
            # land here (they'd lack pass attempts entirely), but guard
            # just in case.
            continue
        grade_rows.append(
            {
                "player_id": int(r["player_id"]),
                "season": season,
                "position": POSITION,
                "composite_grade": float(r["grade"]),
                "composite_z": float(r["composite_z"]),
                "percentile": float(r["percentile"]) if not pd.isna(r["percentile"]) else 50.0,
                "confidence": float(r["confidence"]),
                "data_tier": era_tier,
                "qualified": bool(r["qualified"]),
                "role": None,
                "data_tier_reason": era_reason,
            }
        )

    conn.execute(_DELETE_SEASON_GRADES, {"season": season, "position": POSITION})
    if grade_rows:
        conn.execute(_INSERT_SEASON_GRADES, grade_rows)

    return len(component_rows), len(grade_rows)
