"""TE v1 grading pipeline (ADR-0016).

Structure matches WR v1, with TE role labels, per-role ``data_tier`` / ``data_tier_reason``,
and a blocking-TE composite that omits target earn (weight redistributed to EPA + YAC).
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
from nfl_grades.grading.filters import RB_REC_FILTER_SQL
from nfl_grades.grading.weights import (
    TE_ROLE_BALANCED,
    TE_ROLE_BLOCKING,
    TE_ROLE_RECEIVING,
    TE_TIER_REASON_ERA_AND_ROLE,
    TE_TIER_REASON_ROLE_BLOCKING,
    TE_V1_BLOCKING_WEIGHTS,
    TE_V1_CONFIDENCE_FULL_TARGETS,
    TE_V1_MIN_SNAPS_FOR_BLOCKING_LABEL,
    TE_V1_MIN_TARGETS_TO_GRADE,
    TE_V1_QUALIFIED_MIN_TARGETS,
    TE_V1_RAW_VALUE_COLS,
    TE_V1_SAMPLE_SIZE_COLS,
    TE_V1_SHRINKAGE_K,
    TE_V1_TARGET_RATE_BALANCED_LO,
    TE_V1_TARGET_RATE_RECEIVING,
    TE_V1_WEIGHTS,
    TE_COMPONENT_TARGET_EARN_RATE,
)

logger = logging.getLogger(__name__)

POSITION = "TE"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_tes_total: int
    n_tes_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    engine = get_engine()
    with pipeline_run("grading:te", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no TE targets found for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features, season)

            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_tes_total=len(graded),
            n_tes_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(f"tes_total={result.n_tes_total} tes_qualified={result.n_tes_qualified}")
    return result


# ---------------------------------------------------------------------------
# 1. Extract: plays + NGS + offensive snaps
# ---------------------------------------------------------------------------

_FEATURES_SQL = text(f"""
    WITH tes AS (
        SELECT player_id, full_name, gsis_id
        FROM players
        WHERE position = 'TE' AND gsis_id IS NOT NULL
    ),
    snap_agg AS (
        SELECT player_id, SUM(snaps_offense)::bigint AS snaps_offense
        FROM player_seasons
        WHERE season = :season
        GROUP BY player_id
    ),
    rec_agg AS (
        SELECT
            t.player_id,
            t.full_name,
            t.gsis_id,
            COUNT(*) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS n_targets,
            COUNT(*) FILTER (
                WHERE pl.receiver_player_id IS NOT NULL AND pl.complete_pass
            ) AS n_receptions,
            AVG(pl.epa) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS rec_epa_per_target,
            AVG(pl.success::int) FILTER (WHERE pl.receiver_player_id IS NOT NULL)
                AS success_rate_per_target,
            COUNT(*) FILTER (
                WHERE pl.receiver_player_id IS NOT NULL AND pl.fumble
            ) AS n_fumbles
        FROM tes t
        LEFT JOIN plays pl
          ON pl.receiver_player_id = t.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY t.player_id, t.full_name, t.gsis_id
    ),
    rec_yac_agg AS (
        SELECT
            t.player_id,
            COUNT(*) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS n_rec_with_xyac,
            AVG(pl.yards_after_catch - pl.xyac_mean_yardage) FILTER (
                WHERE pl.complete_pass AND pl.xyac_mean_yardage IS NOT NULL
            ) AS yac_over_expected_per_rec
        FROM tes t
        LEFT JOIN plays pl
          ON pl.receiver_player_id = t.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
        GROUP BY t.player_id
    ),
    te_games_agg AS (
        SELECT DISTINCT
            t.player_id,
            pl.posteam,
            pl.game_id
        FROM tes t
        JOIN plays pl
          ON pl.receiver_player_id = t.gsis_id
         AND pl.season = :season
         AND ({RB_REC_FILTER_SQL})
    ),
    team_pass_agg AS (
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
            SUM(tp.n_team_pass_att) AS n_team_pass_att_active
        FROM te_games_agg g
        JOIN team_pass_agg tp USING (posteam, game_id)
        GROUP BY g.player_id
    ),
    ngs_sep_agg AS (
        SELECT
            player_id,
            SUM(targets) AS ngs_targets,
            SUM(avg_separation * targets) AS ngs_separation_times_targets
        FROM ngs_receiving
        WHERE season = :season AND season_type = 'REG' AND week = 0
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
        COALESCE(snap_agg.snaps_offense, 0)          AS snaps_offense,
        rec_agg.n_fumbles,
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
        CASE WHEN rec_agg.n_receptions > 0 THEN
            rec_agg.n_fumbles::float / rec_agg.n_receptions
        END AS fumble_rate
    FROM rec_agg
    LEFT JOIN rec_yac_agg USING (player_id)
    LEFT JOIN earn_rate_agg USING (player_id)
    LEFT JOIN ngs_sep_agg USING (player_id)
    LEFT JOIN snap_agg USING (player_id)
    WHERE rec_agg.n_targets >= :min_targets
""")


def assign_te_role(n_targets: int, snaps_offense: int) -> str:
    tr = n_targets / max(snaps_offense, 1)
    if tr >= TE_V1_TARGET_RATE_RECEIVING:
        return TE_ROLE_RECEIVING
    if tr >= TE_V1_TARGET_RATE_BALANCED_LO:
        return TE_ROLE_BALANCED
    if tr < TE_V1_TARGET_RATE_BALANCED_LO and snaps_offense >= TE_V1_MIN_SNAPS_FOR_BLOCKING_LABEL:
        return TE_ROLE_BLOCKING
    return TE_ROLE_BALANCED


def compute_te_data_tier_and_reason(season: int, role: str) -> tuple[int, str | None]:
    """TE-only: merge era tier with blocking-role bump (ADR-0016)."""
    base_tier, base_reason = _era_tier_for_season(season)
    if role == TE_ROLE_BLOCKING:
        if base_tier == 1:
            return 2, TE_TIER_REASON_ROLE_BLOCKING
        return base_tier, TE_TIER_REASON_ERA_AND_ROLE
    return base_tier, base_reason


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_targets": TE_V1_MIN_TARGETS_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    float_cols = (
        "rec_epa_per_target",
        "success_rate_per_target",
        "yac_over_expected_per_rec",
        "separation",
        "target_earn_rate",
        "fumble_rate",
    )
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("Float64").astype(float)

    int_cols = (
        "n_targets",
        "n_receptions",
        "n_rec_with_xyac",
        "n_team_pass_att_active",
        "n_fumbles",
        "snaps_offense",
    )
    for col in int_cols:
        df[col] = df[col].fillna(0).astype(int)

    df["role"] = [
        assign_te_role(int(r["n_targets"]), int(r["snaps_offense"])) for _, r in df.iterrows()
    ]
    return df


def compute_grades(features: pd.DataFrame, season: int) -> pd.DataFrame:
    df = features.copy()
    df["qualified"] = df["n_targets"] >= TE_V1_QUALIFIED_MIN_TARGETS
    df["confidence"] = (df["n_targets"].astype(float) / TE_V1_CONFIDENCE_FULL_TARGETS).clip(upper=1.0)

    data_t: list[int] = []
    data_r: list[str | None] = []
    for _, r in df.iterrows():
        t, reas = compute_te_data_tier_and_reason(season, str(r["role"]))
        data_t.append(t)
        data_r.append(reas)
    df["data_tier"] = data_t
    df["data_tier_reason"] = data_r

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in TE_V1_RAW_VALUE_COLS.items():
        n_col = TE_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = TE_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    # Per-row composite: full weights vs blocking (earn omitted in weights dict).
    comp_z: list[float] = []
    for i, r in df.iterrows():
        w = TE_V1_BLOCKING_WEIGHTS if r["role"] == TE_ROLE_BLOCKING else TE_V1_WEIGHTS
        sub = z_frame.loc[[i], list(w.keys())]
        comp_z.append(float(composite.combine(sub, w).iloc[0]))
    df["composite_z"] = comp_z
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
    components = list(TE_V1_RAW_VALUE_COLS.keys())
    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = TE_V1_SAMPLE_SIZE_COLS[component]
        for _, r in graded.iterrows():
            used = True
            if component == TE_COMPONENT_TARGET_EARN_RATE and r["role"] == TE_ROLE_BLOCKING:
                used = False
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
                    "used_in_composite": used,
                }
            )

    conn.execute(_DELETE_STAT_COMPONENTS, {"season": season, "components": components})
    if component_rows:
        conn.execute(_INSERT_STAT_COMPONENTS, component_rows)

    grade_rows: list[dict[str, object]] = []
    for _, r in graded.iterrows():
        if pd.isna(r["grade"]):
            continue
        reason = r["data_tier_reason"]
        reason_out: str | None
        if reason is None or (isinstance(reason, float) and pd.isna(reason)):
            reason_out = None
        else:
            reason_out = str(reason)
        grade_rows.append(
            {
                "player_id": int(r["player_id"]),
                "season": season,
                "position": POSITION,
                "composite_grade": float(r["grade"]),
                "composite_z": float(r["composite_z"]),
                "percentile": float(r["percentile"]) if not pd.isna(r["percentile"]) else 50.0,
                "confidence": float(r["confidence"]),
                "data_tier": int(r["data_tier"]),
                "qualified": bool(r["qualified"]),
                "role": str(r["role"]),
                "data_tier_reason": reason_out,
            }
        )

    conn.execute(_DELETE_SEASON_GRADES, {"season": season, "position": POSITION})
    if grade_rows:
        conn.execute(_INSERT_SEASON_GRADES, grade_rows)

    return len(component_rows), len(grade_rows)


__all__ = [
    "POSITION",
    "RunResult",
    "assign_te_role",
    "compute_grades",
    "compute_te_data_tier_and_reason",
    "extract_features",
    "run",
    "write_results",
]
