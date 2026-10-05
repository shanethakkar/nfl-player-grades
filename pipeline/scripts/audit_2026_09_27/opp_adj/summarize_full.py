from common import *
from scipy.stats import pearsonr
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
R = pd.read_csv(OUT / "full_results.csv")
c = R[R.comp != "COMPOSITE"].copy(); c["ratio"] = c.sd_sched / c.sd_raw; c["ratio_shrunk"] = c.sd_sched / c.sd_shrunk
print(c.groupby(["variant", "comp"])[["nq", "sd_raw", "sd_sched", "ratio", "ratio_shrunk", "spearman_comp", "mean_abs_dz", "max_abs_dz"]].mean().round(3))
k = R[R.comp == "COMPOSITE"]
print(k.groupby(["variant", "P"])[["nq", "spearman_comp", "mean_abs_dgrade", "p90_abs_dgrade", "max_abs_dgrade", "frac_ge3", "frac_ge5", "mean_abs_drank", "max_abs_drank"]].mean().round(3))
print(k.groupby(["variant", "P"])[["max_abs_dgrade"]].max().round(2))
# YoY
PP = pd.read_parquet(OUT / "full_perplayer.parquet")
rows = []
for (v, comp), a in PP[PP.qualified].groupby(["variant", "comp"]):
    m = a.merge(a.assign(season=a.season - 1), on=["player_id", "season"], suffixes=("", "_n"))
    rows.append(dict(variant=v, comp=comp, pairs=len(m), yoy_raw=m.sh_raw.corr(m.sh_raw_n), yoy_adj=m.sh_adj.corr(m.sh_adj_n),
                     sched_yoy=m.sched.corr(m.sched_n)))
Y = pd.DataFrame(rows); Y["delta"] = Y.yoy_adj - Y.yoy_raw; print(Y.round(3))
# composite YoY
M = pd.read_parquet(OUT / "full_movers.parquet")
rows = []
for (v, P), a in M.groupby(["variant", "P"]):
    m = a.merge(a.assign(season=a.season - 1), on=["player_id", "season"], suffixes=("", "_n"))
    rows.append(dict(variant=v, P=P, pairs=len(m), yoy_old=m.grade_old.corr(m.grade_old_n), yoy_new=m.grade_new.corr(m.grade_new_n)))
print(pd.DataFrame(rows).round(4))
# bootstrap-ish: per-season YoY delta sign for ridge EPA comps
rows = []
for comp, a in PP[PP.qualified & (PP.variant == "ridge")].groupby("comp"):
    for s in range(2016, 2025):
        m = a[a.season == s].merge(a[a.season == s + 1].assign(season=s), on=["player_id", "season"], suffixes=("", "_n"))
        rows.append(dict(comp=comp, s=s, d=m.sh_adj.corr(m.sh_adj_n) - m.sh_raw.corr(m.sh_raw_n)))
D = pd.DataFrame(rows); print(D.groupby("comp").d.agg(["mean", "std", lambda x: (x > 0).sum()]).round(3))
# movers 2024, 2025 (ridge)
for s in [2024, 2025]:
    mm = M[(M.variant == "ridge") & (M.season == s)].copy(); mm["dg"] = mm.grade_new - mm.grade_old
    mm["dr"] = mm.rank_old - mm.rank_new
    for P in ["QB", "RB", "WR", "TE"]:
        x = mm[mm.P == P].reindex(mm[mm.P == P].dg.abs().sort_values(ascending=False).index).head(4)
        print(s, P, "\n", x[["name", "team", "grade_old", "grade_new", "dg", "rank_old", "rank_new"]].round(1).to_string(index=False))
