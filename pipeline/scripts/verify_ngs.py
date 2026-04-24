"""Face-check NGS ingest with Mahomes + Barkley + Chase sanity pulls."""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import text

from nfl_grades.db import get_engine


def main() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        print("=" * 70)
        print("NGS row counts by season")
        print("=" * 70)
        for table in ("ngs_passing", "ngs_rushing", "ngs_receiving"):
            print(f"\n{table}:")
            for r in conn.execute(text(
                f"SELECT season, COUNT(*) FILTER (WHERE week=0) AS season_rows, "
                f"COUNT(*) AS all_rows FROM {table} GROUP BY season ORDER BY season"
            )):
                print(f"  season={r[0]}  week=0: {r[1]:<4}  total: {r[2]}")

        print("\n" + "=" * 70)
        print("Mahomes NGS passing (week=0 season summaries)")
        print("=" * 70)
        for r in conn.execute(text("""
            SELECT season, attempts, pass_yards, pass_touchdowns, interceptions,
                   ROUND(avg_time_to_throw::numeric, 2)           AS tt_throw,
                   ROUND(aggressiveness::numeric, 1)              AS aggr,
                   ROUND(completion_percentage::numeric, 1)       AS comp_pct,
                   ROUND(expected_completion_percentage::numeric, 1) AS xcomp,
                   ROUND(completion_percentage_above_expectation::numeric, 2) AS cpoe
            FROM ngs_passing np
            JOIN players p ON p.player_id = np.player_id
            WHERE p.gsis_id = '00-0033873' AND np.week = 0
            ORDER BY season
        """)):
            print(f"  {r[0]}: att={r[1]} yd={r[2]} TD={r[3]} INT={r[4]} "
                  f"TTT={r[5]} aggr={r[6]} comp%={r[7]} xComp%={r[8]} CPOE={r[9]}")

        print("\n" + "=" * 70)
        print("Top 10 RYOE/att (min 100 carries, REG week=0)")
        print("=" * 70)
        for season in (2024, 2025):
            print(f"\n{season}:")
            for r in conn.execute(text("""
                SELECT p.full_name,
                       nr.rush_attempts,
                       nr.rush_yards,
                       ROUND(nr.rush_yards_over_expected_per_att::numeric, 2) AS ryoe_att,
                       ROUND(nr.efficiency::numeric, 2)        AS efficiency
                FROM ngs_rushing nr
                JOIN players p ON p.player_id = nr.player_id
                WHERE nr.season = :s AND nr.week = 0 AND nr.season_type = 'REG'
                  AND nr.rush_attempts >= 100
                ORDER BY nr.rush_yards_over_expected_per_att DESC
                LIMIT 10
            """), {"s": season}):
                print(f"  {r[0]:<22} att={r[1]:<4} yds={r[2]:<5} RYOE/att={r[3]:<5} eff={r[4]}")

        print("\n" + "=" * 70)
        print("Top 10 avg_separation (min 50 targets, REG week=0)")
        print("=" * 70)
        for season in (2024, 2025):
            print(f"\n{season}:")
            for r in conn.execute(text("""
                SELECT p.full_name,
                       nr.targets,
                       ROUND(nr.avg_separation::numeric, 2)             AS sep,
                       ROUND(nr.avg_cushion::numeric, 2)                AS cushion,
                       ROUND(nr.avg_yac_above_expectation::numeric, 2)  AS yac_oe
                FROM ngs_receiving nr
                JOIN players p ON p.player_id = nr.player_id
                WHERE nr.season = :s AND nr.week = 0 AND nr.season_type = 'REG'
                  AND nr.targets >= 50
                ORDER BY nr.avg_separation DESC
                LIMIT 10
            """), {"s": season}):
                print(f"  {r[0]:<22} tgt={r[1]:<4} sep={r[2]:<5} cush={r[3]:<5} YACoE={r[4]}")


if __name__ == "__main__":
    main()
