"""Stage 2 (full seasons): swap opponent-adjusted components into production z-scores, recompute composites."""
from common import *
from scipy.stats import spearmanr, pearsonr
from nfl_grades.grading import weights as W
from nfl_grades.grading.empirical_bayes import shrink_series
from nfl_grades.grading.sigmoid import to_grade

sc = pd.read_parquet(OUT / "db_sc.parquet"); sg = pd.read_parquet(OUT / "db_sg.parquet"); pl = pd.read_parquet(OUT / "db_players.parquet")
pf = pd.read_parquet(OUT / "player_full.parquet")
gs2pid = pl.dropna(subset=["gsis_id"]).set_index("gsis_id").player_id
pf["player_id"] = pf.gsis.map(gs2pid)
names = pl.set_index("player_id").full_name

POS = {
    "QB": dict(w=W.QB_V1_WEIGHTS, k=W.QB_V1_SHRINKAGE_K, fill=False,
               adj={"qb_epa_per_dropback": "db_epa", "qb_cpoe": "cpoe", "qb_success_rate": "db_succ"}),
    "RB": dict(w=W.RB_V1_WEIGHTS, k=W.RB_V1_SHRINKAGE_K, fill=True,
               adj={"rb_rush_epa_per_attempt": "rush_epa", "rb_rush_success_rate": "rush_succ", "rb_rec_epa_per_target": "tgt_epa"}),
    "WR": dict(w=W.WR_V1_WEIGHTS, k=W.WR_V1_SHRINKAGE_K, fill=True,
               adj={"wr_rec_epa_per_target": "tgt_epa", "wr_success_rate_per_target": "tgt_succ"}),
    "TE": dict(w=W.TE_V1_WEIGHTS, k=W.TE_V1_SHRINKAGE_K, fill=True, wblock=W.TE_V1_BLOCKING_WEIGHTS,
               adj={"te_rec_epa_per_target": "tgt_epa", "te_success_rate_per_target": "tgt_succ"}),
}
EPA_COMP = {"QB": "qb_epa_per_dropback", "RB": "rb_rush_epa_per_attempt", "WR": "wr_rec_epa_per_target", "TE": "te_rec_epa_per_target"}


def comp_z(zw: pd.DataFrame, g: pd.DataFrame, spec) -> pd.Series:
    def one(ws, rows):
        tot = sum(abs(v) for v in ws.values())
        acc = pd.Series(0.0, index=rows.index); nan = pd.Series(False, index=rows.index)
        for c, v in ws.items():
            col = rows[c] if c in rows else pd.Series(np.nan, index=rows.index)
            nan |= col.isna()
            acc += v / tot * col.fillna(0)
        if not spec["fill"]:
            acc[nan] = np.nan
        return acc
    out = one(spec["w"], zw)
    if "wblock" in spec:
        blk = g.reindex(zw.index).role.eq("blocking_te")
        out[blk] = one(spec["wblock"], zw[blk])[blk] if blk.any() else out[blk]
    return out


