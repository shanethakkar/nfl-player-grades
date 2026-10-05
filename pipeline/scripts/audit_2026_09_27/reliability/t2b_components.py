"""Test 2b: pooled stayers-vs-changers and per-component YoY split (is the collapse team context or general flux?)."""
import numpy as np, pandas as pd
from common import OUT
exec(open("t2_yoy.py").read().split("def fz")[0])   # reuse pair construction (pairs, changer flag)
res = pd.read_csv(OUT/"t2_yoy.csv")
def pool(grp):
    z = np.arctanh(grp.r); w = grp.n-3; m = (z*w).sum()/w.sum(); se = 1/np.sqrt(w.sum())
    return f"{np.tanh(m):.3f} [{np.tanh(m-1.96*se):.3f},{np.tanh(m+1.96*se):.3f}] n={int(grp.n.sum())}"
for lab in ["stayers","changers"]:
    print("pooled", lab, pool(res[res.group==lab])); print("pooled excl K/P", lab, pool(res[(res.group==lab)&~res.pos.isin(["K","P"])]))
sc = pd.read_parquet(OUT/"stat_components.parquet")
raw = sc.pivot_table(index=["player_id","season"], columns="component_name", values="raw_value", aggfunc="first").reset_index()
pre = {"QB":"qb_","RB":"rb_","WR":"wr_","TE":"te_","CB":"cb_","S":"s_","EDGE":"edge_","iDL":"idl_","LB":"lb_"}
rows=[]
for pos, p in pre.items():
    pp = pairs[pairs.position==pos]
    a = pp.merge(raw, on=["player_id","season"]).merge(raw, left_on=["player_id","season_n1"] if "season_n1" in pp else ["player_id"], right_on=["player_id","season"], how="left", suffixes=("","_y")) if False else None
    x = pp.merge(raw, on=["player_id","season"])
    y = raw.copy(); y["season"] -= 1
    x = x.merge(y, on=["player_id","season"], suffixes=("","__n1"))
    for c in [c for c in raw.columns if isinstance(c,str) and c.startswith(p)]:
        for lab, sub in [("stay", x[~x.changer]), ("chg", x[x.changer])]:
            ok = sub[c].notna() & sub[c+"__n1"].notna()
            if ok.sum() > 10: rows.append(dict(pos=pos, comp=c, grp=lab, n=int(ok.sum()), r=np.corrcoef(sub.loc[ok,c], sub.loc[ok,c+"__n1"])[0,1]))
t = pd.DataFrame(rows).pivot_table(index=["pos","comp"], columns="grp", values=["r","n"]).round(3)
pd.set_option("display.width",200); print(t.to_string()); t.to_csv(OUT/"t2b_components.csv")
