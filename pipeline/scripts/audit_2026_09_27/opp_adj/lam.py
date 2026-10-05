from common import *
res = {}
allc = {k: [] for k in SETS}
for s in SEASONS:
    d = load_pbp(s)
    d.to_parquet(OUT / f"pbp_f_{s}.parquet")
    for k, (f, v) in SETS.items():
        allc[k].append(cells(d, f, v))
for k in SETS:
    lam, s2, t2 = estimate_lambda(allc[k])
    # offense side too
    res[k] = dict(lam=lam, sigma=np.sqrt(s2), tau_def=np.sqrt(t2))
    print(k, res[k])
pd.to_pickle(allc, OUT / "cells_full.pkl")
pd.DataFrame(res).T.to_csv(OUT / "lambda.csv")
