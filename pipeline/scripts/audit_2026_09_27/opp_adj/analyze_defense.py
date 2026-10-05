"""Defense: CB passer_rating_allowed vs opponent passing offense; EDGE pressure/sack rate vs opponent pass protection."""
from common import *
from scipy.stats import spearmanr
from nfl_grades.grading import weights as W_
from nfl_grades.grading.empirical_bayes import shrink_series
from nfl_grades.grading.sigmoid import to_grade
import warnings
warnings.filterwarnings("ignore")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
RAW = REPO / "pipeline/.cache/raw"
sc = pd.read_parquet(OUT / "db_sc.parquet"); sg = pd.read_parquet(OUT / "db_sg.parquet"); pl = pd.read_parquet(OUT / "db_players.parquet")
pfr2pid = pl.dropna(subset=["pfr_id"]).drop_duplicates("pfr_id").set_index("pfr_id").player_id
names = pl.set_index("player_id").full_name
LAM = pd.read_csv(OUT / "lambda.csv", index_col=0)["lam"].to_dict()


def team_game_loo(tg: pd.DataFrame, lam: float):
    """Offense rate deviation from league, excluding games vs deff, shrunk den/(den+lam)."""
    league = tg.num.sum() / tg.den.sum()
    rows = []
    for T in sorted(set(tg.off)):
        g = tg[tg.deff != T].groupby("off")[["num", "den"]].sum()
        dev = (g.num / g.den - league) * g.den / (g.den + lam)
        rows.append(pd.DataFrame({"off": dev.index, "deff": T, "dev": dev.values}))
    return pd.concat(rows), league


def mom_lambda(tg):
    out = []
    for s, t in tg.groupby("season"):
        g = t.groupby("off")[["num", "den"]].sum(); m = g.num / g.den
        r = t.num / t.den; mu = t.num.sum() / t.den.sum()
        sig2 = float((t.den * (r - mu) ** 2).sum() / len(t))
        tau2 = float(m.var() - (sig2 / g.den).mean())
        out.append((sig2, tau2))
    s2, t2 = np.mean(out, axis=0)
    return s2 / max(t2, 1e-12), np.sqrt(max(t2, 0))


def within_beta(df, y, x, w):
    d = df[[y, x, w, "pid"]].copy()
    for c in [y, x]:
        d["wv"] = d[c] * d[w]
        mean = d.groupby("pid").wv.transform("sum") / d.groupby("pid")[w].transform("sum")
        d[c + "_dm"] = d[c] - mean
    return float((d[w] * d[x + "_dm"] * d[y + "_dm"]).sum() / (d[w] * d[x + "_dm"] ** 2).sum())


def wavg(df, val, wt):
    d = df.assign(_v=df[val] * df[wt])
    g = d.groupby("pid")[["_v", wt]].sum()
    return g._v / g[wt]


def swap_and_grade(P, s, comps_adj: dict, wts):
    g = sg[(sg.position == P) & (sg.season == s)].set_index("player_id")
    pre = {"CB": "cb_", "EDGE": "edge_"}[P]
    c = sc[(sc.season == s) & sc.component_name.str.startswith(pre)]
    zw = c.pivot(index="player_id", columns="component_name", values="z_score").reindex(g.index)
    tot = sum(abs(v) for v in wts.values())
    def cz(z): return sum(v / tot * z[k].fillna(0) for k, v in wts.items())
    z0 = cz(zw); z1 = zw.copy(); stats = {}
    for comp, (adj_series, k) in comps_adj.items():
        cc = c[c.component_name == comp].set_index("player_id").join(g[["qualified"]], how="inner")
        cover = adj_series.reindex(cc.index).notna()
        adj = adj_series.reindex(cc.index).fillna(cc.raw_value)
        n = cc.sample_size.astype(float)
        sr = shrink_series(cc.raw_value, n, k); sa = shrink_series(adj, n, k)
        q = cc.qualified.astype(bool)
        zr = (sr - sr[q].mean()) / sr[q].std(); za = (sa - sa[q].mean()) / sa[q].std()
        z1[comp] = zw[comp] + (za - zr).reindex(zw.index).fillna(0)
        stats[comp] = dict(sd_raw=cc.raw_value[q].std(), sd_sched=(cc.raw_value - adj)[q].std(), spear=spearmanr(sr[q], sa[q])[0],
                           mabs_dz=(za - zr)[q].abs().mean(), cover=cover[q].mean(), sh_raw=sr[q], sh_adj=sa[q])
    newz = g.composite_z + (cz(z1) - z0)
    gn = pd.Series(to_grade(newz.to_numpy()), index=g.index)
    q = g.qualified.astype(bool)
    d = (gn - g.composite_grade)[q]
    comp_stats = dict(nq=int(q.sum()), spear=spearmanr(g.composite_grade[q], gn[q])[0], mean_abs_dg=d.abs().mean(),
                      p90=d.abs().quantile(.9), mx=d.abs().max(), ge5=(d.abs() >= 5).mean())
    mv = pd.DataFrame({"P": P, "season": s, "player_id": g.index[q], "name": names.reindex(g.index[q]).values,
                       "old": g.composite_grade[q].values, "new": gn[q].values})
    return stats, comp_stats, mv


