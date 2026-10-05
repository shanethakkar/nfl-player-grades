"""Test 3: odd-week vs even-week split-half reliability for QB/RB/WR/TE (PBP + NGS weekly)."""
import sys
import numpy as np, pandas as pd
from nfl_grades.grading import weights as W
from nfl_grades.grading.empirical_bayes import shrink_series
from common import OUT, REPO
from pbp import load
d = load()
d["half"] = "odd"
sg = pd.read_parquet(OUT/"season_grades.parquet")
qual = sg[sg.qualified][["gsis_id","season","position","player_id"]]

def ngs(kind, valcol, wcol):
    fr = []
    for s in range(2016, 2026):
        x = pd.read_parquet(REPO/f"pipeline/.cache/raw/ngs_{kind}/{s}.parquet")
        x = x[(x.season_type == "REG") & (x.week > 0)]
        fr.append(x[["season","week","player_gsis_id",valcol,wcol]])
    x = pd.concat(fr); x["half"] = "odd"
    x["vw"] = x[valcol]*x[wcol]
    a = x.groupby(["player_gsis_id","season","half"]).agg(vw=("vw","sum"), w=(wcol,"sum")).reset_index()
    a[valcol] = a.vw/a.w
    return a.rename(columns={"player_gsis_id":"gsis"})[["gsis","season","half",valcol,"w"]]

def qb_feats():
    db = d[d.is_db]
    a = db.groupby(["passer_player_id","season","half"]).agg(n_db=("epa","size"), qb_epa_per_dropback=("epa","mean"), qb_success_rate=("success","mean")).reset_index()
    pa = db[db.pass_attempt.fillna(0).astype(bool) & db.cpoe.notna()].groupby(["passer_player_id","season","half"]).agg(qb_cpoe=("cpoe","mean"), n_att=("cpoe","size")).reset_index()
    a = a.merge(pa, how="left").rename(columns={"passer_player_id":"gsis"})
    spec = {"qb_epa_per_dropback":"n_db","qb_cpoe":"n_att","qb_success_rate":"n_db"}
    return a, spec, W.QB_V1_WEIGHTS, W.QB_V1_SHRINKAGE_K

def rec_feats(prefix):
    t = d[d.is_tgt]
    a = t.groupby(["receiver_player_id","season","half"]).agg(n_tgt=("epa","size"), rec_epa=("epa","mean"), succ=("success","mean")).reset_index()
    c = t[t.complete_pass & t.xyac_mean_yardage.notna()].copy(); c["yoe"] = c.yards_after_catch - c.xyac_mean_yardage
    y = c.groupby(["receiver_player_id","season","half"]).agg(yoe=("yoe","mean"), n_xyac=("yoe","size")).reset_index()
    # earn rate: targets / team targeted attempts in games where player had >=1 target
    tg = t.groupby(["posteam","game_id"]).size().rename("team_att").reset_index()
    pg = t[["receiver_player_id","season","half","posteam","game_id"]].drop_duplicates().merge(tg, on=["posteam","game_id"])
    e = pg.groupby(["receiver_player_id","season","half"]).team_att.sum().rename("team_att").reset_index()
    a = a.merge(y, how="left").merge(e, how="left").rename(columns={"receiver_player_id":"gsis"})
    a["earn"] = a.n_tgt/a.team_att
    return a

def rb_feats():
    r = d[d.is_rush]
    a = r.groupby(["rusher_player_id","season","half"]).agg(n_car=("epa","size"), rb_rush_epa_per_attempt=("epa","mean"), rb_rush_success_rate=("success","mean")).reset_index().rename(columns={"rusher_player_id":"gsis"})
    rc = rec_feats("rb")[["gsis","season","half","n_tgt","rec_epa","yoe","n_xyac"]].rename(columns={"rec_epa":"rb_rec_epa_per_target","yoe":"rb_yac_over_expected_per_rec"})
    ry = ngs("rushing","rush_yards_over_expected_per_att","rush_attempts").rename(columns={"rush_yards_over_expected_per_att":"rb_ryoe_per_attempt","w":"n_ngs"})
    a = a.merge(rc, how="left").merge(ry, how="left")
    spec = {"rb_ryoe_per_attempt":"n_ngs","rb_rush_epa_per_attempt":"n_car","rb_rush_success_rate":"n_car","rb_rec_epa_per_target":"n_tgt","rb_yac_over_expected_per_rec":"n_xyac"}
    w = {k: v for k, v in W.RB_V1_WEIGHTS.items() if k in spec}
    return a, spec, w, W.RB_V1_SHRINKAGE_K

def wrte_feats(p):
    a = rec_feats(p)
    sep = ngs("receiving","avg_separation","targets").rename(columns={"avg_separation":"sep","w":"n_ngs"})
    a = a.merge(sep, how="left")
    a = a.rename(columns={"rec_epa":f"{p}_rec_epa_per_target","succ":f"{p}_success_rate_per_target","yoe":f"{p}_yac_over_expected_per_rec","earn":f"{p}_target_earn_rate","sep":f"{p}_separation"})
    spec = {f"{p}_rec_epa_per_target":"n_tgt", f"{p}_success_rate_per_target":"n_tgt", f"{p}_yac_over_expected_per_rec":"n_xyac", f"{p}_target_earn_rate":"team_att", f"{p}_separation":"n_tgt"}
    WT = W.WR_V1_WEIGHTS if p=="wr" else W.TE_V1_WEIGHTS; K = W.WR_V1_SHRINKAGE_K if p=="wr" else W.TE_V1_SHRINKAGE_K
    return a, spec, {k:v for k,v in WT.items() if k in spec}, K

def sb(r): return 2*r/(1+r)
for pos, fn in [("QB", qb_feats), ("RB", rb_feats), ("WR", lambda: wrte_feats("wr")), ("TE", lambda: wrte_feats("te"))]:
    a, spec, w, K = fn()
    coh = qual[qual.position==pos][["gsis_id","season","player_id"]].rename(columns={"gsis_id":"gsis"})
    a = a.merge(coh, on=["gsis","season"])
    zs=[]
    for s, hs in a.groupby("season"):
        hs = hs.copy()
        for c, ncol in spec.items():
            sh = shrink_series(hs[c], hs[ncol].fillna(0), k=K[c]); hs["z_"+c] = (sh-sh.mean())/sh.std(ddof=1)
        zs.append(hs)
    h = pd.concat(zs); wv = pd.Series(w); wv = wv/wv.abs().sum()
    h["comp"] = sum(wv[c]*h["z_"+c].fillna(0) for c in w)
    m = h.merge(sg[sg.position==pos][["player_id","season","composite_z"]], on=["player_id","season"])
    print(pos, len(m), "r(recomputed, production composite_z) =", round(np.corrcoef(m.comp, m.composite_z.astype(float))[0,1],3))
