from common import q, OUT
sg = q("""select sg.*, p.full_name, p.gsis_id, p.position as player_pos from season_grades sg join players p using(player_id)""")
sg.to_parquet(OUT/"season_grades.parquet")
sc = q("select * from stat_components")
sc.to_parquet(OUT/"stat_components.parquet")
ps = q("select ps.*, t.abbr from player_seasons ps left join teams t using(team_id)")
ps.to_parquet(OUT/"player_seasons.parquet")
print(len(sg), len(sc), len(ps))
print(q("select table_name from information_schema.tables where table_schema='public' order by 1").table_name.tolist())
