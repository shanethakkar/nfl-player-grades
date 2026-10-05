"""Stage 1: per-player raw vs opponent-adjusted values for each play set, full + partial seasons."""
from common import *

LAM = pd.read_csv(OUT / "lambda.csv", index_col=0)["lam"].to_dict()
_R = pd.read_csv(OUT / "rho.csv", index_col=0)
RHO_EST = _R["slope_def"].to_dict(); RHO_OFF_EST = _R["slope_off"].to_dict()
KEY = {"db_epa": "passer_player_id", "db_succ": "passer_player_id", "cpoe": "passer_player_id",
       "rush_epa": "rusher_player_id", "rush_succ": "rusher_player_id",
       "tgt_epa": "receiver_player_id", "tgt_succ": "receiver_player_id"}
CUTS = [3, 6]


def agg(x, key, val, cols):
    g = x.groupby(key)
    out = pd.DataFrame({"n": g.size(), "raw": g[val].mean(), "team": g.posteam.agg(lambda t: t.mode().iat[0])})
    for c in cols:
        out[c] = g[c].mean()
    return out


full_def = {}  # (season,set) -> full-season (non-LOO) ridge def rating, used for priors
rows_full, rows_part, team_rows = [], [], []
for s in SEASONS:
    d = pd.read_parquet(OUT / f"pbp_f_{s}.parquet")
    teams = sorted(set(d.posteam) | set(d.defteam))
    for k, (flag, val) in SETS.items():
        lam = LAM[k]
        x = d[d[flag]].copy()
        c = cells(d, flag, val)
        mu, off, de = ridge_ratings(c, lam, teams)
        full_def[(s, k)] = (off, de)
        team_rows.append(pd.DataFrame({"season": s, "set": k, "team": teams, "def": de.to_numpy(), "off": off.reindex(teams).to_numpy()}))
        r_loo = loo_def_ratings(c, lam, teams).rename(columns={"d_loo": "d_ridge"})
        r_simple = simple_loo_def(c, lam, teams).rename(columns={"d_loo": "d_simple"})
        x = x.merge(r_loo, on=["posteam", "defteam"], how="left").merge(r_simple, on=["posteam", "defteam"], how="left")
        x["adj_ridge"] = x[val] - x.d_ridge
        x["adj_simple"] = x[val] - x.d_simple
        a = agg(x, KEY[k], val, ["adj_ridge", "adj_simple"])
        a["season"] = s; a["set"] = k
        rows_full.append(a.reset_index(names="gsis"))
        # ---- partial seasons ----
        prev = full_def.get((s - 1, k))
        for W in CUTS:
            cw = cells(d[d.week <= W], flag, val)
            r_asof = loo_def_ratings(cw, lam, teams).rename(columns={"d_loo": "d_asof"})
            xw = x[x.week <= W].merge(r_asof, on=["posteam", "defteam"], how="left")
            xw["adj_asof"] = xw[val] - xw.d_asof
            xw["adj_oracle"] = xw["adj_ridge"]  # full-season LOO ratings (not knowable in-season)
            cols = ["adj_asof", "adj_oracle"]
            if prev is not None:
                r_pr = loo_def_ratings(cw, lam, teams, prior_def=prev[1] * RHO_EST.get(k, 0.35), prior_off=prev[0] * RHO_OFF_EST.get(k, 0.5)).rename(columns={"d_loo": "d_prior"})
                xw = xw.merge(r_pr, on=["posteam", "defteam"], how="left")
                xw["adj_prior"] = xw[val] - xw.d_prior
                cols.append("adj_prior")
            aw = agg(xw, KEY[k], val, cols)
            xr = x[x.week > W]
            ar = agg(xr, KEY[k], val, ["adj_ridge"]).rename(columns={"n": "n_ros", "raw": "raw_ros", "adj_ridge": "adj_ros", "team": "team_ros"})
            aw = aw.join(ar, how="left")
            aw["season"] = s; aw["set"] = k; aw["W"] = W
            rows_part.append(aw.reset_index(names="gsis"))
    print("done", s, flush=True)

pd.concat(rows_full).to_parquet(OUT / "player_full.parquet")
pd.concat(rows_part).to_parquet(OUT / "player_part.parquet")
pd.concat(team_rows).to_parquet(OUT / "team_ratings.parquet")
