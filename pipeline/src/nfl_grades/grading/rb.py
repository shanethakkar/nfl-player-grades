"""RB v1 grading pipeline (ADR-0014).

Flow mirrors QB v1:
    1. ``extract_features``: one SQL against ``plays`` (rushing + receiving
       CTEs) joined to ``ngs_rushing`` season-summary rows (week=0).
       NGS receiving is not used — nflverse's receiving NGS product only
       publishes WR/TE rows, so we derive YAC-over-expected from
       ``plays.xyac_mean_yardage`` (nflfastR's xYAC model) directly.
       Catch % is likewise computed from ``plays``.
    2. ``compute_grades``: pure-python —
         shrink → z-score →
         composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Public entry point: ``run(season)``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import pipeline_run, transaction
from nfl_grades.grading import empirical_bayes, preview, progress, scoring, zscore
from nfl_grades.grading.era_tier import _era_tier_for_season
from nfl_grades.grading.filters import RB_REC_FILTER_SQL, RB_RUSH_FILTER_SQL
from nfl_grades.grading.progress import COMPLETE, SeasonProgress
from nfl_grades.grading.weights import (
    RB_V1_CONFIDENCE_FULL_TOUCHES,
    RB_V1_MIN_TOUCHES_TO_GRADE,
    RB_V1_QUALIFIED_MIN_TOUCHES,
    RB_V1_RAW_VALUE_COLS,
    RB_V1_RECEIVING_SUB_MIN_TARGETS,
    RB_V1_RUSHING_SUB_MIN_CARRIES,
    RB_V1_SAMPLE_SIZE_COLS,
    RB_V1_SHRINKAGE_K,
    RB_V1_WEIGHTS,
)

logger = logging.getLogger(__name__)

POSITION = "RB"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_rbs_total: int
    n_rbs_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int, *, conn: Connection | None = None) -> RunResult:
    """Run the full RB v1 grading pipeline for one season.

    Idempotent: re-writes all stat_components and season_grades rows
    that belong to (season, position='RB').
    """
    with pipeline_run("grading:rb", season=season) as handle:
        with transaction(conn) as conn:
            season_progress = progress.load(conn, season)
            features = extract_features(conn, season, season_progress)
            if features.empty:
                logger.warning("no RB touches found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(
                features,
                progress=season_progress,
                composite_sd=preview.composite_sd_for(conn, POSITION, season_progress),
            )

            n_components, n_grades = write_results(
                conn, graded, season, through_week=season_progress.through_week
            )

        result = RunResult(
            season=season,
            n_rbs_total=len(graded),
            n_rbs_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(f"rbs_total={result.n_rbs_total} rbs_qualified={result.n_rbs_qualified}")
    return result


# ---------------------------------------------------------------------------
# 1. Extract features from plays + NGS rushing
# ---------------------------------------------------------------------------
#
# Design notes:
#
# - `rush_agg`, `rec_agg`, and `rec_yac_agg` CTEs LEFT JOIN plays to the
#   RB master list, so every RB with position='RB' gets a row even if
#   they had 0 rushes / 0 targets / 0 measured completions. Counts come
#   through as 0 rather than NULL (pandas then treats them as int).
# - NGS rushing season-summary rows use week=0. For players traded
#   mid-season this can produce multiple rows (one per team stint), so
#   we SUM the count columns and volume-weight the rate columns.
# - Fumble rate uses `fumble` (any fumble by the ball carrier, not just
#   ones recovered by the defense). See ADR-0014 v1.1 refinement.
#   Counted on both rushing and receiving plays because RBs can fumble
#   on either.
# - YAC-over-expected uses nflfastR's `xyac_mean_yardage` (plays) rather
#   than NGS, because NGS receiving doesn't publish RB rows. See
#   ADR-0014 v1.1 refinement.


_FEATURES_SQL = text(f"""
    WITH rbs AS (
        SELECT player_id, full_name, gsis_id
        FROM players
        WHERE position = 'RB' AND gsis_id IS NOT NULL
    ),
    rush_agg AS (
        SELECT
            r.player_id,
            r.full_name,
            r.gsis_id,
            COUNT(*) FILTER (WHERE pl.rusher_player_id IS NOT NULL)
                AS n_carries,
            AVG(pl.epa) FILTER (WHERE pl.rusher_player_id IS NOT NULL)
                AS rush_epa_per_attempt,
            AVG(pl.success::int) FILTER (WHERE pl.rusher_player_id IS NOT NULL)
                AS rush_success_rate,
            COUNT(*) FILTER (
                WHERE pl.rusher_player_id IS NOT NULL AND pl.fumble
            ) AS n_rush_fumbles
        FROM rbs r
        LEFT JOIN plays pl
          ON pl.rusher_player_id = r.gsis_id
         AND pl.season = :season
         AND ({RB_RUSH_FILTER_SQL})
        GROUP BY r.player_id, r.full_name, r.gsis_id
    ),
    rec_agg AS (
        SELECT
            r.player_id,
            COUNT(*) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS n_targets,
            COUNT(*) FILTER (
                WHERE pl.receiver_player_id IS NOT NULL AND pl.complete_pass
            ) AS n_receptions,
            AVG(pl.epa) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS rec_epa_per_target,
            COUNT(*) FILTER (
                WHERE pl.receiver_player_id IS NOT NULL AND pl.fumble
            ) AS n_rec_fumbles
        FROM rbs r
        LEFT JOIN plays pl
          ON pl.receiver_player_id = r.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY r.player_id
    ),
    rec_yac_agg AS (
        -- YAC-over-expected derived directly from plays, using nflfastR's
        -- xyac_mean_yardage model output. This replaces the NGS receiving
        -- path (which publishes 0 RB rows). Sample size = receptions
        -- where the xYAC model produced a prediction (>99% of RB
        -- completions in the modern era).
        SELECT
            r.player_id,
            COUNT(*) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS n_rec_with_xyac,
            AVG(pl.yards_after_catch - pl.xyac_mean_yardage) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS yac_over_expected_per_rec
        FROM rbs r
        LEFT JOIN plays pl
          ON pl.receiver_player_id = r.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY r.player_id
    ),
    ngs_rush_agg AS (
        -- Volume-weight across team stints: rate = SUM(total) / SUM(attempts).
        SELECT
            player_id,
            SUM(rush_attempts)               AS ngs_rush_attempts,
            SUM(rush_yards_over_expected)    AS ngs_ryoe_total
        FROM ngs_rushing
        WHERE season = :season AND season_type = 'REG' AND week = 0
        GROUP BY player_id
    ),
    pfr_rush_agg AS (
        -- PFR rush advanced stats (2018+). Stores season totals; we derive
        -- yards_after_contact_per_carry from the per-row carries denominator
        -- (which may differ slightly from rush_agg.n_carries due to PFR/PBP
        -- coverage differences — use PFR's own carries for the rate). Pre-
        -- 2018 LEFT JOIN returns NULL → component drops out of the composite.
        SELECT player_id,
               carries AS pfr_carries,
               yards_after_contact
        FROM pfr_rb_rush
        WHERE season = :season
    )
    SELECT
        rush_agg.player_id,
        rush_agg.gsis_id,
        rush_agg.full_name,
        rush_agg.n_carries,
        rec_agg.n_targets,
        rec_agg.n_receptions,
        rec_yac_agg.n_rec_with_xyac,
        COALESCE(pfr_rush_agg.pfr_carries, 0) AS n_pfr_carries,
        (rush_agg.n_carries + rec_agg.n_receptions) AS n_touches,
        (rush_agg.n_rush_fumbles + rec_agg.n_rec_fumbles)
            AS n_fumbles,
        rush_agg.rush_epa_per_attempt,
        rush_agg.rush_success_rate,
        rec_agg.rec_epa_per_target,
        CASE WHEN ngs_rush_agg.ngs_rush_attempts > 0 THEN
            ngs_rush_agg.ngs_ryoe_total::float / ngs_rush_agg.ngs_rush_attempts
        END AS ryoe_per_attempt,
        rec_yac_agg.yac_over_expected_per_rec,
        CASE WHEN pfr_rush_agg.pfr_carries > 0 THEN
            pfr_rush_agg.yards_after_contact::float / pfr_rush_agg.pfr_carries
        END AS yards_after_contact_per_carry,
        CASE WHEN (rush_agg.n_carries + rec_agg.n_receptions) > 0 THEN
            (rush_agg.n_rush_fumbles + rec_agg.n_rec_fumbles)::float
                / (rush_agg.n_carries + rec_agg.n_receptions)
        END AS fumble_rate
    FROM rush_agg
    JOIN rec_agg USING (player_id)
    LEFT JOIN rec_yac_agg USING (player_id)
    LEFT JOIN ngs_rush_agg USING (player_id)
    LEFT JOIN pfr_rush_agg USING (player_id)
    WHERE (rush_agg.n_carries + rec_agg.n_receptions) >= :min_touches
""")


def extract_features(
    conn: Connection, season: int, progress: SeasonProgress = COMPLETE
) -> pd.DataFrame:
    """Pull per-RB raw components from plays + NGS rushing.

    Returns a DataFrame with one row per RB who reached
    ``RB_V1_MIN_TOUCHES_TO_GRADE`` touches. Columns:

        player_id, gsis_id, full_name,
        n_carries, n_targets, n_receptions, n_rec_with_xyac,
        n_touches, n_fumbles,
        rush_epa_per_attempt, rush_success_rate, rec_epa_per_target,
        ryoe_per_attempt, yac_over_expected_per_rec,
        fumble_rate
    """
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_touches": progress.scale(RB_V1_MIN_TOUCHES_TO_GRADE)},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Cast numeric aggregates to float for numpy math. Decimals from
    # Postgres come back as Python Decimal otherwise.
    float_cols = (
        "rush_epa_per_attempt",
        "rush_success_rate",
        "rec_epa_per_attempt",
        "rec_epa_per_target",
        "ryoe_per_attempt",
        "yac_over_expected_per_rec",
        "yards_after_contact_per_carry",
        "fumble_rate",
    )
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("Float64").astype(float)

    int_cols = (
        "n_carries",
        "n_targets",
        "n_receptions",
        "n_rec_with_xyac",
        "n_pfr_carries",
        "n_touches",
        "n_fumbles",
    )
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)
    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------


def compute_grades(
    features: pd.DataFrame,
    *,
    progress: SeasonProgress = COMPLETE,
    composite_sd: float | None = None,
) -> pd.DataFrame:
    """Apply shrinkage → z-score → composite → sigmoid.

    Returns the input DataFrame augmented with per-component
    ``raw_*``/``adjusted_*``/``z_*`` columns, ``composite_z``, ``grade``,
    ``percentile``, ``qualified``, ``confidence``, and the two sub-grade
    qualification flags (``rushing_sub_qualified``,
    ``receiving_sub_qualified``).
    """
    df = features.copy()

    # --- qualification flags ---
    df["qualified"] = df["n_touches"] >= progress.scale(RB_V1_QUALIFIED_MIN_TOUCHES)
    df["rushing_sub_qualified"] = df["n_carries"] >= progress.scale(RB_V1_RUSHING_SUB_MIN_CARRIES)
    df["receiving_sub_qualified"] = df["n_targets"] >= progress.scale(
        RB_V1_RECEIVING_SUB_MIN_TARGETS
    )
    df["confidence"] = (
        df["n_touches"].astype(float) / progress.scale(RB_V1_CONFIDENCE_FULL_TOUCHES)
    ).clip(upper=1.0)

    # --- per-component: shrink + z-score ---
    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in RB_V1_RAW_VALUE_COLS.items():
        n_col = RB_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = RB_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk  # v1: no opp-adj, so adjusted == shrunk
        df[f"z_{component}"] = z

        # A NaN z-score (n=0, missing NGS row, undefined raw metric) drops
        # out of the composite and the remaining weights are renormalized
        # (ADR-0028), so every RB with any Component has a composite.
        z_frame[component] = z

    return df.assign(
        **scoring.score(z_frame, RB_V1_WEIGHTS, df["qualified"], composite_sd=composite_sd)
    )


# ---------------------------------------------------------------------------
# 3. Write to stat_components + season_grades
# ---------------------------------------------------------------------------


_DELETE_STAT_COMPONENTS = text("""
    DELETE FROM stat_components
    WHERE season = :season
      AND component_name LIKE 'rb_%'
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
         percentile, confidence, data_tier, qualified, role, data_tier_reason,
         through_week)
    VALUES
        (:player_id, :season, :position, :composite_grade, :composite_z,
         :percentile, :confidence, :data_tier, :qualified, :role, :data_tier_reason,
         :through_week)
""")


def write_results(
    conn: Connection, graded: pd.DataFrame, season: int, *, through_week: int | None = None
) -> tuple[int, int]:
    """Upsert stat_components + season_grades. Returns (n_components, n_grades)."""
    components = list(RB_V1_RAW_VALUE_COLS.keys())
    era_tier, era_reason = _era_tier_for_season(season)

    # --- stat_components (wide -> long) ---
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = RB_V1_SAMPLE_SIZE_COLS[component]
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
            # No Component z-scores at all: nothing to grade.
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
                "through_week": through_week,
            }
        )

    conn.execute(_DELETE_SEASON_GRADES, {"season": season, "position": POSITION})
    if grade_rows:
        conn.execute(_INSERT_SEASON_GRADES, grade_rows)

    return len(component_rows), len(grade_rows)


# Re-used from this module's tests; keep the tuple unambiguous.
__all__ = [
    "POSITION",
    "RunResult",
    "compute_grades",
    "extract_features",
    "run",
    "write_results",
]
