"""Exploration: what do nflreadpy.load_rosters and load_players return?

One-shot script that pulls 2024 + 2025 data and prints schema, null patterns,
key uniqueness checks, and side-by-side comparisons against our typed tables
(`players`, `player_seasons`).

Run from `pipeline/`:
    .venv/Scripts/python.exe scripts/explore_rosters.py

Findings inform `ingest/rosters.py` and any schema migrations needed.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

# Disable nflreadpy's built-in cache so we see raw fetch behavior.
os.environ["NFLREADPY_CACHE"] = "off"
os.environ["NFLREADPY_VERBOSE"] = "False"

import nflreadpy as nfl
import pandas as pd
import polars as pl


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def describe(df: pd.DataFrame, name: str) -> None:
    _hr(f"{name} | shape={df.shape}")

    print("\n--- columns + dtypes + null% ---")
    for col in df.columns:
        nulls = df[col].isna().sum()
        pct = 100 * nulls / len(df) if len(df) else 0.0
        sample = df[col].dropna().head(1).tolist()
        sample_str = repr(sample[0])[:50] if sample else "<all null>"
        print(f"  {col:35s} {str(df[col].dtype):12s} {pct:6.2f}% null  e.g. {sample_str}")


def main() -> int:
    _hr("nflreadpy.load_rosters(seasons=[2024, 2025])")
    rosters_pl = nfl.load_rosters(seasons=[2024, 2025])
    print(f"polars shape: {rosters_pl.shape}")
    rosters = rosters_pl.to_pandas()
    describe(rosters, "rosters (combined 2024+2025)")

    print("\n--- per-season row counts ---")
    print(rosters.groupby("season").size().to_string())

    print("\n--- per-team row counts (2024 only) ---")
    r24 = rosters[rosters["season"] == 2024]
    print(r24["team"].value_counts().head(10).to_string())
    print(f"... distinct teams 2024: {r24['team'].nunique()}")

    print("\n--- key uniqueness ---")
    for keyset in [
        ["season", "gsis_id"],
        ["season", "team", "gsis_id"],
        ["season", "team", "jersey_number"],
        ["season", "esb_id"],
    ]:
        if not all(c in rosters.columns for c in keyset):
            print(f"  {keyset}: SKIPPED (missing cols)")
            continue
        n = len(rosters)
        nu = rosters[keyset].drop_duplicates().shape[0]
        dup = n - nu
        print(f"  {keyset}: rows={n} unique={nu} dup_rows={dup}")

    print("\n--- player appearing on multiple teams in a season (traded) ---")
    if "gsis_id" in rosters.columns:
        per_player_season = (
            rosters.dropna(subset=["gsis_id"])
            .groupby(["season", "gsis_id"])["team"]
            .nunique()
        )
        multi = per_player_season[per_player_season > 1]
        print(f"  player-seasons with >1 team: {len(multi)}")
        print(f"  example multi-team rows:")
        if len(multi):
            sample_pid = multi.index[0][1]
            sample_season = multi.index[0][0]
            print(rosters[
                (rosters["gsis_id"] == sample_pid)
                & (rosters["season"] == sample_season)
            ][["season", "team", "full_name", "position", "status", "jersey_number"]].to_string())

    print("\n--- 'status' distribution (active vs IR vs PS, etc.) ---")
    if "status" in rosters.columns:
        print(rosters["status"].value_counts(dropna=False).to_string())

    print("\n--- 'position' distribution ---")
    if "position" in rosters.columns:
        print(rosters["position"].value_counts(dropna=False).head(40).to_string())

    # Players master table
    _hr("nflreadpy.load_players()")
    try:
        players_pl = nfl.load_players()
        print(f"polars shape: {players_pl.shape}")
        players = players_pl.to_pandas()
        describe(players.head(1000), "players (sampled first 1000 rows)")
        print("\n--- key uniqueness on full table ---")
        for keyset in [["gsis_id"], ["esb_id"], ["nfl_id"], ["pfr_id"]]:
            if not all(c in players.columns for c in keyset):
                print(f"  {keyset}: SKIPPED")
                continue
            nu = players[keyset].dropna().drop_duplicates().shape[0]
            present = players[keyset[0]].notna().sum()
            print(f"  {keyset}: present={present} unique_among_present={nu}")
    except Exception as e:
        print(f"load_players failed: {type(e).__name__}: {e}")

    # Cross-check: which roster columns also appear on players?
    _hr("Roster columns ALSO in players (= player-level, time-invariant)")
    try:
        common = sorted(set(rosters.columns) & set(players.columns))
        only_roster = sorted(set(rosters.columns) - set(players.columns))
        only_players = sorted(set(players.columns) - set(rosters.columns))
        print(f"\nIn BOTH rosters and players ({len(common)}):")
        for c in common:
            print(f"  {c}")
        print(f"\nIn rosters ONLY ({len(only_roster)}) -- candidates for player_seasons:")
        for c in only_roster:
            print(f"  {c}")
        print(f"\nIn players ONLY ({len(only_players)}) -- master only:")
        for c in only_players:
            print(f"  {c}")
    except NameError:
        pass

    # Schema mapping suggestion
    _hr("Schema mapping (rosters/players -> our tables)")
    print("""
Our `players` table columns:
    player_id (surrogate)         <- generated
    gsis_id                       <- rosters/players.gsis_id
    full_name                     <- rosters/players.full_name (or players.display_name)
    position                      <- rosters.position (current season's position)
    birth_date                    <- rosters/players.birth_date
    height_inches                 <- rosters/players.height (inches as int)
    weight_lbs                    <- rosters/players.weight
    draft_year                    <- rosters/players.draft_year? OR players.entry_year
    draft_round                   <- rosters/players.draft_round
    draft_pick                    <- rosters/players.draft_number
    current_team_id               <- latest season's rosters.team -> teams.team_id
    last_updated                  <- now()

Our `player_seasons` table columns:
    player_id                     <- FK from players (via gsis_id)
    season                        <- rosters.season
    team_id                       <- rosters.team -> team_aliases -> teams.team_id
    position_played               <- rosters.position
    games                         <- NOT in rosters; comes from snap_counts or PBP
    games_started                 <- NOT in rosters; comes from snap_counts
    snaps_offense/defense/special <- comes from snap_counts (separate ingest)

=> rosters alone gives us players + the (player, season, team) skeleton of
   player_seasons. Snap counts come in a later ingest module that fills in
   the games/snaps columns.
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
