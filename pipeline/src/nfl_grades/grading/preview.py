"""Preview a weight change without re-extracting features or writing the DB.

This is the "fast iteration" path for tuning formula weights:

    nflgrades preview --season 2024 --position TE --weight te_drop_rate=-0.10

The flow reads existing `stat_components.z_score` for the qualified cohort,
applies a candidate weight dict (defaults from `weights.py`, overridden by
`--weight` flags), recomputes composite_z + grade, and prints a side-by-side
comparison against the currently-shipped grade.

Read-only — does not write to `season_grades` or `stat_components`. Use the
`grade --skip-extract` path (TBD) to commit the change after a preview run.

Weight overrides:
    --weight COMPONENT=VALUE         e.g. te_drop_rate=-0.10
    --weight COMPONENT=0             zero-weights a component (effectively removes it)
    pass multiple --weight flags to change multiple components in one run.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nfl_grades.db import get_engine
from nfl_grades.grading import composite, sigmoid
from nfl_grades.grading.weights import (
    CB_V1_WEIGHTS,
    EDGE_V1_WEIGHTS,
    IDL_V1_WEIGHTS,
    LB_V1_WEIGHTS,
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


_FETCH_Z_FRAME_SQL = text(
    """
    SELECT
        sc.player_id,
        sc.component_name,
        sc.z_score
    FROM stat_components sc
    JOIN season_grades sg
      ON sg.player_id = sc.player_id
     AND sg.season    = sc.season
     AND sg.position  = :position
    WHERE sc.season = :season
      AND sc.component_name LIKE :prefix
    """
)

_FETCH_CURRENT_GRADES_SQL = text(
    """
    SELECT
        sg.player_id,
        p.full_name,
        sg.composite_grade AS current_grade,
        sg.role
    FROM season_grades sg
    JOIN players p USING (player_id)
    WHERE sg.season   = :season
      AND sg.position = :position
      AND sg.qualified = true
    """
)


def _component_prefix(position: str) -> str:
    return f"{position.lower()}_%"


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
    current_rank, preview_rank.

    Only qualified players are included (matches the production qualified
    cohort). The composite uses the same NaN-neutralize-to-zero convention as
    `compute_grades` (a missing z-score contributes 0).
    """
    main_weights, blocking_weights = _resolve_weights(position, overrides)
    eng = engine or get_engine()

    prefix = _component_prefix(position)
    with eng.connect() as conn:
        z_rows = pd.read_sql(
            _FETCH_Z_FRAME_SQL,
            conn,
            params={"season": season, "position": position, "prefix": prefix},
        )
        cur = pd.read_sql(
            _FETCH_CURRENT_GRADES_SQL,
            conn,
            params={"season": season, "position": position},
        )

    if cur.empty:
        raise ValueError(
            f"no qualified {position} grades found for season={season} — "
            "run the grader for this (season, position) first"
        )

    z_wide = (
        z_rows.pivot(index="player_id", columns="component_name", values="z_score")
        .astype(float)
    )

    # Restrict to qualified player_ids only — composite normalization is
    # within-cohort so unqualified rows don't enter z_wide.
    z_wide = z_wide.reindex(cur["player_id"].to_numpy())

    # Ensure every component in the weight dict has a column.
    for c in main_weights:
        if c not in z_wide.columns:
            z_wide[c] = np.nan
    if blocking_weights is not None:
        for c in blocking_weights:
            if c not in z_wide.columns:
                z_wide[c] = np.nan

    # Compute composite per row. For TE, dispatch by role; for others, single
    # weight set across the whole cohort.
    preview_z = pd.Series(np.nan, index=z_wide.index, dtype=float)
    if position == "TE":
        # Index `cur` by player_id for role lookup.
        roles = cur.set_index("player_id")["role"]
        main_idx = roles[roles != TE_ROLE_BLOCKING].index
        blk_idx = roles[roles == TE_ROLE_BLOCKING].index
        if len(main_idx):
            preview_z.loc[main_idx] = composite.combine(
                z_wide.loc[main_idx, list(main_weights)].fillna(0.0),
                main_weights,
            )
        if len(blk_idx) and blocking_weights is not None:
            preview_z.loc[blk_idx] = composite.combine(
                z_wide.loc[blk_idx, list(blocking_weights)].fillna(0.0),
                blocking_weights,
            )
    else:
        preview_z = composite.combine(
            z_wide[list(main_weights)].fillna(0.0),
            main_weights,
        )

    preview_grade = sigmoid.to_grade(preview_z.to_numpy())

    result = cur.copy()
    result["preview_grade"] = preview_grade
    result["delta"] = result["preview_grade"] - result["current_grade"]
    result["current_rank"] = (
        result["current_grade"].rank(method="min", ascending=False).astype(int)
    )
    result["preview_rank"] = (
        result["preview_grade"].rank(method="min", ascending=False).astype(int)
    )
    return result.sort_values("preview_grade", ascending=False).reset_index(drop=True)


