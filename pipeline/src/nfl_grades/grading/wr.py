"""WR v1 grading pipeline (ADR-0015).

Flow mirrors QB v1 and RB v1:
    1. ``extract_features``: one SQL against ``plays`` (receiving +
       team pass aggregates + YAC-over-expected CTEs) joined to
       ``ngs_receiving`` season-summary rows (week=0) for separation.
       NGS receiving publishes WR rows cleanly (unlike RBs), so we
       can pull `avg_separation` straight from it.
    2. ``compute_grades``: pure-python —
         shrink → z-score →
         composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Public entry point: ``run(season)``.

Design notes:

- Target earn rate's denominator is "team pass attempts in games
  the WR had at least one target". This proxies "active games"
  without needing snap-count data, and it naturally handles mid-
  season trades (each game's pass-attempt aggregate is counted
  under its correct posteam).
- Fumble rate's denominator is receptions, not targets — WRs only
  touch the ball on completions. This keeps the rate comparable
  across possession WRs (high catch rate) and deep threats (lower
  catch rate). Same filter shape (REG, non-garbage, non-2pt) as
  the production metrics.
- YAC-over-expected is derived from ``plays.xyac_mean_yardage``
  (same pattern as RB v1.1), not from NGS. Keeps the two positions
  comparable and gives us coverage on every completion in the
  modern era.
- Separation comes from NGS. For WRs traded mid-season, NGS
  publishes one row per team stint (week=0 per team); we volume-
  weight by the `targets` column in each NGS row.
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
from nfl_grades.grading.filters import RB_REC_FILTER_SQL
from nfl_grades.grading.progress import COMPLETE, SeasonProgress
from nfl_grades.grading.weights import (
    WR_V1_CONFIDENCE_FULL_TARGETS,
    WR_V1_MIN_TARGETS_TO_GRADE,
    WR_V1_QUALIFIED_MIN_TARGETS,
    WR_V1_RAW_VALUE_COLS,
    WR_V1_SAMPLE_SIZE_COLS,
    WR_V1_SHRINKAGE_K,
    WR_V1_WEIGHTS,
)

logger = logging.getLogger(__name__)

POSITION = "WR"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_wrs_total: int
    n_wrs_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int, *, conn: Connection | None = None) -> RunResult:
    """Run the full WR v1 grading pipeline for one season.

    Idempotent: re-writes all stat_components and season_grades rows
    that belong to (season, position='WR').
    """
    with pipeline_run("grading:wr", season=season) as handle:
        with transaction(conn) as conn:
            season_progress = progress.load(conn, season)
            features = extract_features(conn, season, season_progress)
            if features.empty:
                logger.warning("no WR targets found for season %d", season)
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
            n_wrs_total=len(graded),
            n_wrs_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(f"wrs_total={result.n_wrs_total} wrs_qualified={result.n_wrs_qualified}")
    return result


# ---------------------------------------------------------------------------
# 1. Extract features from plays + NGS receiving
# ---------------------------------------------------------------------------
#
# CTEs:
#   - wrs            : the WR master list (position='WR')
#   - rec_agg        : per-WR receiving production (targets, receptions,
#                      EPA/target, success rate, fumble count)
#   - rec_yac_agg    : YAC-over-expected per reception from plays.xyac_mean_yardage
#   - wr_games_agg   : (player, posteam, game_id) pairs where the WR had a target
#                      — the "active games" proxy used for the earn-rate denominator
#   - team_pass_agg  : team pass attempts per (posteam, game_id) under the
#                      same REG/non-garbage/non-2pt filter as the numerator
#   - earn_rate_agg  : per-WR sum of team_pass_agg over wr_games_agg
#   - ngs_sep_agg    : per-WR separation, volume-weighted by NGS targets when
#                      a WR has multiple NGS rows (traded mid-season)

_FEATURES_SQL = text(f"""
    WITH wrs AS (
        SELECT player_id, full_name, gsis_id
        FROM players
        WHERE position = 'WR' AND gsis_id IS NOT NULL
    ),
    rec_agg AS (
        SELECT
            w.player_id,
            w.full_name,
            w.gsis_id,
            COUNT(*) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS n_targets,
            COUNT(*) FILTER (
                WHERE pl.receiver_player_id IS NOT NULL AND pl.complete_pass
            ) AS n_receptions,
            AVG(pl.epa) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS rec_epa_per_target,
            AVG(pl.success::int) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS success_rate_per_target
        FROM wrs w
        LEFT JOIN plays pl
          ON pl.receiver_player_id = w.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY w.player_id, w.full_name, w.gsis_id
    ),
    rec_yac_agg AS (
        SELECT
            w.player_id,
            COUNT(*) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS n_rec_with_xyac,
            AVG(pl.yards_after_catch - pl.xyac_mean_yardage) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS yac_over_expected_per_rec
        FROM wrs w
        LEFT JOIN plays pl
          ON pl.receiver_player_id = w.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY w.player_id
    ),
    wr_games_agg AS (
        -- Distinct (WR, posteam, game_id) triples where the WR had
        -- >=1 target. Target plays only — so a WR who played but
        -- wasn't targeted in some games isn't counted as "active"
        -- for those games. For qualified WRs this edge case is rare.
        SELECT DISTINCT
            w.player_id,
            pl.posteam,
            pl.game_id
        FROM wrs w
        JOIN plays pl
          ON pl.receiver_player_id = w.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
    ),
    team_pass_agg AS (
        -- Regular-season pass attempts per (posteam, game_id) under
        -- the SAME filter as the numerator. This keeps earn rate's
        -- numerator and denominator on the same scale — e.g., garbage-
        -- time attempts are excluded from both.
        SELECT
            pl.posteam,
            pl.game_id,
            COUNT(*) AS n_team_pass_att
        FROM plays pl
        WHERE pl.season = :season
          AND ({RB_REC_FILTER_SQL})
        GROUP BY pl.posteam, pl.game_id
    ),
    earn_rate_agg AS (
        SELECT
            g.player_id,
            SUM(t.n_team_pass_att) AS n_team_pass_att_active
        FROM wr_games_agg g
        JOIN team_pass_agg t USING (posteam, game_id)
        GROUP BY g.player_id
    ),
    ngs_sep_agg AS (
        -- Aggregate from weekly rows (week > 0) rather than the week=0 season
        -- summary so players who nflverse never publishes a summary row for
        -- (e.g. low-target TEs/WRs in some seasons) still get separation data.
        -- SUM(targets * avg_separation) / SUM(targets) is the same
        -- volume-weighted average either way.
        SELECT
            player_id,
            SUM(targets) AS ngs_targets,
            SUM(avg_separation * targets) AS ngs_separation_times_targets
        FROM ngs_receiving
        WHERE season = :season AND season_type = 'REG' AND week > 0
        GROUP BY player_id
    )
    SELECT
        rec_agg.player_id,
        rec_agg.gsis_id,
        rec_agg.full_name,
        rec_agg.n_targets,
        rec_agg.n_receptions,
        COALESCE(rec_yac_agg.n_rec_with_xyac, 0)     AS n_rec_with_xyac,
        COALESCE(earn_rate_agg.n_team_pass_att_active, 0)
                                                     AS n_team_pass_att_active,
        COALESCE(ftn.catchable_balls, 0)             AS n_catchable_balls,
        ftn.drops                                    AS n_drops,
        rec_agg.rec_epa_per_target,
        rec_agg.success_rate_per_target,
        rec_yac_agg.yac_over_expected_per_rec,
        CASE WHEN ngs_sep_agg.ngs_targets > 0 THEN
            ngs_sep_agg.ngs_separation_times_targets::float
                / ngs_sep_agg.ngs_targets
        END AS separation,
        CASE WHEN COALESCE(earn_rate_agg.n_team_pass_att_active, 0) > 0 THEN
            rec_agg.n_targets::float
                / earn_rate_agg.n_team_pass_att_active
        END AS target_earn_rate,
        CASE WHEN ftn.catchable_balls > 0 THEN
            ftn.drops::float / ftn.catchable_balls
        END AS drop_rate
    FROM rec_agg
    LEFT JOIN rec_yac_agg USING (player_id)
    LEFT JOIN earn_rate_agg USING (player_id)
    LEFT JOIN ngs_sep_agg USING (player_id)
    LEFT JOIN ftn_receiving_charting ftn
        ON ftn.player_id = rec_agg.player_id AND ftn.season = :season
    WHERE rec_agg.n_targets >= :min_targets
