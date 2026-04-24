"""Face-check the plays table.

Runs a battery of sanity queries against the populated plays table and
prints the results. Useful after a fresh ingest to confirm that the
data lines up with well-known external benchmarks (e.g. ESPN / PFR).
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
            _top_qbs(conn, season)
            _top_rushers(conn, season)
            _top_receivers(conn, season)
            _mahomes_drilldown(conn, season)


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def _counts(conn, season: int) -> None:
    row = conn.execute(text("""
        SELECT
          COUNT(*) FILTER (WHERE season_type='REG')                           AS reg_rows,
          COUNT(*) FILTER (WHERE season_type='POST')                          AS post_rows,
          COUNT(*) FILTER (WHERE qb_dropback)                                 AS dropbacks,
          COUNT(*) FILTER (WHERE rush_attempt AND NOT qb_scramble AND NOT qb_kneel) AS non_qb_rushes,
          COUNT(DISTINCT game_id)                                             AS games,
          COUNT(DISTINCT passer_player_id) FILTER (WHERE qb_dropback)         AS distinct_qbs,
          COUNT(DISTINCT rusher_player_id) FILTER (WHERE rush_attempt)        AS distinct_rushers,
          COUNT(DISTINCT receiver_player_id) FILTER (WHERE pass_attempt AND receiver_player_id IS NOT NULL) AS distinct_receivers,
          ROUND(AVG(epa)::numeric, 4)                                         AS mean_epa,
          ROUND(AVG(epa) FILTER (WHERE qb_dropback)::numeric, 4)              AS mean_epa_db
        FROM plays
        WHERE season = :s
    """), {"s": season}).mappings().first()
    print()
    for k, v in row.items():
        print(f"  {k:<22} {v}")


def _top_qbs(conn, season: int) -> None:
    print("\n  Top 10 QBs by EPA/dropback (min 200 dropbacks, REG only):")
    rows = conn.execute(text("""
        SELECT
          p.full_name,
          MODE() WITHIN GROUP (ORDER BY pl.posteam) AS team,
          COUNT(*)                           AS dropbacks,
          ROUND(AVG(pl.epa)::numeric, 3)     AS epa_per_db,
          ROUND(AVG(pl.cpoe)::numeric, 2)    AS cpoe,
          ROUND((AVG(pl.success::int))::numeric, 3) AS success_rate
        FROM plays pl
        JOIN players p ON p.gsis_id = pl.passer_player_id
        WHERE pl.season = :s AND pl.season_type = 'REG' AND pl.qb_dropback
        GROUP BY p.full_name
        HAVING COUNT(*) >= 200
        ORDER BY epa_per_db DESC
        LIMIT 10
    """), {"s": season}).all()
    for r in rows:
        print(f"    {r[0]:<22} {r[1]:<4} dropbacks={r[2]:<4} EPA/db={r[3]:<7} CPOE={r[4]:<6} success={r[5]}")


def _top_rushers(conn, season: int) -> None:
    print("\n  Top 10 non-QB rushers by carries (REG only):")
    rows = conn.execute(text("""
        SELECT
          p.full_name,
          MODE() WITHIN GROUP (ORDER BY pl.posteam) AS team,
          COUNT(*)                           AS carries,
          SUM(pl.yards_gained)               AS yards,
          ROUND(AVG(pl.yards_gained)::numeric, 2) AS ypc,
          ROUND(AVG(pl.epa)::numeric, 3)     AS epa_per_carry,
          ROUND((AVG(pl.success::int))::numeric, 3) AS success_rate
        FROM plays pl
        JOIN players p ON p.gsis_id = pl.rusher_player_id
        WHERE pl.season = :s AND pl.season_type = 'REG'
          AND pl.rush_attempt AND NOT pl.qb_scramble AND NOT pl.qb_kneel
        GROUP BY p.full_name
        ORDER BY carries DESC
        LIMIT 10
    """), {"s": season}).all()
    for r in rows:
        print(f"    {r[0]:<22} {r[1]:<4} carries={r[2]:<4} yards={r[3]:<5} ypc={r[4]:<5} EPA/car={r[5]:<7} success={r[6]}")


def _top_receivers(conn, season: int) -> None:
    print("\n  Top 10 receivers by targets (REG only):")
    rows = conn.execute(text("""
        SELECT
          p.full_name,
          MODE() WITHIN GROUP (ORDER BY pl.posteam) AS team,
          COUNT(*)                                              AS targets,
          SUM(pl.complete_pass::int)                            AS catches,
          SUM(pl.yards_gained) FILTER (WHERE pl.complete_pass)  AS rec_yards,
          ROUND(AVG(pl.epa)::numeric, 3)                        AS epa_per_target
        FROM plays pl
        JOIN players p ON p.gsis_id = pl.receiver_player_id
        WHERE pl.season = :s AND pl.season_type = 'REG'
          AND pl.pass_attempt
        GROUP BY p.full_name
        ORDER BY targets DESC
        LIMIT 10
    """), {"s": season}).all()
    for r in rows:
        print(f"    {r[0]:<22} {r[1]:<4} tgt={r[2]:<4} rec={r[3]:<4} yds={r[4]:<5} EPA/tgt={r[5]}")


def _mahomes_drilldown(conn, season: int) -> None:
    print("\n  Mahomes top-5 EPA plays:")
    rows = conn.execute(text("""
        SELECT week, qtr, down, ydstogo, yardline_100,
               ROUND(epa::numeric, 2) AS epa, play_desc
        FROM plays
        WHERE season = :s AND passer_player_id = '00-0033873'
          AND qb_dropback
        ORDER BY epa DESC NULLS LAST
        LIMIT 5
    """), {"s": season}).all()
    for r in rows:
        desc = (r[6] or "")[:90]
        print(f"    wk{r[0]} q{r[1]} {r[2] or '-'}&{r[3]:<2} @{r[4] or '-':<3} EPA={r[5]:<5}  {desc}")


if __name__ == "__main__":
    main()
