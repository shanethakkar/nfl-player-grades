"""Face-check the QB v1 grades.

Prints, per season:
  - Top 15 qualified QBs by composite grade
  - A few explicit name checks (Mahomes, Allen, Jackson, Burrow) to make
    sure ingest->features->grade didn't go sideways on specific players
  - Bottom of the qualified list so we can see who's getting the worst grade
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import text

from nfl_grades.db import get_engine

SEASONS = [int(s) for s in os.environ.get("SEASONS", "2024 2025").split()]


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        for season in SEASONS:
            _section(f"SEASON {season}")
            _counts(conn, season)
            _top_grades(conn, season, 15)
            _focus_qbs(conn, season)
            _bottom_grades(conn, season, 5)


def _section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def _counts(conn, season: int) -> None:
    row = conn.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE qualified)     AS qualified,
            COUNT(*) FILTER (WHERE NOT qualified) AS unqualified,
            ROUND(AVG(composite_grade) FILTER (WHERE qualified)::numeric, 1)  AS avg_grade_qual,
            ROUND(AVG(composite_grade)::numeric, 1)                           AS avg_grade_all
        FROM season_grades
        WHERE season = :s AND position = 'QB'
    """), {"s": season}).first()
    if row:
        print(f"qualified={row[0]} unqualified={row[1]}  mean grade (qual)={row[2]}  mean (all)={row[3]}")


def _top_grades(conn, season: int, n: int) -> None:
    print(f"\nTop {n} qualified QBs:")
    print(f"  {'#':<3} {'QB':<22} {'Team':<4} {'DB':<5} {'Grade':<6} "
          f"{'zCmp':<6} {'Pct':<6} {'EPA/db':<8} {'CPOE':<6} {'Succ%':<6}")
    rows = conn.execute(text("""
        SELECT
            p.full_name,
            MODE() WITHIN GROUP (ORDER BY pl.posteam)  AS team,
            sg.composite_grade,
            sg.composite_z,
            sg.percentile,
            ROUND(sc_epa.raw_value::numeric, 3)        AS epa_per_db,
            ROUND(sc_cpoe.raw_value::numeric, 2)       AS cpoe,
            ROUND(sc_succ.raw_value::numeric * 100, 1) AS success_pct,
            sc_epa.sample_size                         AS n_db
        FROM season_grades sg
        JOIN players p ON p.player_id = sg.player_id
        JOIN plays pl ON pl.passer_player_id = p.gsis_id AND pl.season = sg.season
        LEFT JOIN stat_components sc_epa
               ON sc_epa.player_id = sg.player_id AND sc_epa.season = sg.season
              AND sc_epa.component_name = 'qb_epa_per_dropback'
        LEFT JOIN stat_components sc_cpoe
               ON sc_cpoe.player_id = sg.player_id AND sc_cpoe.season = sg.season
              AND sc_cpoe.component_name = 'qb_cpoe'
        LEFT JOIN stat_components sc_succ
               ON sc_succ.player_id = sg.player_id AND sc_succ.season = sg.season
              AND sc_succ.component_name = 'qb_success_rate'
        WHERE sg.season = :s AND sg.position = 'QB' AND sg.qualified
        GROUP BY p.full_name, sg.composite_grade, sg.composite_z,
                 sg.percentile, sc_epa.raw_value, sc_cpoe.raw_value,
                 sc_succ.raw_value, sc_epa.sample_size
        ORDER BY sg.composite_grade DESC
        LIMIT :n
    """), {"s": season, "n": n}).all()
    for i, r in enumerate(rows, start=1):
        print(f"  {i:<3} {r[0]:<22} {r[1]:<4} {r[8]:<5} "
              f"{r[2]:<6.1f} {r[3]:<+6.2f} {r[4]:<6.1f} {r[5]:<+8.3f} "
              f"{r[6]:<+6.2f} {r[7]:<6.1f}")


def _focus_qbs(conn, season: int) -> None:
    focus = [
        ("Patrick Mahomes",   "00-0033873"),
        ("Josh Allen",        "00-0034857"),
        ("Lamar Jackson",     "00-0034796"),
        ("Joe Burrow",        "00-0036442"),
        ("Jayden Daniels",    "00-0039910"),   # 2024+
        ("Jared Goff",        "00-0033106"),
        ("Drake Maye",        "00-0039851"),   # 2024+ rookie
    ]
    print("\nFocus QBs:")
    print(f"  {'QB':<22} {'Grade':<6} {'Pct':<6} {'Qual':<6} {'DB':<5} {'EPA/db':<8}")
    for name, gsis in focus:
        row = conn.execute(text("""
            SELECT
                sg.composite_grade, sg.percentile, sg.qualified,
                sc_epa.sample_size, ROUND(sc_epa.raw_value::numeric, 3)
            FROM season_grades sg
            JOIN players p ON p.player_id = sg.player_id
            LEFT JOIN stat_components sc_epa
                   ON sc_epa.player_id = sg.player_id AND sc_epa.season = sg.season
                  AND sc_epa.component_name = 'qb_epa_per_dropback'
            WHERE sg.season = :s AND sg.position = 'QB' AND p.gsis_id = :gsis
        """), {"s": season, "gsis": gsis}).first()
        if row is None:
            print(f"  {name:<22} -- (no grade row)")
        else:
            qual = "Y" if row[2] else "N"
            print(f"  {name:<22} {row[0]:<6.1f} {row[1]:<6.1f} {qual:<6} "
                  f"{row[3]:<5} {row[4]:<+8.3f}")


def _bottom_grades(conn, season: int, n: int) -> None:
    print(f"\nBottom {n} qualified QBs:")
    print(f"  {'QB':<22} {'Grade':<6} {'DB':<5} {'EPA/db':<8} {'CPOE':<6}")
    rows = conn.execute(text("""
        SELECT
            p.full_name, sg.composite_grade,
            sc_epa.sample_size, ROUND(sc_epa.raw_value::numeric, 3),
            ROUND(sc_cpoe.raw_value::numeric, 2)
        FROM season_grades sg
        JOIN players p ON p.player_id = sg.player_id
        LEFT JOIN stat_components sc_epa
               ON sc_epa.player_id = sg.player_id AND sc_epa.season = sg.season
              AND sc_epa.component_name = 'qb_epa_per_dropback'
        LEFT JOIN stat_components sc_cpoe
               ON sc_cpoe.player_id = sg.player_id AND sc_cpoe.season = sg.season
              AND sc_cpoe.component_name = 'qb_cpoe'
        WHERE sg.season = :s AND sg.position = 'QB' AND sg.qualified
        ORDER BY sg.composite_grade ASC
        LIMIT :n
    """), {"s": season, "n": n}).all()
    for r in rows:
        print(f"  {r[0]:<22} {r[1]:<6.1f} {r[2]:<5} "
              f"{r[3]:<+8.3f} {r[4]:<+6.2f}")


if __name__ == "__main__":
    main()
