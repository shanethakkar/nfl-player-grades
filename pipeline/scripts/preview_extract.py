"""Preview a grader code change (SQL extract, filter, cohort) before writing.

``nflgrades preview`` rescores the *stored* z-scores, so it can't show a
change to what a grader pulls from ``plays`` / ``ngs_*`` / ``pfr_*``.
This script runs the grader's own ``extract_features`` and
``compute_grades`` from the working tree, then diffs the result against
the stored ``season_grades``. Read-only: nothing is written.

Use it on Path B changes (docs/grading/iteration-workflow.md) before the
full ``nflgrades grade`` restatement. OL is team-level and not supported.

Usage:
    uv run python scripts/preview_extract.py --season 2024 --position QB
    uv run python scripts/preview_extract.py --season 2024 --position EDGE --top 30

Prints, over players qualified in the new grading:
    - Spearman(stored grade, new grade) over players with a stored grade
    - the new top N with stored rank/grade alongside
    - the biggest movers
    - players entering or leaving the graded cohort
"""

from __future__ import annotations

import argparse
import inspect

import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text

from nfl_grades.db import get_engine
from nfl_grades.grading.run import POSITION_RUNNERS

_STORED_SQL = text(
    """
    SELECT sg.player_id, p.full_name, sg.composite_grade AS stored_grade,
           sg.qualified AS stored_qualified
    FROM season_grades sg
    JOIN players p ON p.player_id = sg.player_id
    WHERE sg.season = :season AND sg.position = :position
    """
)
_NAMES_SQL = text("SELECT player_id, full_name FROM players WHERE player_id = ANY(:ids)")


def _grader(position: str):  # type: ignore[no-untyped-def]
    pos = next((k for k in POSITION_RUNNERS if k.upper() == position.upper()), None)
    if pos is None:
        raise SystemExit(f"unknown position {position!r}; known: {sorted(POSITION_RUNNERS)}")
    if pos == "OL":
        raise SystemExit("OL is team-level; not supported")
    return pos, inspect.getmodule(POSITION_RUNNERS[pos])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--position", required=True)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    position, module = _grader(args.position)
    with get_engine().connect() as conn:
        features = module.extract_features(conn, args.season)
        n_params = len(inspect.signature(module.compute_grades).parameters)
        new = (
            module.compute_grades(features, args.season)
            if n_params > 1
            else module.compute_grades(features)
        )
        stored = pd.DataFrame(
            conn.execute(_STORED_SQL, {"season": args.season, "position": position})
            .mappings()
            .all()
        )
        names = pd.DataFrame(
            conn.execute(_NAMES_SQL, {"ids": [int(i) for i in new["player_id"]]}).mappings().all()
        )
        conn.rollback()

    new = new[new["grade"].notna()][["player_id", "grade", "qualified"]]
    new = new.merge(names, on="player_id", how="left")
    df = new.merge(stored.drop(columns="full_name"), on="player_id", how="left")

    q = df[df["qualified"]].copy()
    q["new_rank"] = q["grade"].rank(ascending=False, method="min").astype(int)
    q["stored_rank"] = q["stored_grade"].rank(ascending=False, method="min").astype("Int64")
    q["delta"] = q["grade"] - q["stored_grade"]
    both = q.dropna(subset=["stored_grade"])
    rho = spearmanr(both["stored_grade"], both["grade"])[0] if len(both) > 2 else float("nan")

    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:.2f}".format)
    cols = ["full_name", "stored_rank", "new_rank", "stored_grade", "grade", "delta"]
    print(
        f"{position} {args.season}: qualified new={len(q)} "
        f"stored={int(stored['stored_qualified'].sum()) if not stored.empty else 0}  "
        f"spearman(stored, new)={rho:.3f}"
    )
    print(f"\nTop {args.top} (new):")
    print(q.sort_values("new_rank")[cols].head(args.top).to_string(index=False))
    print(f"\nBiggest movers (top {args.top}):")
    movers = q.reindex(q["delta"].abs().sort_values(ascending=False).index)
    print(movers[cols].head(args.top).to_string(index=False))

    entered = sorted(set(new["player_id"]) - set(stored.get("player_id", [])))
    left = sorted(set(stored.get("player_id", [])) - set(new["player_id"]))
    if entered:
        print(f"\nEntering cohort ({len(entered)}):")
        print(", ".join(new.set_index("player_id").loc[entered, "full_name"].astype(str)))
    if left:
        print(f"\nLeaving cohort ({len(left)}):")
        print(", ".join(stored.set_index("player_id").loc[left, "full_name"].astype(str)))


if __name__ == "__main__":
    main()
