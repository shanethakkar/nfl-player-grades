"""One-shot probe of load_pbp() so the plays-table schema is grounded in
reality. Outputs:

- total column count + column names
- which of our target columns exist / are missing
- row counts per season_type
- a few sanity facts (Mahomes EPA, etc.)
"""

from __future__ import annotations

import os
import sys

os.environ["NFLREADPY_CACHE"] = "off"
os.environ["NFLREADPY_VERBOSE"] = "False"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import nflreadpy as nfl

TARGET_COLUMNS = [
    # identifiers
    "game_id", "play_id",
    # context
    "season", "season_type", "week", "game_date",
    "posteam", "defteam", "home_team", "away_team",
    # situation
    "qtr", "down", "ydstogo", "yardline_100", "score_differential",
    "game_seconds_remaining", "half_seconds_remaining", "wp",
    # classification
    "play_type", "qb_dropback", "pass_attempt", "rush_attempt",
    "sack", "qb_scramble", "qb_spike", "qb_kneel", "aborted_play",
    "two_point_attempt", "penalty",
    # player attribution (gsis_ids)
    "passer_player_id", "rusher_player_id", "receiver_player_id",
    "sack_player_id", "interception_player_id",
    # outcomes
    "yards_gained", "epa", "wpa", "cpoe", "success",
    "air_yards", "yards_after_catch",
    "complete_pass", "incomplete_pass", "interception", "fumble_lost",
    "pass_touchdown", "rush_touchdown", "touchdown",
    # debugging
    "desc",
]


def main() -> None:
    print("fetching PBP 2024 ...")
    pl_df = nfl.load_pbp(seasons=[2024])
    print(f"shape: {pl_df.shape}")
    all_cols = set(pl_df.columns)
    print(f"total columns available: {len(all_cols)}")
    print()

    have = [c for c in TARGET_COLUMNS if c in all_cols]
    miss = [c for c in TARGET_COLUMNS if c not in all_cols]
    print(f"target columns we want ({len(TARGET_COLUMNS)}):")
    print(f"  present: {len(have)}")
    print(f"  missing: {len(miss)} -> {miss}")
    print()

    df = pl_df.to_pandas()

    # Season-type + week distribution
    print("season_type counts:")
    print(" ", df["season_type"].value_counts().to_dict())
    print(f"REG week range: {sorted(df[df['season_type']=='REG']['week'].unique())}")
    print()

    # Dropback counts for the QB formula sanity
    reg = df[df["season_type"] == "REG"].copy()
    drops = reg[reg["qb_dropback"] == 1]
    print(f"REG rows:          {len(reg):>7}")
    print(f"  qb_dropback==1:  {len(drops):>7}")
    print(f"  sacks:           {int(drops['sack'].sum()):>7}")
    print(f"  scrambles:       {int(drops['qb_scramble'].sum()):>7}")
    print(f"  pass_attempt==1: {int(drops['pass_attempt'].sum()):>7}")

    # Mahomes EPA sanity
    print()
    print("Mahomes 2024 REG dropbacks:")
    m = drops[drops["passer_player_id"] == "00-0033873"]
    print(f"  dropbacks: {len(m)}")
    print(f"  mean EPA/db: {m['epa'].mean():.4f}")
    print(f"  mean CPOE: {m['cpoe'].mean():.4f}")
    print(f"  success rate: {m['success'].mean():.4f}")

    # Column nullability on the target set
    print()
    print("null % for each target column present:")
    for c in have:
        null_pct = df[c].is_null().mean() if hasattr(df[c], "is_null") else df[c].isna().mean()
        null_pct_f = float(null_pct) * 100
        print(f"  {c:<30} {null_pct_f:5.1f}%")


if __name__ == "__main__":
    main()