""")


def extract_features(
    conn: Connection, season: int, progress: SeasonProgress = COMPLETE
) -> pd.DataFrame:
    """Pull per-WR raw components from plays + NGS receiving.

    Returns a DataFrame with one row per WR who reached
    ``WR_V1_MIN_TARGETS_TO_GRADE`` targets. Columns:

        player_id, gsis_id, full_name,
        n_targets, n_receptions, n_rec_with_xyac,
        n_team_pass_att_active, n_catchable_balls, n_drops,
        rec_epa_per_target, success_rate_per_target,
        yac_over_expected_per_rec, separation,
        target_earn_rate, drop_rate
    """
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_targets": progress.scale(WR_V1_MIN_TARGETS_TO_GRADE)},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Decimal -> float for numpy math.
    float_cols = (
        "rec_epa_per_target",
        "success_rate_per_target",
        "yac_over_expected_per_rec",
        "separation",
        "target_earn_rate",
        "drop_rate",
    )
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("Float64").astype(float)

    int_cols = (
        "n_targets",
        "n_receptions",
        "n_rec_with_xyac",
        "n_team_pass_att_active",
        "n_catchable_balls",
        "n_drops",
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
    ``percentile``, ``qualified``, and ``confidence``.
    """
    df = features.copy()

    # --- qualification + confidence ---
    df["qualified"] = df["n_targets"] >= progress.scale(WR_V1_QUALIFIED_MIN_TARGETS)
    df["confidence"] = (
        df["n_targets"].astype(float) / progress.scale(WR_V1_CONFIDENCE_FULL_TARGETS)
    ).clip(upper=1.0)

    # --- per-component: shrink + z-score ---
    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in WR_V1_RAW_VALUE_COLS.items():
        n_col = WR_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = WR_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk  # v1: no opp-adj, adjusted == shrunk
        df[f"z_{component}"] = z

        # A NaN z-score (missing NGS separation, zero-target degenerate
        # cases) drops out of the composite and the remaining weights are
        # renormalized (ADR-0028). The true NaN is kept in
        # stat_components.z_score so the UI renders "-" instead of "0.0".
        z_frame[component] = z

    return df.assign(
        **scoring.score(z_frame, WR_V1_WEIGHTS, df["qualified"], composite_sd=composite_sd)
    )


# ---------------------------------------------------------------------------
# 3. Write to stat_components + season_grades
# ---------------------------------------------------------------------------


_DELETE_STAT_COMPONENTS = text("""
    DELETE FROM stat_components
    WHERE season = :season
      AND component_name LIKE 'wr_%'
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
    components = list(WR_V1_RAW_VALUE_COLS.keys())
    era_tier, era_reason = _era_tier_for_season(season)

    # --- stat_components (wide -> long) ---
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = WR_V1_SAMPLE_SIZE_COLS[component]
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


__all__ = [
    "POSITION",
    "RunResult",
    "compute_grades",
    "extract_features",
    "run",
    "write_results",
]
