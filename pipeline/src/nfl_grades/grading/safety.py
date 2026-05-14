"""Safety v1 grading pipeline (ADR-0019).

Flow:
    1. ``extract_features``: reads ``pfr_def_coverage_s`` (ingested by
       ``ingest/pfr_safety.py``) + ``player_seasons`` (for snaps_defense)
       and computes per-rate metrics from raw counts.
    2. ``compute_grades``: pure-python —
         shrink → z-score → NaN neutralization →
         composite → sigmoid → percentile rank.
    3. ``write_results``: idempotent upsert to stat_components +
       season_grades.

Public entry point: ``run(season)``.

Design notes:

- Data sources: PFR advanced defensive stats (coverage + attempted missed-
  tackle counts via ``pfr_def_coverage_s``), nflverse player stats (PBU,
  combined tackles, TFL, sacks), and ``player_seasons`` (snaps_defense).

- Data available from 2018. Earlier seasons return empty results.

- Qualification is snap-based (not target-based like CB): 200 snaps to
  appear, 400 snaps qualified, 700 snaps full confidence.

- missed_tackle_rate: derived as missed / (comb + missed) when missed_tackles
  is not NULL. If the pfr_advstats_def source does not include a missed-tackle
  column (varies by release), this component is NaN-neutralized to 0.0.

- backfield_disruption_per_snap: (tfl + sacks) / snaps_defense. TFL and sacks
  are combined because they measure the same underlying skill (stopping the
  play behind the line), and combining doubles the event count, improving
  stability.

- No role classification for safeties (no slot_pct equivalent). The single
  pool includes FS, SS, and hybrid safeties.
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
    S_COMPONENT_BACKFIELD_DISRUPTION,
    S_COMPONENT_MISSED_TACKLE_RATE,
    S_COMPONENT_PASSER_RATING_ALLOWED,
    S_COMPONENT_PBU_RATE,
    S_COMPONENT_TACKLES_PER_SNAP,
    S_COMPONENT_TARGET_RATE,
    S_V1_CONFIDENCE_FULL_SNAPS,
    S_V1_MIN_SNAPS_TO_GRADE,
    S_V1_QUALIFIED_MIN_SNAPS,
    S_V1_RAW_VALUE_COLS,
    S_V1_SAMPLE_SIZE_COLS,
    S_V1_SHRINKAGE_K,
    S_V1_WEIGHTS,
)
from nfl_grades.ingest.pfr_safety import PFR_DEF_COVERAGE_S_MIN_SEASON

logger = logging.getLogger(__name__)

POSITION = "S"


@dataclass(frozen=True)
class RunResult:
    season: int
    n_safeties_total: int
    n_safeties_qualified: int
    stat_components_written: int
    season_grades_written: int


def run(season: int) -> RunResult:
    """Run the full Safety v1 grading pipeline for one season.

    Idempotent: re-writes all stat_components and season_grades rows
    that belong to (season, position='S').

    Returns empty RunResult for seasons before PFR_DEF_COVERAGE_S_MIN_SEASON.
    """
    if season < PFR_DEF_COVERAGE_S_MIN_SEASON:
        logger.warning(
            "Safety grading requires PFR coverage data (available from %d); "
            "season %d has no Safety grades.",
            PFR_DEF_COVERAGE_S_MIN_SEASON,
            season,
        )
        return RunResult(season, 0, 0, 0, 0)

    engine = get_engine()
    with pipeline_run("grading:safety", season=season) as handle:
        with engine.begin() as conn:
            features = extract_features(conn, season)
            if features.empty:
                logger.warning("no Safety data found in pfr_def_coverage_s for season %d", season)
                result = RunResult(season, 0, 0, 0, 0)
                handle.rows_written = 0
                handle.note("no data")
                return result

            graded = compute_grades(features)
            n_components, n_grades = write_results(conn, graded, season)

        result = RunResult(
            season=season,
            n_safeties_total=len(graded),
            n_safeties_qualified=int(graded["qualified"].sum()),
            stat_components_written=n_components,
            season_grades_written=n_grades,
        )
        handle.rows_written = n_grades
        handle.note(
            f"safeties_total={result.n_safeties_total} "
            f"safeties_qualified={result.n_safeties_qualified}"
        )
    return result


# ---------------------------------------------------------------------------
# 1. Extract features
# ---------------------------------------------------------------------------

_FEATURES_SQL = text("""
    SELECT
        s.player_id,
        p.full_name,
        s.games,
        s.targets,
        s.completions,
        s.yards,
        s.tds_allowed,
        s.ints,
        s.pass_breakups,
        s.comb_tackles,
        s.tfl,
        s.sacks,
        s.missed_tackles,
        COALESCE(ps_agg.snaps_defense, 0) AS snaps_defense
    FROM pfr_def_coverage_s s
    JOIN players p ON p.player_id = s.player_id
    JOIN (
        SELECT DISTINCT ON (player_id) player_id, position_played
        FROM player_seasons
        WHERE season = :season
        ORDER BY player_id, snaps_defense DESC
    ) ps_pos ON ps_pos.player_id = s.player_id AND ps_pos.position_played = 'S'
    LEFT JOIN (
        SELECT player_id, SUM(snaps_defense) AS snaps_defense
        FROM player_seasons
        WHERE season = :season
        GROUP BY player_id
    ) ps_agg ON ps_agg.player_id = s.player_id
    WHERE s.season = :season
      AND COALESCE(ps_agg.snaps_defense, 0) >= :min_snaps
