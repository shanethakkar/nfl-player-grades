"""Face-check the WR v1 grades.

Prints, per season:
  - Top 20 qualified WRs by composite grade
  - A few explicit name checks (Jefferson, Hill, Chase, ...) so we
    catch grader weirdness on known players
  - Archetype spotlights: slot/possession vs deep-threat vs YAC monster
  - Bottom of the qualified list (noise check)

Run:
    python scripts/verify_wr_grades.py
    SEASONS="2022 2023 2024 2025" python scripts/verify_wr_grades.py
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
            _focus_wrs(conn, season)
            _archetype_spotlights(conn, season)
            _bottom_grades(conn, season, 10)


def _section(title: str) -> None:
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


def _counts(conn, season: int) -> None:
    row = conn.execute(
        text("""
        SELECT
            COUNT(*) FILTER (WHERE qualified)     AS qualified,
            COUNT(*) FILTER (WHERE NOT qualified) AS unqualified,
            ROUND(AVG(composite_grade) FILTER (WHERE qualified)::numeric, 1) AS avg_grade_qual,
            ROUND(AVG(composite_grade)::numeric, 1)                          AS avg_grade_all
        FROM season_grades
        WHERE season = :s AND position = 'WR'
    """),
        {"s": season},
    ).first()
    if row:
        print(
            f"qualified={row[0]} unqualified={row[1]}  "
            f"mean grade (qual)={row[2]}  mean (all)={row[3]}"
        )


# One big aggregate keeps the script readable.
_LEADERBOARD_SQL = text("""
    WITH components AS (
        SELECT
            sg.player_id, sg.season,
            sg.composite_grade, sg.composite_z, sg.percentile,
            sg.qualified,
            MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                     THEN sc.raw_value END)       AS rec_epa,
            MAX(CASE WHEN sc.component_name = 'wr_yac_over_expected_per_rec'
                     THEN sc.raw_value END)       AS yac_over_exp,
            MAX(CASE WHEN sc.component_name = 'wr_separation'
                     THEN sc.raw_value END)       AS separation,
            MAX(CASE WHEN sc.component_name = 'wr_target_earn_rate'
                     THEN sc.raw_value END)       AS earn_rate,
            MAX(CASE WHEN sc.component_name = 'wr_success_rate_per_target'
                     THEN sc.raw_value END)       AS succ_rate,
            MAX(CASE WHEN sc.component_name = 'wr_fumble_rate'
                     THEN sc.raw_value END)       AS fumble_rate,
            MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                     THEN sc.sample_size END)     AS n_targets,
            MAX(CASE WHEN sc.component_name = 'wr_fumble_rate'
                     THEN sc.sample_size END)     AS n_receptions
        FROM season_grades sg
        JOIN stat_components sc
          ON sc.player_id = sg.player_id
         AND sc.season = sg.season
        WHERE sg.position = 'WR'
          AND sg.season = :s
          AND sc.component_name LIKE 'wr_%'
        GROUP BY sg.player_id, sg.season, sg.composite_grade,
                 sg.composite_z, sg.percentile, sg.qualified
    )
    SELECT
        p.full_name,
        (SELECT MODE() WITHIN GROUP (ORDER BY pl.posteam)
         FROM plays pl
         WHERE pl.season = c.season
           AND pl.receiver_player_id = p.gsis_id)  AS team,
        c.composite_grade, c.composite_z, c.percentile, c.qualified,
        c.n_targets, c.n_receptions,
        c.rec_epa, c.yac_over_exp, c.separation,
        c.earn_rate, c.succ_rate, c.fumble_rate
    FROM components c
    JOIN players p ON p.player_id = c.player_id
