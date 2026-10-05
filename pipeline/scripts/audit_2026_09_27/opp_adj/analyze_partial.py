"""Partial seasons (through week 3 / 6): size of schedule effect and rest-of-season predictive value."""
from common import *
from nfl_grades.grading import weights as W_
from nfl_grades.grading.empirical_bayes import shrink_series
from nfl_grades.grading.sigmoid import to_grade
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)

pp = pd.read_parquet(OUT / "player_part.parquet")
sg = pd.read_parquet(OUT / "db_sg.parquet"); pl = pd.read_parquet(OUT / "db_players.parquet")
pp["player_id"] = pp.gsis.map(pl.dropna(subset=["gsis_id"]).set_index("gsis_id").player_id)
pos = sg.drop_duplicates(["player_id", "season"]).set_index(["player_id", "season"]).position
pp["P"] = [pos.get((a, b)) for a, b in zip(pp.player_id, pp.season)]

# (P, component, set, k, full-season qualification threshold on that component's n, weight share)
def share(w, c): return abs(w[c]) / sum(abs(v) for v in w.values())
SPEC = [
    ("QB", "qb_epa_per_dropback", "db_epa", 150, 200, share(W_.QB_V1_WEIGHTS, "qb_epa_per_dropback")),
    ("QB", "qb_cpoe", "cpoe", 100, 180, share(W_.QB_V1_WEIGHTS, "qb_cpoe")),
    ("QB", "qb_success_rate", "db_succ", 150, 200, share(W_.QB_V1_WEIGHTS, "qb_success_rate")),
    ("RB", "rb_rush_epa_per_attempt", "rush_epa", 100, 100, share(W_.RB_V1_WEIGHTS, "rb_rush_epa_per_attempt")),
    ("RB", "rb_rush_success_rate", "rush_succ", 100, 100, share(W_.RB_V1_WEIGHTS, "rb_rush_success_rate")),
    ("WR", "wr_rec_epa_per_target", "tgt_epa", 50, 50, share(W_.WR_V1_WEIGHTS, "wr_rec_epa_per_target")),
    ("WR", "wr_success_rate_per_target", "tgt_succ", 50, 50, share(W_.WR_V1_WEIGHTS, "wr_success_rate_per_target")),
    ("TE", "te_rec_epa_per_target", "tgt_epa", 50, 40, share(W_.TE_V1_WEIGHTS, "te_rec_epa_per_target")),
    ("TE", "te_success_rate_per_target", "tgt_succ", 50, 40, share(W_.TE_V1_WEIGHTS, "te_success_rate_per_target")),
]
VARS = ["raw", "adj_asof", "adj_prior", "adj_oracle"]
GAMES = 17
rows, zstore = [], []
for P, comp, setk, k, thr, sh in SPEC:
    for Wk in [3, 6]:
        for s in range(2017, 2026):
            a = pp[(pp.P == P) & (pp.set == setk) & (pp.W == Wk) & (pp.season == s)].copy()
            q = a.n >= thr * Wk / GAMES
            qr = a.n_ros.fillna(0) >= thr * (GAMES - Wk) / GAMES
            z = {}
            for v in VARS:
                shv = shrink_series(a[v], a.n.astype(float), k)
                z[v] = (shv - shv[q].mean()) / shv[q].std()
                a["sh_" + v] = shv
            ros_raw = shrink_series(a.raw_ros, a.n_ros.fillna(0).astype(float), k)
            ros_adj = shrink_series(a.adj_ros, a.n_ros.fillna(0).astype(float), k)
            m = q & qr
            r = dict(P=P, comp=comp, W=Wk, season=s, nq=int(q.sum()), n_pred=int(m.sum()),
                     sd_raw=a.raw[q].std(), sd_shrunk=a.sh_raw[q].std(),
                     sd_sched_asof=(a.raw - a.adj_asof)[q].std(), sd_sched_prior=(a.raw - a.adj_prior)[q].std(),
                     sd_sched_oracle=(a.raw - a.adj_oracle)[q].std())
            for v in VARS[1:]:
                dz = (z[v] - z["raw"])[q]
                r[f"mabs_dz_{v}"] = dz.abs().mean(); r[f"p90_dgrade_{v}"] = (dz.abs() * sh * 28.75).quantile(.9)
            for v in VARS:
                r[f"r_rosraw_{v}"] = a["sh_" + v][m].corr(ros_raw[m])
                r[f"r_rosadj_{v}"] = a["sh_" + v][m].corr(ros_adj[m])
            rows.append(r)
            zz = pd.DataFrame({f"z_{v}": z[v] for v in VARS}); zz[["player_id", "gsis", "q", "qr"]] = a[["player_id", "gsis"]].assign(q=q, qr=qr)
            zz["ros_raw"] = ros_raw; zz["ros_adj"] = ros_adj; zz[["P", "comp", "W", "season"]] = [P, comp, Wk, s]
            zstore.append(zz)