""")


def extract_features(conn: Connection, season: int) -> pd.DataFrame:
    """Pull per-safety raw stats from pfr_def_coverage_s.

    Returns a DataFrame filtered to safeties with at least
    S_V1_MIN_SNAPS_TO_GRADE defensive snaps.

    Columns returned:
        player_id, full_name, games, targets, completions, yards, tds_allowed,
        ints, pass_breakups, comb_tackles, tfl, sacks, missed_tackles,
        snaps_defense,
        passer_rating_allowed, pbu_rate, target_rate,
        tackles_per_snap, missed_tackle_rate,
        backfield_disruption_per_snap, tackle_attempts
    """
    rows = (
        conn.execute(
            _FEATURES_SQL,
            {"season": season, "min_snaps": S_V1_MIN_SNAPS_TO_GRADE},
        )
        .mappings()
        .all()
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    int_cols = ("games", "targets", "completions", "yards", "tds_allowed",
                "ints", "pass_breakups", "comb_tackles", "tfl",
                "missed_tackles", "snaps_defense")
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    float_cols = ("sacks",)
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("Float64").astype(float)

    # NFL passer rating allowed when targeted (v1.1). Replaces separate
    # comp_pct_allowed, yards_per_target_allowed, and int_rate components.
    targets = df["targets"].astype(float).clip(lower=1)
    comp_pct = df["completions"].astype(float) / targets
    ypa = df["yards"].astype(float) / targets
    td_pct = df["tds_allowed"].astype(float) / targets
    int_pct = df["ints"].astype(float) / targets
    a = ((comp_pct - 0.30) * 5).clip(lower=0.0, upper=2.375)
    b = ((ypa - 3.0) * 0.25).clip(lower=0.0, upper=2.375)
    c = (td_pct * 20).clip(lower=0.0, upper=2.375)
    d = (2.375 - int_pct * 25).clip(lower=0.0, upper=2.375)
    df["passer_rating_allowed"] = np.where(
        df["targets"] > 0,
        ((a + b + c + d) / 6.0 * 100.0).astype(float),
        np.nan,
    )

    # PBU rate (PBU-only — INTs are captured inside passer_rating_allowed).
    df["pbu_rate"] = np.where(
        (df["targets"] > 0) & df["pass_breakups"].notna(),
        df["pass_breakups"] / df["targets"],
        np.nan,
    )

    df["target_rate"] = np.where(
        df["snaps_defense"] > 0,
        df["targets"] / df["snaps_defense"],
        np.nan,
    )

    df["tackles_per_snap"] = np.where(
        df["snaps_defense"] > 0,
        df["comb_tackles"] / df["snaps_defense"],
        np.nan,
    )

    # tackle_attempts = comb + missed; used as EB sample size for missed_rate.
    df["tackle_attempts"] = df["comb_tackles"] + df["missed_tackles"]

    # missed_tackle_rate = missed / (comb + missed). NaN when missed is 0/NULL.
    # When missed_tackles was NULL in pfr_advstats_def, it was stored as 0
    # after fillna above. We treat missed_tackles == 0 as unknown (not truly
    # zero) — if tackle_attempts > 0 AND the original missed was NULL, the
    # rate would be spuriously 0.0. We detect this by checking that the
    # original column was non-zero before fillna.
    # Simpler: just set NaN when comb_tackles == 0 OR tackle_attempts == 0.
    df["missed_tackle_rate"] = np.where(
        df["tackle_attempts"] > 0,
        df["missed_tackles"] / df["tackle_attempts"],
        np.nan,
    )

    sacks_safe = df["sacks"].fillna(0.0)
    df["backfield_disruption_per_snap"] = np.where(
        df["snaps_defense"] > 0,
        (df["tfl"] + sacks_safe) / df["snaps_defense"],
        np.nan,
    )

    return df


# ---------------------------------------------------------------------------
# 2. Compute grades
# ---------------------------------------------------------------------------

def compute_grades(features: pd.DataFrame) -> pd.DataFrame:
    """Apply shrinkage → z-score → NaN neutralization → composite → sigmoid.

    Returns the input DataFrame augmented with:
        raw_*/adjusted_*/z_* columns per component,
        composite_z, grade, percentile, qualified, confidence.
    """
    df = features.copy()

    df["qualified"] = df["snaps_defense"] >= S_V1_QUALIFIED_MIN_SNAPS
    df["confidence"] = (df["snaps_defense"].astype(float) / S_V1_CONFIDENCE_FULL_SNAPS).clip(
        upper=1.0
    )

    z_frame = pd.DataFrame(index=df.index)
    for component, raw_col in S_V1_RAW_VALUE_COLS.items():
        n_col = S_V1_SAMPLE_SIZE_COLS[component]
        raw = df[raw_col]
        n = df[n_col]
        k = S_V1_SHRINKAGE_K[component]
        shrunk = empirical_bayes.shrink_series(raw, n, k=k)
        z = zscore.zscore(shrunk, qualified_mask=df["qualified"])
        df[f"raw_{component}"] = raw
        df[f"adjusted_{component}"] = shrunk
        df[f"z_{component}"] = z
        z_frame[component] = z.fillna(0.0)

    df["composite_z"] = composite.combine(z_frame, S_V1_WEIGHTS)
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
# 3. Write to stat_components + season_grades
# ---------------------------------------------------------------------------

_DELETE_STAT_COMPONENTS = text("""
    DELETE FROM stat_components
    WHERE season = :season
      AND component_name LIKE 's_%'
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
    components = list(S_V1_RAW_VALUE_COLS.keys())
    era_tier, era_reason = _era_tier_for_season(season)

    component_rows: list[dict[str, object]] = []
    for component in components:
        n_col = S_V1_SAMPLE_SIZE_COLS[component]
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

    conn.execute(_DELETE_STAT_COMPONENTS, {"season": season})
    if component_rows:
        conn.execute(_INSERT_STAT_COMPONENTS, component_rows)

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
                "role": None,
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
