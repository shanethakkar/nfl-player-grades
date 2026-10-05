from common import q
for t in ["season_grades","stat_components","players","player_seasons","teams","team_aliases"]:
    print(t, list(q("select column_name from information_schema.columns where table_name=:t order by ordinal_position", t=t).column_name))
print(q("select position, count(*), sum(qualified::int) q from season_grades group by 1 order by 1"))