_FETCH_ALL_Z_SQL = text(
    """
    SELECT
        sc.player_id,
        sc.component_name,
        sc.z_score
    FROM stat_components sc
    JOIN season_grades sg
      ON sg.player_id = sc.player_id
     AND sg.season    = sc.season
     AND sg.position  = :position
    WHERE sc.season = :season
      AND sc.component_name LIKE :prefix
    """
)

_FETCH_ALL_GRADES_SQL = text(
    """
    SELECT sg.player_id, sg.qualified, sg.role
    FROM season_grades sg
    WHERE sg.season = :season AND sg.position = :position
    """
)

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
    main_weights, blocking_weights = _resolve_weights(position, overrides={})
    eng = engine or get_engine()
    prefix = _component_prefix(position)

    with eng.begin() as conn:
        z_rows = pd.read_sql(
            _FETCH_ALL_Z_SQL,
            conn,
            params={"season": season, "position": position, "prefix": prefix},
        )
        all_grades = pd.read_sql(
            _FETCH_ALL_GRADES_SQL,
            conn,
            params={"season": season, "position": position},
        )

        if all_grades.empty:
            return 0

        z_wide = (
            z_rows.pivot(index="player_id", columns="component_name", values="z_score")
            .astype(float)
        )
        z_wide = z_wide.reindex(all_grades["player_id"].to_numpy())

        for c in main_weights:
            if c not in z_wide.columns:
                z_wide[c] = np.nan
        if blocking_weights is not None:
            for c in blocking_weights:
                if c not in z_wide.columns:
                    z_wide[c] = np.nan

        composite_z = pd.Series(np.nan, index=z_wide.index, dtype=float)
        if position == "TE":
            roles = all_grades.set_index("player_id")["role"]
            main_idx = roles[roles != TE_ROLE_BLOCKING].index
            blk_idx = roles[roles == TE_ROLE_BLOCKING].index
            if len(main_idx):
                composite_z.loc[main_idx] = composite.combine(
                    z_wide.loc[main_idx, list(main_weights)].fillna(0.0),
                    main_weights,
                )
            if len(blk_idx) and blocking_weights is not None:
                composite_z.loc[blk_idx] = composite.combine(
                    z_wide.loc[blk_idx, list(blocking_weights)].fillna(0.0),
                    blocking_weights,
                )
        else:
            composite_z = composite.combine(
                z_wide[list(main_weights)].fillna(0.0),
                main_weights,
            )

        grade = sigmoid.to_grade(composite_z.to_numpy())

        # Percentile is computed against the qualified cohort only (matches
        # the production grader). Unqualified players get NaN percentile
        # if there are <2 qualified, else their percentile against the
        # qualified pool.
        all_grades = all_grades.copy()
        all_grades["composite_z"] = composite_z.to_numpy()
        all_grades["grade"] = grade
        q_mask = all_grades["qualified"].astype(bool)
        q_grades = (
            all_grades.loc[q_mask, "grade"].dropna().sort_values().to_numpy()
        )
        if len(q_grades) >= 2:
            def _pct(g: float) -> float:
                if pd.isna(g):
                    return float("nan")
                return 100.0 * np.searchsorted(q_grades, g, side="right") / len(q_grades)

            all_grades["percentile"] = all_grades["grade"].apply(_pct)
        else:
            all_grades["percentile"] = 50.0

        updates = []
        for _, r in all_grades.iterrows():
            if pd.isna(r["grade"]) or pd.isna(r["composite_z"]):
                continue
            pct = r["percentile"]
            if pd.isna(pct):
                pct = 50.0
            updates.append(
                {
                    "player_id": int(r["player_id"]),
                    "season": season,
                    "position": position,
                    "composite_grade": float(r["grade"]),
                    "composite_z": float(r["composite_z"]),
                    "percentile": float(pct),
                }
            )
        if updates:
            conn.execute(_UPDATE_GRADE_SQL, updates)
    return len(updates)


__all__ = [
    "PreviewRow",
    "parse_weight_overrides",
    "preview_position",
    "regrade_from_components",
]
