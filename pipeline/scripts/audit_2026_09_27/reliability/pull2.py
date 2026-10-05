from common import q, OUT
for t in ["team_ol_grades","team_ol_components"]:
    d = q(f"select * from {t}"); print(t, d.columns.tolist(), len(d)); d.to_parquet(OUT/f"{t}.parquet")
import pandas as pd
sg = pd.read_parquet(OUT/"season_grades.parquet")
print(sg.team_abbr.isna().groupby(sg.position).mean())
print(sg.groupby("position").season.agg(["min","max"]))