""")


def _fmt_num(val, *, width: int, prec: int, plus: bool = False) -> str:
    if val is None:
        return f"{'--':<{width}}"
    sign = "+" if plus else ""
    formatted = f"{val:{sign}.{prec}f}"
    return f"{formatted:<{width}}"


def _top_grades(conn, season: int, n: int) -> None:
    print(f"\nTop {n} qualified WRs:")
    print(
        f"  {'#':<3} {'WR':<22} {'Tm':<4} "
        f"{'Tgt':<4} {'Rec':<4} "
        f"{'Grade':<6} {'Pct':<6} "
        f"{'EPA/t':<7} {'YAC/e':<7} {'Sep':<5} "
        f"{'Earn%':<6} {'Succ%':<6} {'Fum%':<6}"
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
            n_tgt,
            n_rec,
            rec_epa,
            yac_over_exp,
            separation,
            earn_rate,
            succ_rate,
            fumble_rate,
        ) = r
        print(
            f"  {i:<3} {name:<22.22} {team or '--':<4} "
            f"{n_tgt or 0:<4} {n_rec or 0:<4} "
            f"{grade:<6.1f} {pct:<6.1f} "
            f"{_fmt_num(rec_epa, width=7, prec=3, plus=True)} "
            f"{_fmt_num(yac_over_exp, width=7, prec=2, plus=True)} "
            f"{_fmt_num(separation, width=5, prec=2)} "
            f"{_fmt_num(earn_rate * 100 if earn_rate is not None else None, width=6, prec=1)} "
            f"{_fmt_num(succ_rate * 100 if succ_rate is not None else None, width=6, prec=1)} "
            f"{_fmt_num(fumble_rate * 100 if fumble_rate is not None else None, width=6, prec=2)}"
        )


def _focus_wrs(conn, season: int) -> None:
    """Named-player face check — catches weirdness on well-known WRs."""
    focus_names = [
        "Justin Jefferson",
        "Ja'Marr Chase",
        "Tyreek Hill",
        "CeeDee Lamb",
        "Amon-Ra St. Brown",
        "A.J. Brown",
        "Davante Adams",
        "Puka Nacua",
        "Nico Collins",
        "Malik Nabers",
        "Brian Thomas",
        "Drake London",
        "Jaxon Smith-Njigba",
        "Terry McLaurin",
        "Ladd McConkey",
    ]
    print("\nFocus WRs:")
    print(
        f"  {'WR':<22} {'Grade':<6} {'Pct':<6} {'Qual':<5} "
        f"{'Tgt':<4} {'Rec':<4} {'EPA/t':<7} {'YAC/e':<7} "
        f"{'Sep':<5} {'Earn%':<6}"
    )
    for name in focus_names:
        rows = conn.execute(
            text("""
            SELECT
                p.full_name,
                sg.composite_grade, sg.percentile, sg.qualified,
                MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                         THEN sc.sample_size END)  AS n_targets,
                MAX(CASE WHEN sc.component_name = 'wr_fumble_rate'
                         THEN sc.sample_size END)  AS n_receptions,
                MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                         THEN sc.raw_value END)    AS rec_epa,
                MAX(CASE WHEN sc.component_name = 'wr_yac_over_expected_per_rec'
                         THEN sc.raw_value END)    AS yac_over_exp,
                MAX(CASE WHEN sc.component_name = 'wr_separation'
                         THEN sc.raw_value END)    AS separation,
                MAX(CASE WHEN sc.component_name = 'wr_target_earn_rate'
                         THEN sc.raw_value END)    AS earn_rate
            FROM season_grades sg
            JOIN players p ON p.player_id = sg.player_id
            LEFT JOIN stat_components sc
                   ON sc.player_id = sg.player_id AND sc.season = sg.season
            WHERE sg.season = :s AND sg.position = 'WR'
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
            (
                full_name,
                grade,
                pct,
                qual,
                n_tgt,
                n_rec,
                rec_epa,
                yac_over_exp,
                separation,
                earn_rate,
            ) = r
            print(
                f"  {full_name:<22} {grade:<6.1f} {pct:<6.1f} "
                f"{'Y' if qual else 'N':<5} "
                f"{n_tgt or 0:<4} {n_rec or 0:<4} "
                f"{_fmt_num(rec_epa, width=7, prec=3, plus=True)} "
                f"{_fmt_num(yac_over_exp, width=7, prec=2, plus=True)} "
                f"{_fmt_num(separation, width=5, prec=2)} "
                f"{_fmt_num(earn_rate * 100 if earn_rate is not None else None, width=6, prec=1)}"
            )