# ---------------- weekly defensive data + opponent ratings ----------------
tg_press, tg_sack, cbw, edw, off_rat = [], [], [], [], []
for s in range(2018, 2026):
    pbp = pd.read_parquet(RAW / f"pbp/{s}.parquet", columns=["season_type", "game_id", "posteam", "defteam", "qb_dropback", "sack"])
    pbp = pbp[(pbp.season_type == "REG") & (pbp.qb_dropback == 1)]
    db = pbp.groupby(["game_id", "posteam", "defteam"]).agg(den=("sack", "size"), sacks=("sack", "sum")).reset_index()
    pf = pd.read_parquet(RAW / f"pfr_advstats_def/{s}.parquet"); pf = pf[pf.game_type == "REG"]
    pr = pf.groupby(["game_id", "team"]).def_pressures.sum().reset_index()
    m = db.merge(pr.rename(columns={"team": "defteam"}), on=["game_id", "defteam"], how="left")
    tg_press.append(pd.DataFrame({"season": s, "game_id": m.game_id, "off": m.posteam, "deff": m.defteam, "num": m.def_pressures, "den": m.den}))
    tg_sack.append(pd.DataFrame({"season": s, "game_id": m.game_id, "off": m.posteam, "deff": m.defteam, "num": m.sacks, "den": m.den}))
    snaps = pd.read_parquet(RAW / f"snap_counts/{s}.parquet"); snaps = snaps[snaps.game_type == "REG"][["game_id", "pfr_player_id", "defense_snaps"]]
    w = pf.merge(snaps, on=["game_id", "pfr_player_id"], how="left")
    w["season"] = s; w["pid"] = w.pfr_player_id.map(pfr2pid)
    cbw.append(w[["season", "week", "game_id", "team", "opponent", "pid", "def_targets", "def_passer_rating_allowed"]])
    edw.append(w[["season", "week", "game_id", "team", "opponent", "pid", "def_pressures", "def_sacks", "defense_snaps"]])
    d = pd.read_parquet(OUT / f"pbp_f_{s}.parquet"); teams = sorted(set(d.posteam) | set(d.defteam))
    c = cells(d, "is_tgt", "epa")
    for T in teams:
        _, off, _ = ridge_ratings(c[c.defteam != T], LAM["tgt_epa"], teams)
        off = off - off.mean()
        off_rat.append(pd.DataFrame({"season": s, "off": off.index, "deff": T, "off_epa": off.values}))
TGP = pd.concat(tg_press); TGS = pd.concat(tg_sack); CBW = pd.concat(cbw); EDW = pd.concat(edw); OFF = pd.concat(off_rat)
print("pfr pressure join coverage:", round(TGP.num.notna().mean(), 4))
print("PFR team abbrs not in pbp:", set(CBW.team) - set(OFF.off))
TGP = TGP.dropna(subset=["num"])
lam_p, tau_p = mom_lambda(TGP); lam_s, tau_s = mom_lambda(TGS)
print(f"lambda pressure={lam_p:.0f} dropbacks (tau={tau_p:.4f}); lambda sack={lam_s:.0f} (tau={tau_s:.4f})")

cb_parts, ed_parts = [], []
for s in range(2018, 2026):
    w = CBW[(CBW.season == s) & (CBW.def_targets > 0)].dropna(subset=["pid"]).merge(
        OFF[OFF.season == s].rename(columns={"off": "opponent", "deff": "team"}), on=["season", "opponent", "team"], how="left")
    cbids = sc[(sc.season == s) & (sc.component_name == "cb_passer_rating_allowed")].player_id
    cb_parts.append(w[w.pid.isin(cbids)])
    e = EDW[(EDW.season == s) & (EDW.defense_snaps > 0)].dropna(subset=["pid"])
    eids = sc[(sc.season == s) & (sc.component_name == "edge_pressure_rate")].player_id
    e = e[e.pid.isin(eids)]
    lp, _ = team_game_loo(TGP[TGP.season == s], lam_p); ls, _ = team_game_loo(TGS[TGS.season == s], lam_s)
    e = e.merge(lp.rename(columns={"off": "opponent", "deff": "team", "dev": "opp_press"}), on=["opponent", "team"], how="left")
    e = e.merge(ls.rename(columns={"off": "opponent", "deff": "team", "dev": "opp_sack"}), on=["opponent", "team"], how="left")
    ed_parts.append(e)
