"""Face-check TE v1 grades (ADR-0016)."""

from __future__ import annotations

import contextlib
import os
import sys

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text

from nfl_grades.db import get_engine

SEASONS = [int(s) for s in os.environ.get("SEASONS", "2024 2025").split()]


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        for season in SEASONS:
            print()
            print("=" * 90)
            print(f"SEASON {season}")
            print("=" * 90)
            row = conn.execute(
                text("""
                SELECT
                    COUNT(*) FILTER (WHERE qualified) AS q,
                    COUNT(*) FILTER (WHERE NOT qualified) AS uq
                FROM season_grades
                WHERE season = :s AND position = 'TE'
                """),
                {"s": season},
            ).first()
            if row:
                print(f"qualified={row[0]} unqualified={row[1]}")
            _top(conn, season, 20)


def _top(conn, season: int, n: int) -> None:
    print(f"\nTop {n} qualified TEs:")
    print(f"  {'#':<3} {'Name':<24} {'Grade':<6} {'role':<14} {'tier':<4} {'reason':<20} {'Tgt':<5}")
    sql = text("""
        SELECT
            p.full_name,
            sg.composite_grade,
            sg.role,
            sg.data_tier,
            sg.data_tier_reason
        FROM season_grades sg
        JOIN players p ON p.player_id = sg.player_id
        WHERE sg.season = :s AND sg.position = 'TE' AND sg.qualified
        ORDER BY sg.composite_grade DESC
        LIMIT :n
    """)
    rows = conn.execute(sql, {"s": season, "n": n}).all()
    for i, (name, g, role, dtr, dtn) in enumerate(rows, 1):
        rsn = dtn or ""
        if len(rsn) > 18:
            rsn = rsn[:17] + "…"
        print(
            f"  {i:<3} {name[:24]:<24} {g:<6.1f} {str(role or '--'):<14} "
            f"{dtr!s:<4} {rsn:<20}"
        )
    # Earn component used_in_composite check for a blocking role row
    sample = conn.execute(
        text("""
        SELECT sc.used_in_composite, sg.role, sc.component_name
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id AND sg.season = sc.season
        WHERE sc.season = :s
          AND sg.position = 'TE'
          AND sc.component_name = 'te_target_earn_rate'
          AND sg.role = 'blocking_te'
        LIMIT 3
        """),
        {"s": season},
    ).all()
    if sample:
        print(f"\n  (sanity) blocking TE earn used_in_composite: {[s[0] for s in sample]}")


if __name__ == "__main__":
    main()
