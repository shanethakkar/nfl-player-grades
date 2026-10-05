"""Test 6 supplement: exact-zero raw values (possible silent imputation) and NULL-z vs absent split."""
import pandas as pd
from common import OUT
sg = pd.read_parquet(OUT/"season_grades.parquet"); sc = pd.read_parquet(OUT/"stat_components.parquet")
q = sg[sg.qualified][["player_id","season","position"]]
m = q.merge(sc, on=["player_id","season"])
pre = {"QB":"qb_","RB":"rb_","WR":"wr_","TE":"te_","CB":"cb_","S":"s_","EDGE":"edge_","iDL":"idl_","LB":"lb_","K":"k_","P":"p_"}
m = m[[c.startswith(pre[p]) for c,p in zip(m.component_name, m.position)]]
t = m.groupby(["position","component_name"]).agg(n=("player_id","size"), null_z=("z_score", lambda s: s.isna().sum()), null_raw=("raw_value", lambda s: s.isna().sum()),
     zero_raw=("raw_value", lambda s: (s==0).sum()), zero_n=("sample_size", lambda s: (s==0).sum())).reset_index()
pd.set_option("display.width",200); print(t[(t.null_z>0)|(t.zero_raw>0)|(t.zero_n>0)].to_string(index=False))
z = m[m.component_name.str.contains("missed_tackle")].copy(); z["zero"]=z.raw_value==0
print(z.groupby(["component_name","season"]).zero.mean().unstack().round(2))
