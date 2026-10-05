from common import *
M = pd.read_parquet(OUT / "full_movers.parquet"); M = M[M.variant == "ridge"].copy(); M["dg"] = M.grade_new - M.grade_old
pf = pd.read_parquet(OUT / "player_full.parquet"); pl = pd.read_parquet(OUT / "db_players.parquet")
pf["player_id"] = pf.gsis.map(pl.dropna(subset=["gsis_id"]).set_index("gsis_id").player_id)
sched = pf[pf.set.isin(["db_epa", "tgt_epa", "rush_epa"])].assign(sched=lambda x: x.raw - x.adj_ridge)
q = M[M.P == "QB"].merge(sched[sched.set == "db_epa"][["player_id", "season", "team", "sched", "n"]], on=["player_id", "season"], how="left")
print(q.reindex(q.dg.abs().sort_values(ascending=False).index).head(10)[["season", "name", "team_y", "n", "sched", "grade_old", "grade_new", "dg", "rank_old", "rank_new"]].round(3).to_string(index=False))
for s in range(2016, 2025):
    a = M[(M.P == "QB") & (M.season == s)].merge(M[(M.P == "QB") & (M.season == s + 1)], on="player_id", suffixes=("", "_n"))
    print(s, len(a), round(a.grade_new.corr(a.grade_new_n) - a.grade_old.corr(a.grade_old_n), 3))
# team-level schedule effect distribution for QB (EPA/db) per season
t = sched[sched.set == "db_epa"].groupby(["season", "team"]).apply(lambda x: np.average(x.sched, weights=x.n))
print("team QB-EPA schedule effect SD by season:", t.groupby("season").std().round(4).to_dict(), "max abs", t.abs().max().round(3))
