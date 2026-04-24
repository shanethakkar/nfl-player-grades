"""Read-only sanity check of snap_counts ingestion output."""

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
            print(f"\n{'=' * 72}\nSeason {season}\n{'=' * 72}")

            total, with_snaps = c.execute(text(
                """
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE games > 0 OR snaps_offense > 0
                                          OR snaps_defense > 0 OR snaps_special > 0)
                  FROM player_seasons WHERE season = :s
                """
            ), {"s": season}).first()
            print(f"player_seasons: {total} total, {with_snaps} with any snaps "
                  f"({100*with_snaps/total:.1f}%)")

            print("\nTop 5 offensive workload (any position):")
            for name, pos, team, g, snaps in c.execute(text(
                """
                SELECT p.full_name, ps.position_played, t.abbr,
                       ps.games, ps.snaps_offense
                  FROM player_seasons ps
                  JOIN players p ON p.player_id = ps.player_id
                  JOIN teams t ON t.team_id = ps.team_id
                 WHERE ps.season = :s
                 ORDER BY ps.snaps_offense DESC
                 LIMIT 5
                """
            ), {"s": season}):
                print(f"  {name:<24} {pos:<4} {team:<4} "
                      f"games={g:>2}  off_snaps={snaps}")

            print("\nTop 5 defensive workload:")
            for name, pos, team, g, snaps in c.execute(text(
                """
                SELECT p.full_name, ps.position_played, t.abbr,
                       ps.games, ps.snaps_defense
                  FROM player_seasons ps
                  JOIN players p ON p.player_id = ps.player_id
                  JOIN teams t ON t.team_id = ps.team_id
                 WHERE ps.season = :s
                 ORDER BY ps.snaps_defense DESC
                 LIMIT 5
                """
            ), {"s": season}):
                print(f"  {name:<24} {pos:<4} {team:<4} "
                      f"games={g:>2}  def_snaps={snaps}")

            print("\nStarting QBs (games_started >= 10):")
            for name, team, g, gs, snaps in c.execute(text(
                """
                SELECT p.full_name, t.abbr,
                       ps.games, ps.games_started, ps.snaps_offense
                  FROM player_seasons ps
                  JOIN players p ON p.player_id = ps.player_id
                  JOIN teams t ON t.team_id = ps.team_id
                 WHERE ps.season = :s
                   AND ps.position_played = 'QB'
                   AND ps.games_started >= 10
                 ORDER BY ps.games_started DESC, ps.snaps_offense DESC
                 LIMIT 20
                """
            ), {"s": season}):
                print(f"  {name:<24} {team:<4} g={g:>2}  started={gs:>2}  "
                      f"off_snaps={snaps}")


if __name__ == "__main__":
    main()
