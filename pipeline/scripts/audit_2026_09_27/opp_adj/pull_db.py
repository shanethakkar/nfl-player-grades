from db import q
from common import OUT
sc = q("""select sc.player_id, sc.season, sc.component_name, sc.raw_value, sc.adjusted_value, sc.z_score, sc.sample_size, sc.used_in_composite
          from stat_components sc""")
sg = q("select player_id, season, position, composite_grade, composite_z, percentile, qualified, role, team_abbr from season_grades")
pl = q("select player_id, gsis_id, pfr_id, full_name, position from players")
sc.to_parquet(OUT/"db_sc.parquet"); sg.to_parquet(OUT/"db_sg.parquet"); pl.to_parquet(OUT/"db_players.parquet")
print(len(sc), len(sg), len(pl))