def _archetype_spotlights(conn, season: int) -> None:
    """Three-way archetype face check. If any of these look broken
    the weights or filter likely have a problem.

    - Slot/possession: should have high separation, high catch %, low aDOT
    - Deep threat: moderate separation, lower catch %, high per-target EPA
    - YAC monster: high YAC-over-expected, moderate everything else
    """
    archetypes = {
        "Slot/possession": [
            "Amon-Ra St. Brown",
            "Ladd McConkey",
            "Cooper Kupp",
            "Keenan Allen",
        ],
        "Deep threat": [
            "Tyreek Hill",
            "Brian Thomas",
            "D.K. Metcalf",
            "Rashee Rice",
        ],
        "YAC monster": [
            "Deebo Samuel",
            "Puka Nacua",
            "Rashid Shaheed",
            "Jaylen Waddle",
        ],
    }

    print("\nArchetype spotlights:")
    for archetype, names in archetypes.items():
        print(f"\n  [{archetype}]")
        for name in names:
            row = conn.execute(
                text("""
                SELECT sg.composite_grade, sg.percentile, sg.qualified,
                    MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                             THEN sc.raw_value END)    AS rec_epa,
                    MAX(CASE WHEN sc.component_name = 'wr_yac_over_expected_per_rec'
                             THEN sc.raw_value END)    AS yac_over_exp,
                    MAX(CASE WHEN sc.component_name = 'wr_separation'
                             THEN sc.raw_value END)    AS separation,
                    MAX(CASE WHEN sc.component_name = 'wr_rec_epa_per_target'
                             THEN sc.sample_size END)  AS n_targets
                FROM season_grades sg
                JOIN players p ON p.player_id = sg.player_id
                LEFT JOIN stat_components sc
                       ON sc.player_id = sg.player_id AND sc.season = sg.season
                WHERE sg.season = :s AND sg.position = 'WR' AND p.full_name = :name
                GROUP BY sg.composite_grade, sg.percentile, sg.qualified
                ORDER BY sg.composite_grade DESC
                LIMIT 1
            """),
                {"s": season, "name": name},
            ).first()
            if not row:
                print(f"    {name:<24} (no grade)")
                continue
            grade, pct, qual, rec_epa, yac_oe, sep, n_tgt = row
            print(
                f"    {name:<24} grade={grade:<5.1f} pct={pct:<5.1f} "
                f"qual={'Y' if qual else 'N'} "
                f"EPA/t={_fmt_num(rec_epa, width=7, prec=3, plus=True)} "
                f"YAC/e={_fmt_num(yac_oe, width=6, prec=2, plus=True)} "
                f"sep={_fmt_num(sep, width=5, prec=2)} "
                f"tgt={n_tgt or 0}"
            )


def _bottom_grades(conn, season: int, n: int) -> None:
    print(f"\nBottom {n} qualified WRs (noise check):")
    print(
        f"  {'WR':<22} {'Grade':<6} {'Tgt':<4} {'Rec':<4} "
        f"{'EPA/t':<7} {'YAC/e':<7} {'Sep':<5} {'Fum%':<6}"
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
            n_tgt,
            n_rec,
            rec_epa,
            yac_over_exp,
            separation,
            _earn_rate,
            _succ_rate,
            fumble_rate,
        ) = r
        print(
            f"  {name:<22.22} {grade:<6.1f} "
            f"{n_tgt or 0:<4} {n_rec or 0:<4} "
            f"{_fmt_num(rec_epa, width=7, prec=3, plus=True)} "
            f"{_fmt_num(yac_over_exp, width=7, prec=2, plus=True)} "
            f"{_fmt_num(separation, width=5, prec=2)} "
            f"{_fmt_num(fumble_rate * 100 if fumble_rate is not None else None, width=6, prec=2)}"
        )


if __name__ == "__main__":
    main()
