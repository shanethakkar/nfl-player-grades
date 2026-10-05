from __future__ import annotations
import pandas as pd, numpy as np
from common import OUT, REPO
COLS = ['season','week','game_id','posteam','defteam','season_type','qb_dropback','aborted_play','two_point_attempt','passer_player_id',
        'rusher_player_id','receiver_player_id','epa','cpoe','success','pass_attempt','rush_attempt','qb_kneel','qb_scramble','qtr',
        'score_differential','game_seconds_remaining','complete_pass','yards_after_catch','xyac_mean_yardage']
def load(seasons=range(2016, 2026)):
    cache = OUT/"pbp_slim.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    fr = []
    for s in seasons:
        d = pd.read_parquet(REPO/f"pipeline/.cache/raw/pbp/{s}.parquet", columns=COLS)
        fr.append(d[d.season_type == "REG"])
    d = pd.concat(fr, ignore_index=True)
    b = lambda c: d[c].fillna(0).astype(bool)
    garbage = ((d.qtr >= 4) & (d.score_differential.abs() > 21)) | ((d.qtr == 4) & (d.game_seconds_remaining < 300) & (d.score_differential.abs() > 14))
    d["garbage"] = garbage
    d["is_db"] = b("qb_dropback") & ~b("aborted_play") & ~b("two_point_attempt") & d.passer_player_id.notna() & ~garbage
    d["is_rush"] = b("rush_attempt") & d.rusher_player_id.notna() & ~b("qb_kneel") & ~b("qb_scramble") & ~b("two_point_attempt") & ~garbage
    d["is_tgt"] = b("pass_attempt") & d.receiver_player_id.notna() & ~b("two_point_attempt") & ~garbage
    d["is_passatt"] = b("pass_attempt") & ~b("two_point_attempt") & ~garbage  # team pass att (receiver not required, as in team_pass_agg? see note)
    d["complete_pass"] = b("complete_pass")
    d = d[d.is_db | d.is_rush | d.is_tgt | d.is_passatt].copy()
    d.to_parquet(cache)
    return d
if __name__ == "__main__":
    d = load(); print(d.shape, d.groupby("season").size().to_dict())
