"""Regression check for the shared scoring step (issue #2).

Recomputes composite_z, grade and percentile for every graded
position-season from the stored stat_components / team_ol_components
z-scores, through ``scoring.score``, and compares against what's stored.
Read-only.

Exits non-zero if any value differs by more than TOLERANCE.
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

TOLERANCE = 1e-9
COLUMNS = (
    ("composite_z", "current_composite_z"),
    ("grade", "current_grade"),
    ("percentile", "current_percentile"),
)

_OL_Z_SQL = text(
    "SELECT team_id, component_name, z_score FROM team_ol_components WHERE season = :season"
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
    z = (
        pd.read_sql(_OL_Z_SQL, conn, params={"season": season})
        .pivot(index="team_id", columns="component_name", values="z_score")
        .astype(float)
        .reindex(grades.index)
    )
    return grades.join(scoring.score(z, OL_V1_WEIGHTS, grades["qualified"].astype(bool)))


def _max_diffs(df: pd.DataFrame) -> dict[str, float]:
    return {
        new: float((df[new] - df[stored]).abs().max()) if len(df) else 0.0
        for new, stored in COLUMNS
    }


def main() -> int:
    failures = 0
    total_rows = 0
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
            if position == "OL":
                df = _rescore_ol(conn, season)
            else:
                df = rescore_from_components(conn, season, position)
            diffs = _max_diffs(df)
            ungraded = int(df["grade"].isna().sum())
            ok = ungraded == 0 and all(d <= TOLERANCE for d in diffs.values())
            total_rows += len(df)
            failures += not ok
            print(
                f"{'ok ' if ok else 'BAD'} {position:<4} {season}  rows={len(df):>4}  "
                + "  ".join(f"max|d {k}|={v:.2e}" for k, v in diffs.items())
                + (f"  ungraded={ungraded}" if ungraded else "")
            )

    print(f"\n{len(targets)} position-seasons, {total_rows} rows, {failures} mismatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
