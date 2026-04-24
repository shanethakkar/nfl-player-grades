"""Short probe to nail down NGS columns before writing migration 0004."""

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


def probe(loader_name: str, fn) -> None:
    print(f"\n{'='*70}\n{loader_name}\n{'='*70}")
    df = fn(seasons=[2024]).to_pandas()
    print(f"shape: {df.shape}")
    print(f"\ncolumns ({len(df.columns)}):")
    for c in df.columns:
        null_pct = df[c].isna().mean() * 100
        sample = df[c].dropna().iloc[0] if df[c].dropna().size else "<all null>"
        print(f"  {c:<35} null={null_pct:5.1f}%   sample={sample}")
    # Week distribution — 0 typically means season summary
    if "week" in df.columns:
        print(f"\nweek distribution: {sorted(df['week'].unique())}")
        print(f"  rows at week=0: {(df['week']==0).sum()}")
        print(f"  rows at week>0: {(df['week']!=0).sum()}")
    # Check grain
    if {"player_gsis_id", "season", "week", "team_abbr"}.issubset(df.columns):
        dup = df.duplicated(subset=["player_gsis_id", "season", "week", "team_abbr"]).sum()
        print(f"dupes on (player,season,week,team): {dup}")


def main() -> None:
    probe("load_nextgen_stats(stat_type='passing')", lambda seasons: nfl.load_nextgen_stats(seasons=seasons, stat_type="passing"))
    probe("load_nextgen_stats(stat_type='rushing')", lambda seasons: nfl.load_nextgen_stats(seasons=seasons, stat_type="rushing"))
    probe("load_nextgen_stats(stat_type='receiving')", lambda seasons: nfl.load_nextgen_stats(seasons=seasons, stat_type="receiving"))


if __name__ == "__main__":
    main()
