"""NGS coverage probe — how far back does each stat_type go?"""
from __future__ import annotations

import os
import sys

os.environ['NFLREADPY_CACHE'] = 'off'
os.environ['NFLREADPY_VERBOSE'] = 'False'
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import inspect

import nflreadpy as nfl

print('load_nextgen_stats signature:', inspect.signature(nfl.load_nextgen_stats))
print()

for stat_type in ['passing', 'rushing', 'receiving']:
    df = nfl.load_nextgen_stats(seasons=True, stat_type=stat_type).to_pandas()
    print(f'=== {stat_type}: {len(df)} rows, cols={len(df.columns)} ===')
    print(f'  seasons: {sorted(df["season"].unique())}')
    reg = df[df['season_type'] == 'REG']
    print(f'  REG season_type row counts:')
    print('  ', dict(sorted(reg.groupby('season').size().items())))
    print(f'  week values (REG): {sorted(reg["week"].unique())}')
    # Season-aggregated rows are typically week=0 or similar
    print(f'  week=0 rows (season aggregates): {len(reg[reg["week"] == 0])}')
    print()

# Examine season aggregates specifically
pass_df = nfl.load_nextgen_stats(seasons=True, stat_type='passing').to_pandas()
season_agg = pass_df[(pass_df['season_type'] == 'REG') & (pass_df['week'] == 0)]
print('SEASON AGGREGATES — passing QB rows by year:')
print(season_agg.groupby('season').size().to_dict())
print()
print('Mahomes all-time NGS passing (season aggregates):')
mahomes = season_agg[season_agg['player_gsis_id'] == '00-0033873']
cols = ['season', 'attempts', 'avg_time_to_throw', 'aggressiveness',
        'completion_percentage_above_expectation',
        'avg_air_yards_to_sticks', 'avg_completed_air_yards']
print(mahomes[cols].to_string(index=False))
