"""YoY regression slope of full-season ridge team ratings (for as-of-week priors)."""
from common import *
LAM = pd.read_csv(OUT / "lambda.csv", index_col=0)["lam"].to_dict()
rows = []
for s in SEASONS:
    d = pd.read_parquet(OUT / f"pbp_f_{s}.parquet")
    teams = sorted(set(d.posteam) | set(d.defteam))
    for k, (f, v) in SETS.items():
        mu, off, de = ridge_ratings(cells(d, f, v), LAM[k], teams)
        rows.append(pd.DataFrame({"season": s, "set": k, "team": teams, "def": de.values, "off": off.reindex(teams).values}))
t = pd.concat(rows)
# normalize historical abbreviations crudely for YoY: map old->new
alias = {"SD": "LAC", "OAK": "LV", "STL": "LA"}
t["team"] = t.team.replace(alias)
res = {}
for k in SETS:
    a = t[t.set == k]
    m = a.merge(a.assign(season=a.season - 1), on=["season", "team"], suffixes=("", "_n"))
    bd = np.polyfit(m["def"], m["def_n"], 1)[0]; bo = np.polyfit(m["off"], m["off_n"], 1)[0]
    res[k] = dict(slope_def=bd, r_def=m["def"].corr(m["def_n"]), slope_off=bo, r_off=m["off"].corr(m["off_n"]))
r = pd.DataFrame(res).T; print(r.round(3)); r.to_csv(OUT / "rho.csv")