cb = pd.concat(cb_parts); ed = pd.concat(ed_parts)
beta_cb = within_beta(cb.dropna(subset=["off_epa", "def_passer_rating_allowed"]), "def_passer_rating_allowed", "off_epa", "def_targets")
ed["press_rate_w"] = ed.def_pressures / ed.defense_snaps; ed["sack_rate_w"] = ed.def_sacks / ed.defense_snaps
beta_p = within_beta(ed.dropna(subset=["opp_press", "press_rate_w"]), "press_rate_w", "opp_press", "defense_snaps")
beta_s = within_beta(ed.dropna(subset=["opp_sack", "sack_rate_w"]), "sack_rate_w", "opp_sack", "defense_snaps")
print(f"beta CB PR-allowed per unit opp tgt-EPA = {beta_cb:.1f}; EDGE press/snap per unit opp press/db = {beta_p:.3f}; sack/snap per opp sack/db = {beta_s:.3f}")

res, comp_rows, movers, yy = [], [], [], []
for s in range(2018, 2026):
    c = cb[cb.season == s].dropna(subset=["off_epa"])
    sched_cb = wavg(c, "off_epa", "def_targets") * beta_cb
    stored = sc[(sc.season == s) & (sc.component_name == "cb_passer_rating_allowed")].set_index("player_id").raw_value
    adj_cb = stored - sched_cb.reindex(stored.index)
    st, cs, mv = swap_and_grade("CB", s, {"cb_passer_rating_allowed": (adj_cb, W_.CB_V1_SHRINKAGE_K["cb_passer_rating_allowed"])}, W_.CB_V1_WEIGHTS)
    parts = [("CB", st, cs, mv)]
    e = ed[ed.season == s]
    sp = wavg(e.dropna(subset=["opp_press"]), "opp_press", "defense_snaps") * beta_p
    ss = wavg(e.dropna(subset=["opp_sack"]), "opp_sack", "defense_snaps") * beta_s
    stp = sc[(sc.season == s) & (sc.component_name == "edge_pressure_rate")].set_index("player_id").raw_value
    sts = sc[(sc.season == s) & (sc.component_name == "edge_sack_rate")].set_index("player_id").raw_value
    st, cs, mv = swap_and_grade("EDGE", s, {"edge_pressure_rate": (stp - sp.reindex(stp.index), W_.EDGE_V1_SHRINKAGE_K["edge_pressure_rate"]),
                                            "edge_sack_rate": (sts - ss.reindex(sts.index), W_.EDGE_V1_SHRINKAGE_K["edge_sack_rate"])}, W_.EDGE_V1_WEIGHTS)
    parts.append(("EDGE", st, cs, mv))
    for P, st, cs, mv in parts:
        for k, v in st.items():
            comp_rows.append(dict(P=P, season=s, comp=k, **{a: b for a, b in v.items() if not a.startswith("sh_")}))
            yy.append(pd.DataFrame({"comp": k, "season": s, "player_id": v["sh_raw"].index, "sh_raw": v["sh_raw"].values, "sh_adj": v["sh_adj"].values}))
        res.append(dict(P=P, season=s, **cs)); movers.append(mv)

C = pd.DataFrame(comp_rows); C["ratio"] = C.sd_sched / C.sd_raw
print(C.groupby("comp")[["sd_raw", "sd_sched", "ratio", "spear", "mabs_dz", "cover"]].mean().round(4))
Rz = pd.DataFrame(res); print(Rz.groupby("P").mean(numeric_only=True).drop(columns="season").round(3)); print(Rz.groupby("P").mx.max())
Y = pd.concat(yy)
for comp, a in Y.groupby("comp"):
    m = a.merge(a.assign(season=a.season - 1), on=["player_id", "season"], suffixes=("", "_n"))
    print(comp, "pairs", len(m), "yoy raw %.3f adj %.3f" % (m.sh_raw.corr(m.sh_raw_n), m.sh_adj.corr(m.sh_adj_n)))
M = pd.concat(movers); M["dg"] = M.new - M.old
for P in ["CB", "EDGE"]:
    for s in [2024, 2025]:
        x = M[(M.P == P) & (M.season == s)]; x = x.reindex(x.dg.abs().sort_values(ascending=False).index).head(4)
        print(P, s); print(x[["name", "old", "new", "dg"]].round(1).to_string(index=False))
Rz.to_csv(OUT / "defense_results.csv", index=False); C.to_csv(OUT / "defense_components.csv", index=False)
