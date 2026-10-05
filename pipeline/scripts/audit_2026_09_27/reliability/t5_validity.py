"""Test 5: Pro Bowl validity (same vs next season), SE of r, bootstrap of weight-change deltas, reputation-free targets."""
import sys
import numpy as np, pandas as pd
from nfl_grades.grading.validity import normalize_name
from nfl_grades.grading import weights as W
from nfl_grades.grading.sigmoid import to_grade
from common import OUT, REPO
rng = np.random.default_rng(7)
sg = pd.read_parquet(OUT/"season_grades.parquet"); sc = pd.read_parquet(OUT/"stat_components.parquet")
pb = pd.read_csv(REPO/"pipeline/data/pro_bowl_selections.csv"); pb["nn"] = pb.name.apply(normalize_name)
pbset = set(zip(pb.nn, pb.season))
g = sg[sg.qualified & sg.composite_grade.notna()].copy()
g["nn"] = g.full_name.apply(normalize_name); g["grade"] = g.composite_grade.astype(float)
g["pb_same"] = [int((n, s) in pbset) for n, s in zip(g.nn, g.season)]
g["pb_next"] = [int((n, s+1) in pbset) for n, s in zip(g.nn, g.season)]
def se(r, n): return (1-r*r)/np.sqrt(n-1)
rows=[]
for pos, x in g.groupby("position"):
    xs = x[x.season.between(2018, 2024)]; xn = x[x.season.between(2017, 2023)]
    rs = xs.grade.corr(xs.pb_same); rn = xn.grade.corr(xn.pb_next)
    per = xs.groupby("season").pb_same.sum()
    rows.append(dict(pos=pos, n_same=len(xs), pb_same=int(xs.pb_same.sum()), pb_per_season=round(per.mean(),1), r_same=rs, se_same=se(rs,len(xs)),
                     n_next=len(xn), pb_next=int(xn.pb_next.sum()), r_next=rn, se_next=se(rn,len(xn))))
v = pd.DataFrame(rows); pd.set_option("display.width",220); print(v.round(3).to_string(index=False)); v.to_csv(OUT/"t5_validity.csv", index=False)

# Bootstrap: is a historical weight tweak's validity delta distinguishable from noise? (paired, player-cluster bootstrap)
zw = sc.pivot_table(index=["player_id","season"], columns="component_name", values="z_score", aggfunc="first")
def comp(sub, w):
    Z = sub[list(w)].fillna(0.0).to_numpy(); wv = np.array(list(w.values())); wv = wv/np.abs(wv).sum()
    return to_grade(Z@wv)
tweaks = {
  "QB v1.0->v1.1 (success .25->.10)": ("QB", {"qb_epa_per_dropback":.5,"qb_cpoe":.25,"qb_success_rate":.25}, W.QB_V1_WEIGHTS),
  "WR v1.2->v1.3 (earn .10->.15, succ .08->.05)": ("WR", {**W.WR_V1_WEIGHTS, "wr_target_earn_rate":.10, "wr_success_rate_per_target":.08}, W.WR_V1_WEIGHTS),
  "CB v1.1->v1.2 (target_rate .08->.05)": ("CB", {**W.CB_V1_WEIGHTS, "cb_target_rate":-.08}, W.CB_V1_WEIGHTS),
  "LB v1.1->v1.2": ("LB", {**W.LB_V1_WEIGHTS, "lb_passer_rating_allowed":-.27, "lb_pressure_rate":.07}, W.LB_V1_WEIGHTS),
  "EDGE add tackles/snap .05": ("EDGE", {k:v for k,v in W.EDGE_V1_WEIGHTS.items() if k!="edge_tackles_per_snap"}, W.EDGE_V1_WEIGHTS),
}
brow=[]
for lab,(pos,wold,wnew) in tweaks.items():
    x = g[(g.position==pos)&g.season.between(2017,2023)].set_index(["player_id","season"]).join(zw, how="left").reset_index()
    a, b, y = comp(x, wold), comp(x, wnew), x.pb_next.to_numpy()
    d0 = np.corrcoef(b,y)[0,1]-np.corrcoef(a,y)[0,1]
    pids = x.player_id.to_numpy(); up = np.unique(pids); idx = {p: np.where(pids==p)[0] for p in up}
    ds=[]
    for _ in range(2000):
        ii = np.concatenate([idx[p] for p in rng.choice(up, len(up))])
        ds.append(np.corrcoef(b[ii],y[ii])[0,1]-np.corrcoef(a[ii],y[ii])[0,1])
    ds=np.array(ds)
    brow.append(dict(tweak=lab, n=len(x), r_old=np.corrcoef(a,y)[0,1], r_new=np.corrcoef(b,y)[0,1], delta=d0, boot_se=ds.std(), ci_lo=np.percentile(ds,2.5), ci_hi=np.percentile(ds,97.5), p_delta_le0=(ds<=0).mean(), r_old_new=np.corrcoef(a,b)[0,1]))
bt = pd.DataFrame(brow); print(bt.round(4).to_string(index=False)); bt.to_csv(OUT/"t5_bootstrap.csv", index=False)

# (d) reputation-free predictive targets: grade N -> primary raw component N+1, vs component N -> component N+1
prim = {"QB":"qb_epa_per_dropback","RB":"rb_rush_epa_per_attempt","WR":"wr_rec_epa_per_target","TE":"te_rec_epa_per_target","CB":"cb_passer_rating_allowed",
        "S":"s_passer_rating_allowed","EDGE":"edge_pressure_rate","iDL":"idl_pressure_rate","LB":"lb_tfl_rate","K":"k_fg_over_expected_per_att","P":"p_net_avg"}
raw = sc.pivot_table(index=["player_id","season"], columns="component_name", values="raw_value", aggfunc="first").reset_index()
out=[]
for pos, c in prim.items():
    x = g[g.position==pos][["player_id","season","grade"]].merge(raw[["player_id","season",c]], on=["player_id","season"])
    y = x.copy(); y["season"] -= 1
    m = x.merge(y, on=["player_id","season"], suffixes=("","_n1"))
    out.append(dict(pos=pos, primary=c, n=len(m), r_grade_to_prim_n1=m.grade.corr(m[c+"_n1"]), r_prim_to_prim_n1=m[c].corr(m[c+"_n1"]), r_grade_to_grade_n1=m.grade.corr(m.grade_n1)))
o = pd.DataFrame(out); print(o.round(3).to_string(index=False)); o.to_csv(OUT/"t5_predictive.csv", index=False)
