"""Test 1 (scale comparability) + Test 6 (missing components)."""
import sys
import numpy as np, pandas as pd
from nfl_grades.grading import weights as W
from common import OUT
sg = pd.read_parquet(OUT/"season_grades.parquet")
sc = pd.read_parquet(OUT/"stat_components.parquet")
WTS = {"QB":W.QB_V1_WEIGHTS,"RB":W.RB_V1_WEIGHTS,"WR":W.WR_V1_WEIGHTS,"TE":W.TE_V1_WEIGHTS,"CB":W.CB_V1_WEIGHTS,
       "S":W.S_V1_WEIGHTS,"EDGE":W.EDGE_V1_WEIGHTS,"iDL":W.IDL_V1_WEIGHTS,"LB":W.LB_V1_WEIGHTS,"K":W.K_V1_WEIGHTS,"P":W.P_V1_WEIGHTS}
rows=[]; miss=[]
for pos, w in WTS.items():
    g = sg[(sg.position==pos)&sg.qualified&sg.composite_grade.notna()].copy()
    gr = g.composite_grade.astype(float); cz = g.composite_z.astype(float)
    comps = list(w)
    zz = sc[sc.component_name.isin(comps)].pivot_table(index=["player_id","season"], columns="component_name", values="z_score", aggfunc="first")
    zz = g[["player_id","season"]].merge(zz.reset_index(), on=["player_id","season"], how="left")
    Z = zz[comps].astype(float)
    wv = np.array([w[c] for c in comps]); wv = wv/np.abs(wv).sum()
    # predicted SD: correlation-matrix version (unit variances) and actual covariance (z filled 0 as in prod)
    Zf = Z.fillna(0.0)
    R = Zf.corr().to_numpy(); C = Zf.cov().to_numpy()
    sd_R = float(np.sqrt(wv@R@wv)) if len(comps)>1 else 1.0
    sd_C = float(np.sqrt(wv@C@wv))
    # recompute composite from components as check
    recomp = (Zf.to_numpy()@wv)
    chk = np.corrcoef(recomp, cz)[0,1] if len(comps)>1 else 1.0
    # mean within-season SD of composite_z
    sd_within = g.groupby("season").composite_z.std().mean()
    pct90 = (gr<90).mean()*100
    rows.append(dict(pos=pos, n=len(g), k=len(comps), sd_cz=cz.std(), sd_cz_within_season=sd_within, pred_sd_R=sd_R, pred_sd_cov=sd_C, recomp_r=chk,
        p10=gr.quantile(.1), p50=gr.quantile(.5), p90=gr.quantile(.9), p99=gr.quantile(.99), max=gr.max(),
        share_ge90=(gr>=90).mean()*100, share_ge80=(gr>=80).mean()*100, pctile_of_90=pct90,
        grade_at_p98=gr.quantile(.98), z_needed_for_90_in_sd=1.9106/sd_within))
    for c in comps:
        present = zz[c].notna()
        miss.append(dict(pos=pos, comp=c, weight=w[c], n_qual=len(g), n_missing=int((~present).sum()),
                         pct_missing=100*(~present).mean(),
                         seasons_missing=",".join(str(s) for s,v in zz.assign(m=~present).groupby("season").m.mean().items() if v>0.5)))
df = pd.DataFrame(rows)
# OL
ol = pd.read_parquet(OUT/"team_ol_grades.parquet"); olc = pd.read_parquet(OUT/"team_ol_components.parquet")
zo = olc.pivot_table(index=["team_id","season"], columns="component_name", values="z_score")
wv = np.array([W.OL_V1_WEIGHTS[c] for c in zo.columns]); wv=wv/np.abs(wv).sum()
gr = ol.composite_grade.astype(float)
df = pd.concat([df, pd.DataFrame([dict(pos="OL(team)", n=len(ol), k=2, sd_cz=ol.composite_z.astype(float).std(),
    sd_cz_within_season=ol.groupby("season").composite_z.std().mean(), pred_sd_R=float(np.sqrt(wv@zo.corr().to_numpy()@wv)),
    pred_sd_cov=float(np.sqrt(wv@zo.cov().to_numpy()@wv)), recomp_r=np.nan, p10=gr.quantile(.1), p50=gr.quantile(.5), p90=gr.quantile(.9),
    p99=gr.quantile(.99), max=gr.max(), share_ge90=(gr>=90).mean()*100, share_ge80=(gr>=80).mean()*100, pctile_of_90=(gr<90).mean()*100,
    grade_at_p98=gr.quantile(.98), z_needed_for_90_in_sd=1.9106/ol.groupby('season').composite_z.std().mean())])])
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
print(df.round(3).to_string(index=False))
df.to_csv(OUT/"t1_scale.csv", index=False)
m = pd.DataFrame(miss); print(m[m.n_missing>0].round(1).to_string(index=False)); m.to_csv(OUT/"t6_missing.csv", index=False)
# normal theory: what share >=90 if composite ~ N(0, s)
from scipy.stats import norm
print("theory share>=90 if N(0,s):", {r.pos: round(100*norm.sf(1.9106/r.sd_cz_within_season),2) for r in df.itertuples()})
# correlation matrices
for pos,w in WTS.items():
    if len(w)<2: continue
    g = sg[(sg.position==pos)&sg.qualified]
    zz = sc[sc.component_name.isin(list(w))].pivot_table(index=["player_id","season"], columns="component_name", values="z_score").reset_index()
    zz = g[["player_id","season"]].merge(zz, on=["player_id","season"]).drop(columns=["player_id","season"]).fillna(0)
    print(pos); print(zz.corr().round(2).to_string())
