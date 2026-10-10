"""Check that the evaluation harness reproduces stored grades (#12, #13).

For each position and completed season in the harness windows, builds the
full-season panel with ``grading.panels``, scores it with the current
Formula, and compares against what the grader stored for Qualified
players: every Component's raw value (``stat_components.raw_value``) and
the standardized Composite (``season_grades.composite_z``). Read-only.

A mismatch means the harness and the grader read different data, or the
stored grades are stale (regrade the season).

    python scripts/verify_evaluation_panels.py            # every harness position
    python scripts/verify_evaluation_panels.py RB WR

Exits non-zero on any mismatch.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

from nfl_grades.db import get_engine
from nfl_grades.grading import evaluation, panels

_TOL = 1e-9

_STORED_SQL = text("""
    SELECT g.player_id, g.season, g.composite_z, sc.component_name AS component, sc.raw_value
    FROM season_grades g
    JOIN stat_components sc ON sc.player_id = g.player_id AND sc.season = g.season
    WHERE g.position = :position AND g.qualified AND g.through_week IS NULL
      AND g.season = ANY(:seasons)
      AND sc.component_name = ANY(:components)
""")


def check(position: str) -> bool:
    source = panels.POSITIONS[position]
    seasons = sorted({s for w in evaluation.WINDOWS.values() for s in w})
    with get_engine().connect() as conn:
        data = panels.load(conn, source, seasons=seasons)
        stored = pd.DataFrame(
            conn.execute(
                _STORED_SQL,
                {"position": position, "seasons": seasons, "components": list(source.weights)},
            ).mappings()
        )

    scores = evaluation.score_panel(data.panel, data.roster, source.formula)
    full = scores[scores["split"] == "full"]
    keys = ["player_id", "season"]

    grades = stored.drop_duplicates(keys)[[*keys, "composite_z"]]
    composite = grades.merge(full, on=keys, how="outer", indicator=True)
    raw = stored.merge(
        data.panel[data.panel["split"] == "full"], on=[*keys, "component"], how="left"
    )

    ok = True
    print(f"\n{position}")
    print(f"{'season':>6} {'qualified':>9} {'max |dz|':>10} {'raw rows':>8} {'max |draw|':>10}")
    for season in seasons:
        c = composite[composite["season"] == season]
        r = raw[raw["season"] == season]
        unmatched = int((c["_merge"] != "both").sum())
        dz = (c["composite_z"] - c["composite"]).abs().max()
        draw = (r["raw_value"].astype(float) - r["raw"]).abs()
        # Both missing (e.g. no FTN before 2022) is a match.
        draw = draw[~(r["raw_value"].isna() & r["raw"].isna())].fillna(np.inf).max()
        bad = unmatched > 0 or not dz <= _TOL or not (pd.isna(draw) or draw <= _TOL)
        ok &= not bad
        flag = "  MISMATCH" if bad else ""
        if unmatched:
            flag += f" ({unmatched} player-seasons in only one of stored / harness)"
        print(f"{season:>6} {len(c):>9} {dz:>10.1e} {len(r):>8} {draw:>10.1e}{flag}")
    return ok


def main(argv: list[str]) -> int:
    positions = argv or list(panels.POSITIONS)
    results = [check(p) for p in positions]
    if all(results):
        print("\nAll stored values reproduced.")
        return 0
    print("\nMismatches found.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
