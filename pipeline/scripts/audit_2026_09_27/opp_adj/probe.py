from db import q
print(q("select column_name, table_name from information_schema.columns where table_name in ('stat_components','season_grades','players') order by table_name, ordinal_position").groupby('table_name').column_name.apply(list).to_dict())
print(q("""select split_part(component_name,'_',1) pos, count(*) n,
  sum((adjusted_value is not null)::int) n_adj,
  avg(abs(adjusted_value-raw_value)) mad_adj_raw
  from stat_components group by 1 order by 1"""))
print(q("select position, count(*), sum(qualified::int) q from season_grades group by 1 order by 1"))
