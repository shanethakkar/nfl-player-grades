"""CB v1 grading pipeline (ADR-0018).

Flow:
    1. ``extract_features``: reads ``pfr_def_coverage`` (ingested by
       ``ingest/pfr.py``) and computes per-rate metrics from raw counts.
       No play-by-play join needed — PFR publishes season-level totals.
    2. ``compute_grades``: pure-python —
         shrink → z-score → NaN neutralization →
         composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Public entry point: ``run(season)``.

Design notes:

- Data source: PFR advanced defensive stats (``pfr_def_coverage``).
  PBP was considered but discarded because PBP doesn't record the
  covering CB on completed passes — only interceptions and PBUs have
  a defender ID. PFR is the only free, season-level, player-level source
  with full coverage metrics.

- Data available from 2018. Earlier seasons return empty results with a
  warning logged. The era tier from ``_era_tier_for_season`` still applies
  for seasons ≥ 2016 (tier 1), so no special tier is needed.

- YAC component: PFR publishes per-CB YAC allowed for most seasons. If
  missing (``yac IS NULL``), the z-score is NaN and is neutralized to 0.0
  in the composite (standard NaN handling per ADR-0015).

- Role classification: outside_cb / slot_cb / hybrid_cb from slot_pct.
  Role is label-only — z-scores are computed against the full CB pool,
  not within role cohorts. With ~30-60 qualified CBs per season, splitting
  further would make z-scores unstable.

- Qualification: 25 targets to appear, 30 to be qualified (full
  percentile-pool member), confidence reaches 1.0 at 60 targets.
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
    CB_ROLE_HYBRID,
    CB_ROLE_OUTSIDE,
    CB_ROLE_SLOT,
    CB_V1_CONFIDENCE_FULL_TARGETS,
    CB_V1_MIN_TARGETS_TO_GRADE,
    CB_V1_QUALIFIED_MIN_TARGETS,
    CB_V1_RAW_VALUE_COLS,    # comp%, YAC, TD rate, INT rate, PBU rate
    CB_V1_SAMPLE_SIZE_COLS,
    CB_V1_SHRINKAGE_K,
    CB_V1_SLOT_HI,
    CB_V1_SLOT_LO,
    CB_V1_WEIGHTS,
)
from nfl_grades.ingest.pfr import PFR_DEF_COVERAGE_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "CB"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_cbs_total: int
    n_cbs_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    """Run the full CB v1 grading pipeline for one season.

    Idempotent: re-writes all stat_components and season_grades rows
    that belong to (season, position='CB').

    Returns empty RunResult (all zeros) for seasons before
    PFR_DEF_COVERAGE_MIN_SEASON with a warning — no grades are written.
    """
    if season < PFR_DEF_COVERAGE_MIN_SEASON:
        logger.warning(
            "CB grading requires PFR coverage data (available from %d); "
            "season %d has no CB grades.",
            PFR_DEF_COVERAGE_MIN_SEASON,
            season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:cb", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no CB coverage data found in pfr_def_coverage for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_cbs_total=len(graded),
            n_cbs_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(f"cbs_total={result.n_cbs_total} cbs_qualified={result.n_cbs_qualified}")
    return result


# ---------------------------------------------------------------------------
# 1. Extract features from pfr_def_coverage
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        pdc.player_id,
        p.full_name,
        pdc.games,
        pdc.targets,
        pdc.completions,
        pdc.yards,
        pdc.yac,
        pdc.tds,
        pdc.ints,
        pdc.pass_breakups,
        pdc.slot_pct
    FROM pfr_def_coverage pdc
    JOIN players p ON p.player_id = pdc.player_id
    WHERE pdc.season = :season
      AND p.position = 'CB'
      AND pdc.targets >= :min_targets
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    """Pull per-CB raw coverage stats from pfr_def_coverage.

    Returns a DataFrame with one row per CB who reached
    ``CB_V1_MIN_TARGETS_TO_GRADE`` targets. Rate columns are derived
    from the raw count columns here (not in SQL) so we keep the math
    in Python where it's easier to test.

    Columns returned:
        player_id, full_name,
        games, targets, completions, yards, yac, tds, ints, pass_breakups,
        slot_pct,
        comp_pct_allowed, yac_per_rec_allowed, td_rate, pbu_rate, int_rate
    """
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_targets": CB_V1_MIN_TARGETS_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Coerce integer count columns.
    int_cols = ("games", "targets", "completions", "yards", "tds", "ints", "pass_breakups")
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    float_cols = ("yac", "slot_pct")
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("Float64").astype(float)

    # Derived rate columns from raw counts.
    # Each rate is None (→ NaN) when the denominator is zero.
    df["comp_pct_allowed"] = np.where(
        df["targets"] > 0,
        df["completions"] / df["targets"],
        np.nan,
    )

    # YAC per reception allowed: only defined when there are completions to
    # be the denominator. If yac column was never populated (all NaN), this
    # stays NaN and the component will be NaN-neutralized in compute_grades.
    df["yac_per_rec_allowed"] = np.where(
        (df["completions"] > 0) & df["yac"].notna(),
        df["yac"] / df["completions"],
        np.nan,
    )

    df["td_rate"] = np.where(
        df["targets"] > 0,
        df["tds"] / df["targets"],
        np.nan,
    )

    df["int_rate"] = np.where(
        df["targets"] > 0,
        df["ints"] / df["targets"],
        np.nan,
    )

    # PBU rate: NULL pass_breakups → NaN (treated as neutral in composite).
    df["pbu_rate"] = np.where(
        (df["targets"] > 0) & df["pass_breakups"].notna(),
        df["pass_breakups"] / df["targets"],
        np.nan,
    )

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------


def _classify_role(slot_pct: float | None) -> str | None:
    """Map slot_pct fraction to a CB role label, or None if unknown."""
    if slot_pct is None or not np.isfinite(slot_pct):
        return None
    if slot_pct < CB_V1_SLOT_LO:
        return CB_ROLE_OUTSIDE
    if slot_pct > CB_V1_SLOT_HI:
        return CB_ROLE_SLOT
    return CB_ROLE_HYBRID


def compute_grades(features: pd.DataFrame) -> pd.DataFrame:
    """Apply shrinkage → z-score → NaN neutralization → composite → sigmoid.

    Returns the input DataFrame augmented with:
        raw_*/adjusted_*/z_* columns per component,
        composite_z, grade, percentile, qualified, confidence, role.
    """
    df = features.copy()

    # --- qualification + confidence ---
    df["qualified"] = df["targets"] >= CB_V1_QUALIFIED_MIN_TARGETS
    df["confidence"] = (df["targets"].astype(float) / CB_V1_CONFIDENCE_FULL_TARGETS).clip(
        upper=1.0
    )

    # --- role classification (label-only; doesn't affect z-score pooling) ---
    df["role"] = df["slot_pct"].apply(_classify_role)

    # --- per-component: shrink + z-score ---
    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in CB_V1_RAW_VALUE_COLS.items():
        n_col = CB_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = CB_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z

        # NaN z-scores (missing YAC or degenerate edge cases) are replaced with
        # 0.0 (neutral) before entering the composite. The raw NaN is preserved
        # in stat_components.z_score so the UI renders "—" rather than "0.0".
        z_frame[component] = z.fillna(0.0)

    # --- composite + sigmoid ---
    df["composite_z"] = composite.combine(z_frame, CB_V1_WEIGHTS)
    df["grade"] = sigmoid.to_grade(df["composite_z"].to_numpy())

    # --- percentile against the qualified cohort ---
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
    components = list(CB_V1_RAW_VALUE_COLS.keys())
    era_tier, era_reason = _era_tier_for_season(season)

    # --- stat_components ---
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = CB_V1_SAMPLE_SIZE_COLS[component]
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

    # --- season_grades ---
    grade_rows: list[dict[str, object]] = []
    for _, r in graded.iterrows():
        if pd.isna(r["grade"]):
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
                "role": r["role"],
                "data_tier_reason": era_reason,
            }
        )

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
