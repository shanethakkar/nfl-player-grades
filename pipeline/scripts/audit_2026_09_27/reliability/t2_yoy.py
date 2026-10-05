"""Test 2: YoY reliability of composite_grade, split by team changers vs stayers."""
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr, norm
from common import OUT
from pbp import load
sg = pd.read_parquet(OUT/"season_grades.parquet")
ps = pd.read_parquet(OUT/"player_seasons.parquet").drop_duplicates(["player_id","season"])
# offensive primary team from pbp (most involvement), fallback player_seasons
d = load()
inv = pd.concat([d[d.is_db][["season","passer_player_id","posteam"]].rename(columns={"passer_player_id":"gsis"}),
                 d[d.is_rush][["season","rusher_player_id","posteam"]].rename(columns={"rusher_player_id":"gsis"}),
                 d[d.is_tgt][["season","receiver_player_id","posteam"]].rename(columns={"receiver_player_id":"gsis"})])
cnt = inv.groupby(["gsis","season","posteam"]).size().rename("n").reset_index()
tot = cnt.groupby(["gsis","season"]).n.transform("sum")
cnt["share"] = cnt.n/tot
prim = cnt.sort_values("n").drop_duplicates(["gsis","season"], keep="last").rename(columns={"posteam":"pbp_team","share":"pbp_share"})
# primary QB per team-season (most dropbacks)
qbc = d[d.is_db].groupby(["season","posteam","passer_player_id"]).size().rename("n").reset_index()
pqb = qbc.sort_values("n").drop_duplicates(["season","posteam"], keep="last").rename(columns={"passer_player_id":"prim_qb"})[["season","posteam","prim_qb"]]
g = sg[sg.qualified & sg.composite_grade.notna()].merge(ps[["player_id","season","abbr"]], on=["player_id","season"], how="left")
g = g.merge(prim[["gsis","season","pbp_team","pbp_share"]], left_on=["gsis_id","season"], right_on=["gsis","season"], how="left")
g["team"] = np.where(g.pbp_team.notna() & g.position.isin(["QB","RB","WR","TE"]), g.pbp_team, g.abbr)
g = g.merge(pqb, left_on=["season","team"], right_on=["season","posteam"], how="left")
a = g[["player_id","position","season","composite_grade","team","prim_qb","pbp_share"]]
b = a.copy(); b["season"] -= 1
pairs = a.merge(b, on=["player_id","position","season"], suffixes=("","_n1"))
# LA/STL, SD/LAC, OAK/LV relocation: normalize via team_aliases-like map (pbp already uses LA/LAC/LV; player_seasons uses team_id abbr)
pairs["changer"] = pairs.team != pairs.team_n1
def fz(r, n):
    if n < 4: return (np.nan, np.nan)
    z = np.arctanh(r); se = 1/np.sqrt(n-3); return (np.tanh(z-1.96*se), np.tanh(z+1.96*se))
def stats(x, y):
    n = len(x)
    if n < 5: return dict(n=n)
    r = pearsonr(x, y)[0]; rho = spearmanr(x, y)[0]; lo, hi = fz(r, n)
    return dict(n=n, r=r, lo=lo, hi=hi, rho=rho, sd_x=np.std(x, ddof=1))
rows = []
for pos, grp in pairs.groupby("position"):
    for lab, sub in [("all", grp), ("stayers", grp[~grp.changer]), ("changers", grp[grp.changer])]:
        rows.append(dict(pos=pos, group=lab, **stats(sub.composite_grade.values, sub.composite_grade_n1.values)))
    if pos in ("WR","TE","RB"):
        st = grp[~grp.changer]
        for lab, sub in [("stay_sameQB", st[st.prim_qb == st.prim_qb_n1]), ("stay_newQB", st[st.prim_qb != st.prim_qb_n1])]:
            rows.append(dict(pos=pos, group=lab, **stats(sub.composite_grade.values, sub.composite_grade_n1.values)))
res = pd.DataFrame(rows)
# difference test stayers vs changers
for pos in res.pos.unique():
    s = res[(res.pos==pos)&(res.group=="stayers")].iloc[0]; c = res[(res.pos==pos)&(res.group=="changers")].iloc[0]
    if c.n >= 5:
        zd = (np.arctanh(s.r)-np.arctanh(c.r))/np.sqrt(1/(s.n-3)+1/(c.n-3)); res.loc[(res.pos==pos)&(res.group=="changers"),"p_diff"] = 2*norm.sf(abs(zd))
pd.set_option("display.width",200)
print(res.round(3).to_string(index=False)); res.to_csv(OUT/"t2_yoy.csv", index=False)
# OL team-level YoY
ol = pd.read_parquet(OUT/"team_ol_grades.parquet"); o2 = ol.copy(); o2["season"] -= 1
op = ol.merge(o2, on=["team_id","season"], suffixes=("","_n1")); print("OL team YoY", stats(op.composite_grade.values, op.composite_grade_n1.values))
