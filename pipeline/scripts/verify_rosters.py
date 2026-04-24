"""Read-only sanity check of the rosters ingest output.

Run after `nflgrades ingest rosters --season 2024` and 2025.
"""

from __future__ import annotations

from sqlalchemy import text

from nfl_grades.db import get_engine


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        print("=== Row counts ===")
        for tbl in ("players", "player_seasons", "pipeline_runs"):
            n = c.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            print(f"  {tbl}: {n:,}")

        print("\n=== player_seasons by season ===")
        for season, n in c.execute(text(
            "SELECT season, COUNT(*) FROM player_seasons "
            "GROUP BY season ORDER BY season"
        )):
            print(f"  {season}: {n:,}")

        print("\n=== position_played distribution (2024) ===")
        for pos, n in c.execute(text(
            "SELECT position_played, COUNT(*) "
            "FROM player_seasons WHERE season=2024 "
            "GROUP BY position_played ORDER BY COUNT(*) DESC"
        )):
            print(f"  {pos:>5}: {n:>4}")

        print("\n=== position_played distribution (2025) ===")
        for pos, n in c.execute(text(
            "SELECT position_played, COUNT(*) "
            "FROM player_seasons WHERE season=2025 "
            "GROUP BY position_played ORDER BY COUNT(*) DESC"
        )):
            print(f"  {pos:>5}: {n:>4}")

        print("\n=== Top-team QBs (2024) ===")
        for name, team, _ in c.execute(text(
            """
            SELECT p.full_name, t.abbr, ps.position_played
            FROM player_seasons ps
            JOIN players p ON p.player_id = ps.player_id
            JOIN teams t ON t.team_id = ps.team_id
            WHERE ps.season = 2024
              AND ps.position_played = 'QB'
              AND t.abbr IN ('KC','BAL','BUF','PHI','SF','CIN')
            ORDER BY t.abbr, p.full_name
            """
        )):
            print(f"  {team}: {name}")

        print("\n=== pipeline_runs ===")
        for row in c.execute(text(
            "SELECT run_id, stage, season, status, rows_written, "
            "       EXTRACT(EPOCH FROM (finished_at - started_at))::int AS secs "
            "FROM pipeline_runs ORDER BY run_id"
        )):
            print(
                f"  #{row[0]:>3} {row[1]:<18} season={row[2]} "
                f"status={row[3]:<5} rows={row[4]:>5} secs={row[5]}"
            )

        print("\n=== Roster size sanity (per-team, 2024) ===")
        sizes = list(c.execute(text(
            """
            SELECT t.abbr, COUNT(*) AS n
            FROM player_seasons ps
            JOIN teams t ON t.team_id = ps.team_id
            WHERE ps.season = 2024
            GROUP BY t.abbr
            ORDER BY n DESC
            """
        )))
        sizes_only = [n for _, n in sizes]
        print(f"  teams covered: {len(sizes)}")
        print(f"  min={min(sizes_only)} max={max(sizes_only)} "
              f"avg={sum(sizes_only)/len(sizes_only):.1f}")
        print(f"  smallest: {sizes[-1]}  largest: {sizes[0]}")

        print("\n=== Cross-check: do all 32 teams have rosters in 2024? ===")
        n_teams = c.execute(text(
            "SELECT COUNT(DISTINCT team_id) FROM player_seasons WHERE season=2024"
        )).scalar()
        print(f"  distinct team_id: {n_teams} (expected 32)")

        print("\n=== Players with no current_team_id (should be ~0) ===")
        n_no_team = c.execute(text(
            "SELECT COUNT(*) FROM players WHERE current_team_id IS NULL"
        )).scalar()
        print(f"  no current_team_id: {n_no_team}")


if __name__ == "__main__":
    main()
