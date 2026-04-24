"""Read-only sanity check of depth_charts ingestion output."""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import text

from nfl_grades.db import get_engine


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        for season in (2024, 2025):
            print(f"\n{'=' * 72}\nSeason {season}  (week=99 snapshot)\n{'=' * 72}")

            total = c.execute(text(
                "SELECT COUNT(*) FROM depth_charts WHERE season=:s AND week=99"
            ), {"s": season}).scalar()
            teams = c.execute(text(
                "SELECT COUNT(DISTINCT team_id) FROM depth_charts WHERE season=:s AND week=99"
            ), {"s": season}).scalar()
            positions = c.execute(text(
                "SELECT COUNT(DISTINCT position) FROM depth_charts WHERE season=:s AND week=99"
            ), {"s": season}).scalar()
            print(f"  rows={total}  teams={teams}  distinct_positions={positions}")

            print("\n  Starting QBs:")
            for name, team in c.execute(text(
                """
                SELECT p.full_name, t.abbr
                  FROM depth_charts dc
                  JOIN players p ON p.player_id = dc.player_id
                  JOIN teams t ON t.team_id = dc.team_id
                 WHERE dc.season = :s AND dc.week = 99
                   AND dc.position = 'QB' AND dc.depth_order = 1
                 ORDER BY t.abbr
                """
            ), {"s": season}):
                print(f"    {team:<4} {name}")

            print("\n  KC full depth chart (top 3 at each pos):")
            for pos, depth, name in c.execute(text(
                """
                SELECT dc.position, dc.depth_order, p.full_name
                  FROM depth_charts dc
                  JOIN players p ON p.player_id = dc.player_id
                  JOIN teams t ON t.team_id = dc.team_id
                 WHERE dc.season=:s AND dc.week=99 AND t.abbr='KC' AND dc.depth_order<=3
                 ORDER BY dc.position, dc.depth_order
                """
            ), {"s": season}):
                print(f"    {pos:<6} #{depth}  {name}")


if __name__ == "__main__":
    main()
