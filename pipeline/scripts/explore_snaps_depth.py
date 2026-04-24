"""One-shot exploration of load_snap_counts() and load_depth_charts().

Dumps schema + a row sample + key summaries for 2024, to inform the
ingest modules.
"""

from __future__ import annotations

import os

os.environ.setdefault("NFLREADPY_CACHE", "off")
os.environ.setdefault("NFLREADPY_VERBOSE", "False")

import sys

# Force stdout to UTF-8 so we can print names like "De'Von" on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import nflreadpy as nfl
import polars as pl


def summarize(df: pl.DataFrame, name: str) -> None:
    print(f"\n{'=' * 72}\n{name}  shape={df.shape}\n{'=' * 72}")
    print(f"columns ({len(df.columns)}):")
    for col, dtype in zip(df.columns, df.dtypes, strict=True):
        null_pct = df[col].is_null().mean() * 100
        print(f"  {col:<30} {str(dtype):<15}  null%={null_pct:5.1f}")
    print("\nfirst 3 rows (as dicts):")
    for row in df.head(3).to_dicts():
        safe = {k: (str(v).encode("ascii", errors="replace").decode("ascii") if isinstance(v, str) else v) for k, v in row.items()}
        print(" ", safe)


def main() -> None:
    print("nflreadpy version:", getattr(nfl, "__version__", "?"))

    # What ID columns does load_players expose? We need to join snap_counts
    # (keyed on pfr_player_id) back to players (keyed on gsis_id).
    players = nfl.load_players()
    print("\nload_players() columns (all):")
    for col in players.columns:
        print(f"  {col}")
    id_cols = [c for c in players.columns if "id" in c.lower()]
    print(f"\nload_players() id-ish columns: {id_cols}")
    for c in id_cols:
        non_null = (players[c].is_null().mean() * 100)
        print(f"  {c}: null%={non_null:.1f}")

    snaps = nfl.load_snap_counts(seasons=[2024])
    summarize(snaps, "snap_counts 2024")
    pdf = snaps.to_pandas()
    print("\nunique seasons:", sorted(pdf["season"].unique()))
    if "game_type" in pdf.columns:
        print("game_type distribution:")
        print(pdf["game_type"].value_counts())
    print("rows per player (top 3):")
    print(pdf.groupby("pfr_player_id").size().sort_values(ascending=False).head(5))

    # how many total rows per player-season would aggregate?
    print("\nagg sanity: total distinct pfr_player_id:", pdf["pfr_player_id"].nunique())
    if "player" in pdf.columns:
        sample = pdf[pdf["player"].isin(["Patrick Mahomes", "Josh Allen"])]
        print("\nMahomes/Allen rows (sample cols):")
        cols_to_show = [c for c in [
            "season","week","game_type","team","player","pfr_player_id",
            "offense_snaps","offense_pct","defense_snaps","defense_pct",
            "st_snaps","st_pct","position",
        ] if c in sample.columns]
        print(sample[cols_to_show].head(10))

    depth = nfl.load_depth_charts(seasons=[2024])
    summarize(depth, "depth_charts 2024")
    pdf2 = depth.to_pandas()
    print("\nunique weeks:", sorted(pdf2["week"].unique()))
    print("unique game_type / season_type (if present):")
    for col in ("game_type", "season_type"):
        if col in pdf2.columns:
            print(f"  {col}: {pdf2[col].value_counts().to_dict()}")
    print("unique position sample (top 30):")
    if "position" in pdf2.columns:
        print(pdf2["position"].value_counts().head(30))
    if "formation" in pdf2.columns:
        print("formation distribution:")
        print(pdf2["formation"].value_counts().head(10))

    print("\nKC QB rows, latest regular-season week:")
    cols_to_show = [c for c in [
        "season","season_type","week","club_code","team","formation",
        "position","depth_team","player_name","full_name","gsis_id",
    ] if c in pdf2.columns]
    team_col = "club_code" if "club_code" in pdf2.columns else "team"
    reg = pdf2[pdf2.get("season_type", "REG") == "REG"] if "season_type" in pdf2.columns else pdf2
    latest_week = reg["week"].max()
    print(f"  latest REG week: {latest_week}")
    kc_qb = reg[(reg[team_col] == "KC") & (reg["position"] == "QB") & (reg["week"] == latest_week)]
    print(kc_qb[cols_to_show].head(10))


if __name__ == "__main__":
    main()