results, movers, per_player = [], [], []
checks = []
for P, spec in POS.items():
    pre = P.lower() + "_"
    for s in SEASONS:
        g = sg[(sg.position == P) & (sg.season == s)].set_index("player_id")
        c = sc[(sc.season == s) & sc.component_name.str.startswith(pre)]
        zw = c.pivot(index="player_id", columns="component_name", values="z_score").reindex(g.index)
        # reconstruction check
        cz0 = comp_z(zw, g, spec)
        checks.append(dict(P=P, season=s, max_abs_err_compz=float((cz0 - g.composite_z).abs().max())))
        for variant in ["ridge", "simple"]:
            zw_new = zw.copy()
            comp_rows = []
            for comp, setk in spec["adj"].items():
                cc = c[c.component_name == comp].set_index("player_id")
                mine = pf[(pf.season == s) & (pf.set == setk)].dropna(subset=["player_id"]).drop_duplicates("player_id").set_index("player_id")
                df = cc[["raw_value", "z_score", "sample_size"]].join(mine[["n", "raw", f"adj_{variant}"]], how="left")
                df = df.join(g[["qualified"]], how="inner")
                has = df.raw.notna()
                if variant == "ridge":
                    checks.append(dict(P=P, season=s, comp=comp, match_rate=has.mean(),
                                       max_raw_diff=float((df.raw - df.raw_value).abs()[has].max()),
                                       n_diff=float((df.n - df.sample_size).abs()[has].max())))
                n = df.n.fillna(0); k = spec["k"][comp]
                sh_raw = shrink_series(df.raw, n, k); sh_adj = shrink_series(df[f"adj_{variant}"], n, k)
                q = df.qualified & has
                zr = (sh_raw - sh_raw[q].mean()) / sh_raw[q].std(); za = (sh_adj - sh_adj[q].mean()) / sh_adj[q].std()
                dz = (za - zr).fillna(0)
                zw_new[comp] = zw[comp] + dz.reindex(zw.index).fillna(0)
                sched = (df.raw - df[f"adj_{variant}"])
                yo = dict(P=P, season=s, variant=variant, comp=comp, nq=int(q.sum()),
                          sd_raw=df.raw[q].std(), sd_shrunk=sh_raw[q].std(), sd_sched=sched[q].std(),
                          spearman_comp=spearmanr(sh_raw[q], sh_adj[q])[0], mean_abs_dz=dz[q].abs().mean(),
                          max_abs_dz=dz[q].abs().max())
                comp_rows.append(yo)
                per_player.append(pd.DataFrame({"P": P, "season": s, "variant": variant, "comp": comp, "player_id": df.index,
                                                "qualified": df.qualified.values, "sh_raw": sh_raw.values, "sh_adj": sh_adj.values,
                                                "sched": sched.values, "n": n.values}))
            cz1 = comp_z(zw_new, g, spec)
            # grade delta applied to stored composite (removes tiny reconstruction error)
            new_cz = g.composite_z + (cz1 - cz0)
            gr_old = g.composite_grade; gr_new = pd.Series(to_grade(new_cz.to_numpy()), index=g.index)
            qq = g.qualified & new_cz.notna()
            dg = (gr_new - gr_old)[qq]
            rk_old = gr_old[qq].rank(ascending=False); rk_new = gr_new[qq].rank(ascending=False)
            for r in comp_rows:
                results.append(r)
            results.append(dict(P=P, season=s, variant=variant, comp="COMPOSITE", nq=int(qq.sum()),
                                spearman_comp=spearmanr(gr_old[qq], gr_new[qq])[0],
                                mean_abs_dgrade=dg.abs().mean(), p90_abs_dgrade=dg.abs().quantile(.9), max_abs_dgrade=dg.abs().max(),
                                frac_ge3=(dg.abs() >= 3).mean(), frac_ge5=(dg.abs() >= 5).mean(),
                                mean_abs_drank=(rk_old - rk_new).abs().mean(), max_abs_drank=(rk_old - rk_new).abs().max()))
            m = pd.DataFrame({"P": P, "season": s, "variant": variant, "player_id": g.index[qq], "name": names.reindex(g.index[qq]).values,
                              "team": g.team_abbr[qq].values, "grade_old": gr_old[qq].values, "grade_new": gr_new[qq].values,
                              "rank_old": rk_old.values, "rank_new": rk_new.values})
            movers.append(m)
        print(P, s, flush=True)

R = pd.DataFrame(results); R.to_csv(OUT / "full_results.csv", index=False)
M = pd.concat(movers); M.to_parquet(OUT / "full_movers.parquet")
PP = pd.concat(per_player); PP.to_parquet(OUT / "full_perplayer.parquet")
C = pd.DataFrame(checks); C.to_csv(OUT / "recon_checks.csv", index=False)
print(C.groupby("P").max(numeric_only=True))
print(C.dropna(subset=["comp"]).groupby("comp")[["match_rate", "max_raw_diff", "n_diff"]].agg(["min", "max"]))
