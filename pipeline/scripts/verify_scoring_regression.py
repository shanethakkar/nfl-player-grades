"""Regression check for the standardized Composite (issue #6, ADR-0028).

Rescores every graded position-season from the stored stat_components /
team_ol_components z-scores through ``scoring.score`` and compares against
what's stored. Read-only.

Standardization rescales the Composite, so values change by design. What
must not change is the ranking of players who have every Formula
Component: their Composite is the same weighted sum, divided by one
per-position-season constant. Players missing a Component can move,
because their weights are now renormalized instead of zero-filled; the
report shows how far.

Per position-season it prints:
    rho_full   Spearman(stored, new composite) over players with every
               Component the season has. Must be 1.0.
    n_missing  players missing at least one Component, and the largest
               rank move among them (percentile points).
    90+        share of qualified players graded 90+, stored -> new.

Exits non-zero if any rho_full < 1 or any stored row is left ungraded.
"""

from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nfl_grades.db import get_engine
from nfl_grades.grading import scoring
from nfl_grades.grading.preview import _DEFAULT_WEIGHTS, rescore_from_components
from nfl_grades.grading.weights import OL_V1_WEIGHTS

_Z_SQL = text(
    """
    SELECT sc.player_id AS entity_id, sc.component_name, sc.z_score
    FROM stat_components sc
    WHERE sc.season = :season AND sc.component_name LIKE :prefix
    """
)
_OL_Z_SQL = text(
    """
    SELECT team_id AS entity_id, component_name, z_score
    FROM team_ol_components WHERE season = :season
    """
)
_OL_GRADES_SQL = text(
    """
    SELECT team_id, qualified,
           composite_z AS current_composite_z,
           composite_grade AS current_grade,
           percentile AS current_percentile
    FROM team_ol_grades WHERE season = :season
    """
)


def _rescore_ol(conn: Connection, season: int) -> pd.DataFrame:
    grades = pd.read_sql(_OL_GRADES_SQL, conn, params={"season": season}).set_index("team_id")
    z = _components(conn, season, "OL").reindex(grades.index)
    return grades.join(scoring.score(z, OL_V1_WEIGHTS, grades["qualified"].astype(bool)))


def _components(conn: Connection, season: int, position: str) -> pd.DataFrame:
    if position == "OL":
        rows = pd.read_sql(_OL_Z_SQL, conn, params={"season": season})
    else:
        prefix = f"{position.lower()}_%"
        rows = pd.read_sql(_Z_SQL, conn, params={"season": season, "prefix": prefix})
    return rows.pivot(index="entity_id", columns="component_name", values="z_score").astype(float)


def _check(conn: Connection, position: str, season: int) -> tuple[bool, str]:
    if position == "OL":
        df = _rescore_ol(conn, season)
        formula = OL_V1_WEIGHTS
    else:
        df = rescore_from_components(conn, season, position).set_index("player_id")
        formula = _DEFAULT_WEIGHTS[position]
    z = _components(conn, season, position).reindex(df.index, columns=list(formula))
    # A Component missing for the whole season (RB YAC pre-2018, drops
    # pre-2022) renormalizes everyone alike, so it can't reorder anyone.
    complete = z.dropna(axis=1, how="all").notna().all(axis=1)

    rho_full = df.loc[complete, "current_composite_z"].corr(
        df.loc[complete, "composite_z"], method="spearman"
    )
    pct_move = (df["percentile"] - df["current_percentile"]).abs()
    max_move = float(pct_move[~complete].max()) if (~complete).any() else 0.0
    qualified = df["qualified"].astype(bool)
    before = (df.loc[qualified, "current_grade"] >= 90).mean()
    after = (df.loc[qualified, "grade"] >= 90).mean()
    ungraded = int(df["grade"].isna().sum())

    # Fewer than two complete players (or all tied): nothing to rank.
    rank_ok = pd.isna(rho_full) or rho_full >= 1 - 1e-12
    ok = rank_ok and ungraded == 0
    line = (
        f"{'ok ' if ok else 'BAD'} {position:<4} {season}  rows={len(df):>4}  "
        f"rho_full={rho_full:.6f}  n_missing={int((~complete).sum()):>3} "
        f"(max pct move {max_move:5.1f})  90+ {before:5.1%} -> {after:5.1%}"
        + (f"  ungraded={ungraded}" if ungraded else "")
    )
    return ok, line


def main() -> int:
    failures = 0
    with get_engine().connect() as conn:
        seasons_by_position = pd.read_sql(
            text("SELECT DISTINCT position, season FROM season_grades ORDER BY 1, 2"), conn
        )
        targets: list[tuple[str, int]] = [
            (r.position, int(r.season))
            for r in seasons_by_position.itertuples()
            if r.position in _DEFAULT_WEIGHTS
        ]
        ol_seasons = pd.read_sql(text("SELECT DISTINCT season FROM team_ol_grades"), conn)
        targets += [("OL", int(s)) for s in sorted(ol_seasons["season"])]

        for position, season in targets:
            ok, line = _check(conn, position, season)
            failures += not ok
            print(line)

    print(f"\n{len(targets)} position-seasons, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
