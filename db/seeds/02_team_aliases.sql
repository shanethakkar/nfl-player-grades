-- Historical NFL team abbreviations -> current team. Every value used by
-- nflverse for our covered seasons (2016+) must resolve through this table.
--
-- Idempotent: safe to re-run.
--
-- Coverage notes:
--   SD   -> LAC  (Chargers relocated 2017)
--   OAK  -> LV   (Raiders relocated 2020)
--   STL  -> LA   (Rams relocated 2016; pre-2016 data uses STL but is out of scope)
--   LAR  -> LA   (some sources use LAR; nflverse standardizes to LA)
--   WSH  -> WAS  (some sources use WSH for Washington)
--   ARZ  -> ARI  (rare alternate spelling for Arizona)
--   BLT  -> BAL  (rare alternate spelling for Baltimore)
--   CLV  -> CLE  (rare alternate spelling for Cleveland)
--   HST  -> HOU  (rare alternate spelling for Houston)
--   SL   -> LA   (very rare alternate for St. Louis Rams)
--
-- Plus: every current abbreviation aliases to itself, so the lookup is always
-- one query (no "if not found, try as-is" branch in the pipeline).

INSERT INTO team_aliases (alias, team_id)
SELECT abbr, team_id FROM teams
ON CONFLICT (alias) DO UPDATE SET team_id = EXCLUDED.team_id;

INSERT INTO team_aliases (alias, team_id) VALUES
    ('SD',  (SELECT team_id FROM teams WHERE abbr = 'LAC')),
    ('OAK', (SELECT team_id FROM teams WHERE abbr = 'LV')),
    ('STL', (SELECT team_id FROM teams WHERE abbr = 'LA')),
    ('LAR', (SELECT team_id FROM teams WHERE abbr = 'LA')),
    ('SL',  (SELECT team_id FROM teams WHERE abbr = 'LA')),
    ('WSH', (SELECT team_id FROM teams WHERE abbr = 'WAS')),
    ('ARZ', (SELECT team_id FROM teams WHERE abbr = 'ARI')),
    ('BLT', (SELECT team_id FROM teams WHERE abbr = 'BAL')),
    ('CLV', (SELECT team_id FROM teams WHERE abbr = 'CLE')),
    ('HST', (SELECT team_id FROM teams WHERE abbr = 'HOU'))
ON CONFLICT (alias) DO UPDATE SET team_id = EXCLUDED.team_id;
