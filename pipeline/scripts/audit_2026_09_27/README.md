# 2026-09-27 system audit: analysis scripts

The analyses behind [docs/grading/audits/2026-09-27-system-audit.md](../../../docs/grading/audits/2026-09-27-system-audit.md),
promoted from session scratch (#12) so the audit can be reproduced. They were
the starting point for the evaluation harness (`nflgrades evaluate`,
`grading/evaluation.py`), which replaces them for any new Formula decision.

**Frozen as run.** They read the database and parquet cache as they stood on
2026-09-27, before Phase 1 restated every season. Several re-implement
production filters that have since changed (the QB dropback filter here
excludes scrambles, fixed in #3; composites zero-fill missing Components,
fixed in #6). Expect different numbers if you re-run them today.

## Running

Run from inside the script's folder, with the pipeline venv active
(`nfl_grades` installed editable). They read through `nfl_grades.db`
(so `DATABASE_URL` decides the database) and the nflverse parquet cache under
`PIPELINE_CACHE_DIR/raw/`. Intermediate files go to
`PIPELINE_CACHE_DIR/audit_2026_09_27/`, never into the repo. All of them are
read-only against the database.

## reliability/

| Script | Audit finding |
|---|---|
| `pull.py`, `pull2.py`, `schema.py` | Snapshot `season_grades`, `stat_components`, `player_seasons` and team OL tables to parquet. Run first. |
| `pbp.py` | Slim cached pbp with the production play filters. |
| `t1_scale.py` | F1: grade scale by position, predicted vs actual composite SD, missing-Component rates. |
| `t2_yoy.py`, `t2b_components.py` | F2: YoY for team stayers vs changers, composite and per Component. |
| `t3_splithalf.py`, `t3_fullcheck.py` | F3: odd/even-week split-half Reliability for QB/RB/WR/TE; check that the rebuilt composite matches production. |
| `t4_contam.py` | F2: receiver Components vs own QB / team passing, coverage stats vs team pass rush. |
| `t5_validity.py` | F4: Pro Bowl same vs next season, SE of r, bootstrap of historical weight-change deltas, grade vs next-season primary stat. |
| `t6_zero.py` | F7: exact-zero and NULL Component values. |

## opp_adj/

Opponent adjustment (F6, ADR-0029). Run in order: `pull_db.py`, `lam.py`
(cached filtered pbp + ridge λ), `rho.py`, `build_offense.py`, then the
analyses `analyze_full.py` (full seasons), `analyze_partial.py` (through week
3/6, rest-of-season prediction), `analyze_defense.py` (CB/EDGE), and
`summarize_full.py` / `extra.py` for the tables in the audit. `common.py` holds
the pbp loader and the ridge team ratings. #18 builds the QB Opponent
adjustment Candidate from it.
