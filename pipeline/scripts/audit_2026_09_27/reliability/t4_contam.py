"""Test 4: component-level team contamination (WR/TE vs QB quality; CB vs team pass rush; S/LB too)."""
import numpy as np, pandas as pd
from scipy.stats import pearsonr
from common import OUT, REPO
from pbp import load
d = load()
sg = pd.read_parquet(OUT/"season_grades.parquet"); sc = pd.read_parquet(OUT/"stat_components.parquet")
ps = pd.read_parquet(OUT/"player_seasons.parquet").drop_duplicates(["player_id","season"])
raw = sc.pivot_table(index=["player_id","season"], columns="component_name", values="raw_value", aggfunc="first").reset_index()
db = d[d.is_db]
team_db = db.groupby(["season","posteam"]).agg(t_n=("epa","size"), t_epa=("epa","sum")).reset_index()
# receiver's dropbacks-targeted (to leave out)
rt = db[db.receiver_player_id.notna()].groupby(["season","posteam","receiver_player_id"]).agg(r_n=("epa","size"), r_epa=("epa","sum")).reset_index()
tg = d[d.is_tgt].groupby(["receiver_player_id","season","posteam"]).size().rename("n").reset_index()
prim = tg.sort_values("n").drop_duplicates(["receiver_player_id","season"], keep="last")
# primary QB raw epa/db from production
qbc = db.groupby(["season","posteam","passer_player_id"]).size().rename("n").reset_index()
pqb = qbc.sort_values("n").drop_duplicates(["season","posteam"], keep="last").rename(columns={"passer_player_id":"qb_gsis"})
qbraw = sg[sg.position=="QB"][["player_id","season","gsis_id","composite_z"]].merge(raw[["player_id","season","qb_epa_per_dropback","qb_cpoe"]], on=["player_id","season"])
out=[]
def rep(pos, lab, x, y):
    ok = x.notna() & y.notna(); r = pearsonr(x[ok], y[ok])[0]
    out.append(dict(pos=pos, pair=lab, n=int(ok.sum()), r=r, R2=r*r))
for pos, p in [("WR","wr"),("TE","te")]:
    g = sg[(sg.position==pos)&sg.qualified][["player_id","season","gsis_id","composite_z","composite_grade"]].merge(raw, on=["player_id","season"])
    g = g.merge(prim[["receiver_player_id","season","posteam"]], left_on=["gsis_id","season"], right_on=["receiver_player_id","season"])
    g = g.merge(team_db, on=["season","posteam"]).merge(rt, on=["season","posteam","receiver_player_id"], how="left")
    g["loo_team_epa_db"] = (g.t_epa - g.r_epa.fillna(0))/(g.t_n - g.r_n.fillna(0))
    g = g.merge(pqb[["season","posteam","qb_gsis"]], on=["season","posteam"]).merge(qbraw.rename(columns={"gsis_id":"qb_gsis","composite_z":"qb_cz","qb_epa_per_dropback":"qb_epa","qb_cpoe":"qb_cpoe_q"})[["qb_gsis","season","qb_epa","qb_cpoe_q","qb_cz"]], on=["qb_gsis","season"], how="left")
    for comp in [f"{p}_rec_epa_per_target", f"{p}_success_rate_per_target", f"{p}_target_earn_rate", f"{p}_yac_over_expected_per_rec", f"{p}_separation"]:
        rep(pos, f"{comp} ~ team EPA/db (leave-receiver-out)", g[comp], g.loo_team_epa_db)
    rep(pos, f"{p}_rec_epa_per_target ~ primary QB raw EPA/db (prod)", g[f"{p}_rec_epa_per_target"], g.qb_epa)
    rep(pos, f"{p}_rec_epa_per_target ~ primary QB CPOE", g[f"{p}_rec_epa_per_target"], g.qb_cpoe_q)
    rep(pos, "composite_z ~ team EPA/db (leave-receiver-out)", g.composite_z.astype(float), g.loo_team_epa_db)
    rep(pos, "composite_z ~ primary QB composite_z", g.composite_z.astype(float), g.qb_cz.astype(float))
# CB / S / LB: passer_rating_allowed vs team pressure proxy
cols = ["season","season_type","defteam","qb_dropback","sack","qb_hit","two_point_attempt","aborted_play"]
fr=[]
for s in range(2016,2026):
    x = pd.read_parquet(REPO/f"pipeline/.cache/raw/pbp/{s}.parquet", columns=cols); x = x[(x.season_type=="REG") & (x.qb_dropback==1)]
    fr.append(x)
x = pd.concat(fr); x["pr"] = ((x.sack.fillna(0)+x.qb_hit.fillna(0))>0).astype(int)
tp = x.groupby(["season","defteam"]).pr.mean().rename("team_pressure").reset_index()
for pos, comp in [("CB","cb_passer_rating_allowed"),("S","s_passer_rating_allowed"),("LB","lb_passer_rating_allowed")]:
    g = sg[(sg.position==pos)&sg.qualified][["player_id","season","composite_z"]].merge(raw[["player_id","season",comp]], on=["player_id","season"])
    g = g.merge(ps[["player_id","season","abbr"]], on=["player_id","season"]).merge(tp, left_on=["season","abbr"], right_on=["season","defteam"])
    rep(pos, f"{comp} ~ team (sack+hit)/dropback", g[comp], g.team_pressure)
    rep(pos, "composite_z ~ team (sack+hit)/dropback", g.composite_z.astype(float), g.team_pressure)
res = pd.DataFrame(out); pd.set_option("display.width",200); print(res.round(3).to_string(index=False)); res.to_csv(OUT/"t4_contam.csv", index=False)
