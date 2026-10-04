"""Preview a weight change without re-extracting features or writing the DB.

This is the "fast iteration" path for tuning formula weights:

    nflgrades preview --season 2024 --position TE --weight te_drop_rate=-0.10

The flow reads existing `stat_components.z_score` for the position-season,
applies a candidate weight dict (defaults from `weights.py`, overridden by
`--weight` flags), rescores through the grader's own scoring step
(`scoring.score`), and prints a side-by-side comparison against the
currently-shipped grade.

Read-only — does not write to `season_grades` or `stat_components`. Use the
`grade --skip-extract` path (TBD) to commit the change after a preview run.

Weight overrides:
    --weight COMPONENT=VALUE         e.g. te_drop_rate=-0.10
    --weight COMPONENT=0             zero-weights a component (effectively removes it)
    pass multiple --weight flags to change multiple components in one run.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from nfl_grades.db import get_engine
from nfl_grades.grading import scoring
from nfl_grades.grading.progress import SeasonProgress
from nfl_grades.grading.weights import (
    CB_V1_WEIGHTS,
    EDGE_V1_WEIGHTS,
    IDL_V1_WEIGHTS,
    K_V1_WEIGHTS,
    LB_V1_WEIGHTS,
    P_V1_WEIGHTS,
    QB_V1_WEIGHTS,
    RB_V1_WEIGHTS,
    S_V1_WEIGHTS,
    TE_ROLE_BLOCKING,
    TE_V1_BLOCKING_WEIGHTS,
    TE_V1_WEIGHTS,
    WR_V1_WEIGHTS,
)

# Position → default weight dict. TE has a second dict for blocking_te role.
_DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "QB":   QB_V1_WEIGHTS,
    "RB":   RB_V1_WEIGHTS,
    "WR":   WR_V1_WEIGHTS,
    "TE":   TE_V1_WEIGHTS,
    "CB":   CB_V1_WEIGHTS,
    "S":    S_V1_WEIGHTS,
    "EDGE": EDGE_V1_WEIGHTS,
    "iDL":  IDL_V1_WEIGHTS,
    "LB":   LB_V1_WEIGHTS,
    "K":    K_V1_WEIGHTS,
    "P":    P_V1_WEIGHTS,
}

@dataclass(frozen=True)
class PreviewRow:
    player_id: int
    full_name: str
    role: str | None
    current_grade: float
    preview_grade: float
    delta: float
    current_rank: int
    preview_rank: int


def parse_weight_overrides(overrides: tuple[str, ...]) -> dict[str, float]:
    """Parse ``--weight foo=1.5`` style strings into a dict."""
    out: dict[str, float] = {}
    for s in overrides:
        if "=" not in s:
            raise ValueError(f"--weight expects KEY=VALUE, got {s!r}")
        k, v = s.split("=", 1)
        out[k.strip()] = float(v.strip())
    return out


def _resolve_weights(
    position: str, overrides: dict[str, float]
) -> tuple[dict[str, float], dict[str, float] | None]:
    """Apply overrides on top of the position's default weights.

    Returns (main_weights, blocking_weights_or_none). Both are returned for
    TE; blocking is None for every other position.
    """
    if position not in _DEFAULT_WEIGHTS:
        raise ValueError(
            f"unknown position {position!r}; supported: {sorted(_DEFAULT_WEIGHTS)}"
        )
    main = dict(_DEFAULT_WEIGHTS[position])
    unknown = set(overrides) - set(main)
    if unknown:
        raise ValueError(
            f"overrides reference components not in {position} formula: "
            f"{sorted(unknown)}"
        )
    for k, v in overrides.items():
        main[k] = v

    blocking: dict[str, float] | None = None
    if position == "TE":
        blocking = dict(TE_V1_BLOCKING_WEIGHTS)
        # Only carry over overrides that exist in the blocking dict (it omits
        # te_target_earn_rate). Silently ignore other overrides since they
        # don't apply to blocking-tier composite.
        for k, v in overrides.items():
            if k in blocking:
                blocking[k] = v
    return main, blocking


_FETCH_Z_SQL = text(
    """
    SELECT
        sc.season,
        sc.player_id,
        sc.component_name,
        sc.z_score
    FROM stat_components sc
    JOIN season_grades sg
      ON sg.player_id = sc.player_id
     AND sg.season    = sc.season
     AND sg.position  = :position
    WHERE sc.season = ANY(:seasons)
      AND sc.component_name LIKE :prefix
    """
)

_FETCH_GRADES_SQL = text(
    """
    SELECT
        sg.season,
        sg.player_id,
        p.full_name,
        sg.role,
        sg.qualified,
        sg.through_week,
        sg.composite_grade AS current_grade,
        sg.composite_z     AS current_composite_z,
        sg.percentile      AS current_percentile
    FROM season_grades sg
    JOIN players p USING (player_id)
    WHERE sg.season   = ANY(:seasons)
      AND sg.position = :position
    """
)

_COMPLETED_SEASONS_SQL = text(
    """
    SELECT DISTINCT season
    FROM season_grades
    WHERE position = :position AND through_week IS NULL
    """
)


def _component_prefix(position: str) -> str:
    return f"{position.lower()}_%"


def _load_stored_cohort(
    conn: Connection,
    seasons: list[int],
    position: str,
    overrides: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float] | pd.Series]:
    """Stored ``season_grades`` rows for ``(seasons, position)``, their
    Component z-scores (wide) and each player's Formula, all indexed by
    ``(season, player_id)``."""
    main_weights, blocking_weights = _resolve_weights(position, overrides)
    params = {"seasons": seasons, "position": position}
    z_rows = pd.read_sql(
        _FETCH_Z_SQL, conn, params={**params, "prefix": _component_prefix(position)}
    )
    grades = pd.read_sql(_FETCH_GRADES_SQL, conn, params=params).set_index(
        ["season", "player_id"]
    )
    z_wide = (
        z_rows.pivot(index=["season", "player_id"], columns="component_name", values="z_score")
        .astype(float)
        .reindex(grades.index)
    )
    formulas: dict[str, float] | pd.Series = main_weights
    if blocking_weights is not None:
        formulas = grades["role"].map(
            lambda role: blocking_weights if role == TE_ROLE_BLOCKING else main_weights
        )
    return grades, z_wide, formulas


def pooled_composite_sd(
    conn: Connection,
    position: str,
    overrides: dict[str, float] | None = None,
) -> float:
    """Pooled within-season SD of the raw Composite over the Qualified
    players of every completed season of ``position``, under current
    weights plus ``overrides``. Provisional grades are standardized by it.
    """
    seasons = [int(s) for s in conn.execute(_COMPLETED_SEASONS_SQL, {"position": position}).scalars()]
    grades, z_wide, formulas = _load_stored_cohort(conn, seasons, position, overrides or {})
    raw = scoring.raw_composite(z_wide, formulas)
    season = pd.Series(grades.index.get_level_values("season"), index=grades.index)
    return scoring.pooled_sd(raw, grades["qualified"].astype(bool), season)


def composite_sd_for(conn: Connection, position: str, progress: SeasonProgress) -> float | None:
    """The Composite SD a grader passes to ``scoring.score``: the pooled
    completed-season SD for a Provisional season, None (the cohort's own SD)
    otherwise."""
    return pooled_composite_sd(conn, position) if progress.is_provisional else None


def rescore_from_components(
    conn: Connection,
    season: int,
    position: str,
    overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Score every ``season_grades`` row for ``(season, position)`` from the
    stored ``stat_components`` z-scores, through the same scoring step the
    grader uses (including the pooled SD for a Provisional season).

    Returns one row per season_grades row with columns: season, player_id,
    full_name, role, qualified, through_week, current_grade,
    current_composite_z, current_percentile (as stored) and composite_z,
    grade, percentile (recomputed under current weights plus ``overrides``).
    """
    grades, z_wide, formulas = _load_stored_cohort(conn, [season], position, overrides or {})
    composite_sd = None
    if grades["through_week"].notna().any():
        composite_sd = pooled_composite_sd(conn, position, overrides)
    scored = scoring.score(
        z_wide, formulas, grades["qualified"].astype(bool), composite_sd=composite_sd
    )
    return grades.join(scored).reset_index()


def preview_position(
    season: int,
    position: str,
    overrides: dict[str, float],
    *,
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Recompute grades for ``(season, position)`` under a candidate weight set.

    Returns a DataFrame sorted by ``preview_grade`` (descending) with columns:
    player_id, full_name, role, current_grade, preview_grade, delta,
    current_rank, preview_rank. Only qualified players are included.
    """
    with (engine or get_engine()).connect() as conn:
        rescored = rescore_from_components(conn, season, position, overrides)

    result = rescored.loc[
        rescored["qualified"].astype(bool),
        ["player_id", "full_name", "role", "current_grade", "grade"],
    ].rename(columns={"grade": "preview_grade"})
    if result.empty:
        raise ValueError(
            f"no qualified {position} grades found for season={season} — "
            "run the grader for this (season, position) first"
        )

    result["delta"] = result["preview_grade"] - result["current_grade"]
    result["current_rank"] = (
        result["current_grade"].rank(method="min", ascending=False).astype(int)
    )
    result["preview_rank"] = (
        result["preview_grade"].rank(method="min", ascending=False).astype(int)
    )
    return result.sort_values("preview_grade", ascending=False).reset_index(drop=True)


_UPDATE_GRADE_SQL = text(
    """
    UPDATE season_grades
       SET composite_grade = :composite_grade,
           composite_z     = :composite_z,
           percentile      = :percentile
     WHERE player_id = :player_id
       AND season    = :season
       AND position  = :position
    """
)


def regrade_from_components(
    season: int,
    position: str,
    *,
    engine: Engine | None = None,
) -> int:
    """Recompute composite_grade / composite_z / percentile for every
    season_grades row in ``(season, position)`` using current weights.py and
    the existing stat_components z-scores.

    Does NOT re-extract features or recompute z-scores. Use this after a
    pure weight change (no SQL change, no new components). For schema
    changes use the normal ``grade`` path.

    Returns the number of rows updated. Idempotent.
    """
    with (engine or get_engine()).begin() as conn:
        rescored = rescore_from_components(conn, season, position)
        updates = [
            {
                "player_id": int(r.player_id),
                "season": season,
                "position": position,
                "composite_grade": float(r.grade),
                "composite_z": float(r.composite_z),
                "percentile": float(r.percentile),
            }
            for r in rescored.itertuples()
            if not pd.isna(r.grade)
        ]
        if updates:
            conn.execute(_UPDATE_GRADE_SQL, updates)
    return len(updates)


__all__ = [
    "PreviewRow",
    "composite_sd_for",
    "pooled_composite_sd",
    "parse_weight_overrides",
    "preview_position",
    "regrade_from_components",
    "rescore_from_components",
]