R = pd.DataFrame(rows); R.to_csv(OUT / "partial_results.csv", index=False)
Z = pd.concat(zstore); Z.to_parquet(OUT / "partial_z.parquet")
R["ratio_asof"] = R.sd_sched_asof / R.sd_raw; R["ratio_asof_sh"] = R.sd_sched_asof / R.sd_shrunk
R["ratio_prior_sh"] = R.sd_sched_prior / R.sd_shrunk; R["ratio_oracle_sh"] = R.sd_sched_oracle / R.sd_shrunk
g = R.groupby(["comp", "W"])
print(g[["nq", "ratio_asof", "ratio_asof_sh", "ratio_prior_sh", "ratio_oracle_sh", "mabs_dz_adj_asof", "mabs_dz_adj_prior", "mabs_dz_adj_oracle",
         "p90_dgrade_adj_asof", "p90_dgrade_adj_prior", "p90_dgrade_adj_oracle"]].mean().round(3))
print(g[[f"r_rosraw_{v}" for v in VARS] + [f"r_rosadj_{v}" for v in VARS]].mean().round(3))
# seasons where asof/prior beat raw at predicting ROS raw
for v in VARS[1:]:
    R[f"win_{v}"] = R[f"r_rosraw_{v}"] > R["r_rosraw_raw"]
print(g[[f"win_{v}" for v in VARS[1:]]].sum())

# ---- QB full in-season composite (all 3 QB components are PBP-derived) ----
w = W_.QB_V1_WEIGHTS; tot = sum(abs(x) for x in w.values())
qrows = []
for Wk in [3, 6]:
    for s in range(2017, 2026):
        zq = Z[(Z.P == "QB") & (Z.W == Wk) & (Z.season == s)]
        piv = {v: zq.pivot_table(index="player_id", columns="comp", values=f"z_{v}") for v in VARS}
        base = piv["raw"]
        qual = zq[zq.comp == "qb_epa_per_dropback"].set_index("player_id").q.reindex(base.index).fillna(False).astype(bool)
        qualr = zq[zq.comp == "qb_epa_per_dropback"].set_index("player_id").qr.reindex(base.index).fillna(False).astype(bool)
        ros = {t: zq.pivot_table(index="player_id", columns="comp", values=t) for t in ["ros_raw", "ros_adj"]}
        def cz(p): return sum(w[c] / tot * p[c] for c in w)
        def zs(x): return (x - x[qual].mean()) / x[qual].std()
        ros_c = {t: cz(ros[t].apply(zs)) for t in ros}
        g0 = pd.Series(to_grade(cz(base).to_numpy()), index=base.index)
        for v in VARS[1:]:
            gv = pd.Series(to_grade(cz(piv[v]).to_numpy()), index=base.index)
            d = (gv - g0)[qual]
            mm = qual & qualr
            qrows.append(dict(W=Wk, season=s, variant=v, nq=int(qual.sum()), mean_abs_dg=d.abs().mean(), p90=d.abs().quantile(.9), mx=d.abs().max(),
                              ge5=(d.abs() >= 5).mean(), spear=g0[qual].rank().corr(gv[qual].rank()),
                              r_ros_raw_base=cz(base)[mm].corr(ros_c["ros_raw"][mm]), r_ros_raw_v=cz(piv[v])[mm].corr(ros_c["ros_raw"][mm]),
                              r_ros_adj_base=cz(base)[mm].corr(ros_c["ros_adj"][mm]), r_ros_adj_v=cz(piv[v])[mm].corr(ros_c["ros_adj"][mm])))
Q = pd.DataFrame(qrows); Q.to_csv(OUT / "partial_qb_composite.csv", index=False)
print(Q.groupby(["W", "variant"]).mean(numeric_only=True).drop(columns="season").round(3))
