# CB v1 + Safety v1 Implementation Notes

CB v1 grading implemented 2026-05-12 (ADR-0018); Safety v1 grading implemented 2026-05-13 (ADR-0019).

**Why:** Both positions use PFR advstats def as primary coverage data source — PBP doesn't record the covering defender on completions.

**CB data:** `pfr_advstats_def` → `pfr_def_coverage` table. Available 2018+. v1 components: cb_comp_pct_allowed (−0.22), cb_yac_per_rec_allowed (−0.18), cb_target_rate (−0.08), cb_int_rate (+0.10), cb_pbu_rate (+0.12). Qualification: 25 targets appear, 30 qualified, 60 full confidence.

> **v1.1 swap (2026-05-14):** comp_pct_allowed + int_rate replaced with single `cb_passer_rating_allowed` (−0.35) component. Industry-standard coverage damage metric, naturally captures comp%, yds/att, TDs allowed, and INTs as four sub-components. v1 didn't penalize TDs allowed at all; v1.1 does.

**Safety data:** `pfr_advstats_def` (coverage + missed tackles — confirmed present all seasons) + `nflvs_player_stats` (PBU, comb_tackles, TFL, sacks) → `pfr_def_coverage_s` table. Available 2018+. Qualification: 200 snaps appear, 400 qualified, 700 full confidence.

**Safety formula (v1.1):** 70% coverage / 30% tackling, sum |abs|=0.82. Components: s_passer_rating_allowed (−0.30), s_pbu_rate (+0.12), s_target_rate (−0.08), s_tackles_per_snap (+0.07), s_missed_tackle_rate (−0.09), s_backfield_disruption_per_snap (+0.09).

**Key facts:**
- `pfr_advstats_def` DOES include missed tackle data (confirmed in all 2018-2025 seasons, ~100% coverage)
- Safety position in players table is 'S' (mapped from FS/SS/S/SAF by rosters ingest)
- Safety leaderboard uses player_seasons for team lookup (not plays table like offense)
- `component_name LIKE 'cb_%'` or `LIKE 's_%'` delete pattern prevents orphaned rows on formula change

**Files created/modified:**
- `db/migrations/0007_create_pfr_def_coverage.sql` (CB)
- `db/migrations/0009_safety_coverage.sql` (Safety)
- `pipeline/.../ingest/pfr.py` — CB ingest
- `pipeline/.../ingest/pfr_safety.py` — Safety ingest (separate module)
- `pipeline/.../grading/weights.py` — CB and Safety constants
- `pipeline/.../grading/cb.py` — CB grader
- `pipeline/.../grading/safety.py` — Safety grader
- `pipeline/.../grading/run.py` — both registered
- `pipeline/.../cli.py` — `ingest pfr-def-coverage-s` + grade S
- `docs/adr/0018-cb-v1-grading-formula.md`, `docs/adr/0019-s-v1-grading-formula.md`
- `web/src/lib/grades.ts` — CB and Safety component formats, weights, role labels
- `web/src/lib/queries.ts` — S branch in getLeaderboard()
- `web/src/components/LeaderboardTable.tsx` — S_COLUMNS
- `web/src/types/index.ts` — n_snaps, s_* fields on LeaderboardEntry
- `web/src/app/methodology/page.tsx` — CB and Safety position cards
