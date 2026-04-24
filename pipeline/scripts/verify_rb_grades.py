"""Face-check the RB v1 grades.

Prints, per season:
  - Top 20 qualified RBs by composite grade
  - A few explicit name checks (Barkley, Henry, Gibbs, CMC, ...) so we
    catch grader weirdness on known players
  - Bottom of the qualified list (noise check)

Run:
    python scripts/verify_rb_grades.py
    SEASONS="2022 2023 2024 2025" python scripts/verify_rb_grades.py
"""

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
            _section(f"SEASON {season}")
            _counts(conn, season)
            _top_grades(conn, season, 20)
            _focus_rbs(conn, season)
            _bottom_grades(conn, season, 10)


def _section(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def _counts(conn, season: int) -> None:
    row = conn.execute(
        text("""
        SELECT
            COUNT(*) FILTER (WHERE qualified)     AS qualified,
            COUNT(*) FILTER (WHERE NOT qualified) AS unqualified,
            ROUND(AVG(composite_grade) FILTER (WHERE qualified)::numeric, 1) AS avg_grade_qual,
            ROUND(AVG(composite_grade)::numeric, 1)                          AS avg_grade_all
        FROM season_grades
        WHERE season = :s AND position = 'RB'
    """),
        {"s": season},
    ).first()
    if row:
        print(
            f"qualified={row[0]} unqualified={row[1]}  "
            f"mean grade (qual)={row[2]}  mean (all)={row[3]}"
        )


# Columns used by the top/bottom listings. Pulled once via a big
# aggregate to keep the script readable.
_LEADERBOARD_SQL = text("""
    WITH components AS (
        SELECT
            sg.player_id, sg.season,
            sg.composite_grade, sg.composite_z, sg.percentile,
            sg.qualified,
            MAX(CASE WHEN sc.component_name = 'rb_ryoe_per_attempt'
                     THEN sc.raw_value END)       AS ryoe_per_att,
            MAX(CASE WHEN sc.component_name = 'rb_rush_epa_per_attempt'
                     THEN sc.raw_value END)       AS rush_epa,
            MAX(CASE WHEN sc.component_name = 'rb_rush_success_rate'
                     THEN sc.raw_value END)       AS rush_succ,
            MAX(CASE WHEN sc.component_name = 'rb_rec_epa_per_target'
                     THEN sc.raw_value END)       AS rec_epa,
            MAX(CASE WHEN sc.component_name = 'rb_yac_over_expected_per_rec'
                     THEN sc.raw_value END)       AS yac_over_exp,
            MAX(CASE WHEN sc.component_name = 'rb_catch_pct'
                     THEN sc.raw_value END)       AS catch_pct,
            MAX(CASE WHEN sc.component_name = 'rb_fumble_rate'
                     THEN sc.raw_value END)       AS fumble_rate,
            MAX(CASE WHEN sc.component_name = 'rb_ryoe_per_attempt'
                     THEN sc.sample_size END)     AS n_carries,
            MAX(CASE WHEN sc.component_name = 'rb_rec_epa_per_target'
                     THEN sc.sample_size END)     AS n_targets,
            MAX(CASE WHEN sc.component_name = 'rb_fumble_rate'
                     THEN sc.sample_size END)     AS n_touches
        FROM season_grades sg
        JOIN stat_components sc
          ON sc.player_id = sg.player_id
         AND sc.season = sg.season
        WHERE sg.position = 'RB'
          AND sg.season = :s
          AND sc.component_name LIKE 'rb_%'
        GROUP BY sg.player_id, sg.season, sg.composite_grade,
                 sg.composite_z, sg.percentile, sg.qualified
    )
    SELECT
        p.full_name,
        (SELECT MODE() WITHIN GROUP (ORDER BY pl.posteam)
         FROM plays pl
         WHERE pl.season = c.season
           AND (pl.rusher_player_id = p.gsis_id
                OR pl.receiver_player_id = p.gsis_id))  AS team,
        c.composite_grade, c.composite_z, c.percentile, c.qualified,
        c.n_carries, c.n_targets, c.n_touches,
        c.ryoe_per_att, c.rush_epa, c.rush_succ,
        c.rec_epa, c.yac_over_exp, c.catch_pct, c.fumble_rate
    FROM components c
    JOIN players p ON p.player_id = c.player_id
""")


def _fmt_num(val, *, width: int, prec: int, plus: bool = False) -> str:
    if val is None:
        return f"{'--':<{width}}"
    # Python format spec order: [[fill]align][sign][#][0][width][,][.precision][type]
    sign = "+" if plus else ""
    formatted = f"{val:{sign}.{prec}f}"
    return f"{formatted:<{width}}"


def _top_grades(conn, season: int, n: int) -> None:
    print(f"\nTop {n} qualified RBs:")
    print(
        f"  {'#':<3} {'RB':<22} {'Tm':<4} "
        f"{'Car':<4} {'Tgt':<4} {'Tch':<4} "
        f"{'Grade':<6} {'Pct':<6} "
        f"{'RYOE/a':<7} {'EPA/a':<7} {'Rec EPA':<8} "
        f"{'YAC/e':<7} {'Catch%':<7} {'Fum%':<6}"
    )
    rows = conn.execute(
        text(_LEADERBOARD_SQL.text + " WHERE c.qualified ORDER BY c.composite_grade DESC LIMIT :n"),
        {"s": season, "n": n},
    ).all()
    for i, r in enumerate(rows, start=1):
        (
            name,
            team,
            grade,
            _z,
            pct,
            _qual,
            n_car,
            n_tgt,
            n_tch,
            ryoe,
            rush_epa,
            _rush_succ,
            rec_epa,
            yac_over_exp,
            catch_pct,
            fumble_rate,
        ) = r
        print(
            f"  {i:<3} {name:<22.22} {team or '--':<4} "
            f"{n_car or 0:<4} {n_tgt or 0:<4} {n_tch or 0:<4} "
            f"{grade:<6.1f} {pct:<6.1f} "
            f"{_fmt_num(ryoe, width=7, prec=2, plus=True)} "
            f"{_fmt_num(rush_epa, width=7, prec=3, plus=True)} "
            f"{_fmt_num(rec_epa, width=8, prec=3, plus=True)} "
            f"{_fmt_num(yac_over_exp, width=7, prec=2, plus=True)} "
            f"{_fmt_num(catch_pct * 100 if catch_pct is not None else None, width=7, prec=1)} "
            f"{_fmt_num(fumble_rate * 100 if fumble_rate is not None else None, width=6, prec=2)}"
        )


def _focus_rbs(conn, season: int) -> None:
    # Look up by full_name + position='RB'. If a name matches multiple
    # players we print them all (helps catch the "two Josh Jacobs" case).
    focus_names = [
        "Saquon Barkley",
        "Derrick Henry",
        "Jahmyr Gibbs",
        "Christian McCaffrey",
        "Bijan Robinson",
        "James Cook",
        "Kyren Williams",
        "Josh Jacobs",
        "Chuba Hubbard",
        "De'Von Achane",
        "Joe Mixon",
        "Alvin Kamara",
    ]
    print("\nFocus RBs:")
    print(
        f"  {'RB':<22} {'Grade':<6} {'Pct':<6} {'Qual':<5} "
        f"{'Car':<4} {'Tgt':<4} {'Tch':<4} {'RYOE/a':<7} {'EPA/a':<7} "
        f"{'Rec EPA/t':<10}"
    )
    for name in focus_names:
        rows = conn.execute(
            text("""
            SELECT
                p.full_name,
                sg.composite_grade, sg.percentile, sg.qualified,
                MAX(CASE WHEN sc.component_name = 'rb_ryoe_per_attempt'
                         THEN sc.sample_size END)  AS n_carries,
                MAX(CASE WHEN sc.component_name = 'rb_rec_epa_per_target'
                         THEN sc.sample_size END)  AS n_targets,
                MAX(CASE WHEN sc.component_name = 'rb_fumble_rate'
                         THEN sc.sample_size END)  AS n_touches,
                MAX(CASE WHEN sc.component_name = 'rb_ryoe_per_attempt'
                         THEN sc.raw_value END)    AS ryoe_per_att,
                MAX(CASE WHEN sc.component_name = 'rb_rush_epa_per_attempt'
                         THEN sc.raw_value END)    AS rush_epa,
                MAX(CASE WHEN sc.component_name = 'rb_rec_epa_per_target'
                         THEN sc.raw_value END)    AS rec_epa
            FROM season_grades sg
            JOIN players p ON p.player_id = sg.player_id
            LEFT JOIN stat_components sc
                   ON sc.player_id = sg.player_id AND sc.season = sg.season
            WHERE sg.season = :s AND sg.position = 'RB'
              AND p.full_name = :name
            GROUP BY p.full_name, sg.composite_grade, sg.percentile, sg.qualified
            ORDER BY sg.composite_grade DESC
        """),
            {"s": season, "name": name},
        ).all()
        if not rows:
            print(f"  {name:<22} -- (no grade row)")
            continue
        for r in rows:
            (full_name, grade, pct, qual, n_car, n_tgt, n_tch, ryoe, rush_epa, rec_epa) = r
            print(
                f"  {full_name:<22} {grade:<6.1f} {pct:<6.1f} "
                f"{'Y' if qual else 'N':<5} "
                f"{n_car or 0:<4} {n_tgt or 0:<4} {n_tch or 0:<4} "
                f"{_fmt_num(ryoe, width=7, prec=2, plus=True)} "
                f"{_fmt_num(rush_epa, width=7, prec=3, plus=True)} "
                f"{_fmt_num(rec_epa, width=10, prec=3, plus=True)}"
            )


def _bottom_grades(conn, season: int, n: int) -> None:
    print(f"\nBottom {n} qualified RBs (noise check):")
    print(
        f"  {'RB':<22} {'Grade':<6} {'Car':<4} {'Tgt':<4} {'Tch':<4} "
        f"{'RYOE/a':<7} {'EPA/a':<7} {'Fum%':<6}"
    )
    rows = conn.execute(
        text(_LEADERBOARD_SQL.text + " WHERE c.qualified ORDER BY c.composite_grade ASC LIMIT :n"),
        {"s": season, "n": n},
    ).all()
    for r in rows:
        (
            name,
            _team,
            grade,
            _z,
            _pct,
            _qual,
            n_car,
            n_tgt,
            n_tch,
            ryoe,
            rush_epa,
            _rush_succ,
            _rec_epa,
            _yac_over_exp,
            _catch_pct,
            fumble_rate,
        ) = r
        print(
            f"  {name:<22.22} {grade:<6.1f} "
            f"{n_car or 0:<4} {n_tgt or 0:<4} {n_tch or 0:<4} "
            f"{_fmt_num(ryoe, width=7, prec=2, plus=True)} "
            f"{_fmt_num(rush_epa, width=7, prec=3, plus=True)} "
            f"{_fmt_num(fumble_rate * 100 if fumble_rate is not None else None, width=6, prec=2)}"
        )


if __name__ == "__main__":
    main()
