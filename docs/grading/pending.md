# Pending — exhaustive audit master plan

Locked 2026-05-14. After running the YoY noise + pairwise correlation audits, the user committed to the "do it right" statistical approach: exhaustive candidate audit per position before any new component decision, using four criteria (reliability + cross-sectional discrimination + independence + downstream predictive validity). Goal is a methodology defensible enough for a published article.

## The full queue

| # | Phase | Item | Cost | Status |
|---|---|---|---|---|
| 1 | Foundation | Build downstream predictive validity check tool | 0.5-1 day | **SHIPPED 2026-05-14** |
| 1a | Foundation | Run validity baseline on all 9 shipped positions | 10 min | **SHIPPED 2026-05-14** ([baseline](audits/2026-05-14-validity-baseline.md)) |
| 2 | Foundation | Build "exhaustive candidate" audit tool | 1-2 days | **SHIPPED 2026-05-14** (framework + QB starter; per-position fetchers fill in during phase 4-12) |
| 3 | Foundation | Hold-out validation norm + audit-playbook codification | 1 hour | **SHIPPED 2026-05-14** ([playbook](audit-playbook.md)) |
| 4 | Exhaustive audit | QB (smallest formula, validates tooling first) | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-qb.md), [research](research/qb-v1-1.md)) |
| 5 | Exhaustive audit | WR (largest cohort, validates scaling) | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-wr.md), [research](research/wr-v1-1.md)) |
| 6 | Exhaustive audit | RB | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-rb.md)) — v1.3 shipped success_rate reduction; v1.4 queued below |
| **6b** | New component (Path B) | RB v1.4: add `rb_yards_after_contact` from pfr_advstats rush — highest-validity candidate of any audit so far (+0.192) | 0.5-1 day | **SHIPPED 2026-05-14** — first Path B ship from the framework. Validity +0.247→+0.259. |
| 7 | Exhaustive audit | TE | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-te.md)) — v1.2: target_earn 0.10→0.15, success_rate 0.08→0.05. Validity +0.384→+0.407 (strongest Path A gain in any audit). Brock Bowers rises 18→13. |
| 8 | Exhaustive audit | CB | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-cb.md)) — v1.2: target_rate -0.08→-0.05. Validity +0.219→+0.220. Methodology cleanup; CB has structural weak validity (voter noise ceiling). |
| 9 | Exhaustive audit | S | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-s.md)) — v1.2: target_rate -0.08→-0.05. Validity +0.253→+0.255. Same finding as CB; both DB positions converged on target_rate cleanup. |
| 10 | Exhaustive audit | EDGE | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-edge.md)) — v1.2: added edge_tackles_per_snap at +0.05 (validity +0.216, max_r +0.468 — independent signal). Validity +0.420→+0.424. Second Path B ship from the framework. |
| 11 | Exhaustive audit | iDL | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-idl.md)) — v1.2: rebalance (pressure 0.30→0.35, TFL 0.35→0.25, sack 0.15→0.20) + add tackles_per_snap +0.05. **Validity +0.457→+0.475 — biggest defensive gain.** Voters reward interior pressure more than original "iDL=run-stop" design assumed. |
| 12 | Exhaustive audit | LB | 0.5 day | **SHIPPED 2026-05-14** ([audit](audits/2026-05-14-exhaustive-lb.md)) — v1.2: passer_rating_allowed -0.27→-0.15 (over-weighted vs validity at LB sample sizes), pressure_rate +0.07→+0.10 (under-weighted). **Validity +0.179→+0.198 (+11%, biggest relative defensive gain).** LB has structural stats-vs-reputation ceiling. **ALL POSITION AUDITS COMPLETE.** |
| 13 | Ship | Apply any v1.X weight changes that emerge (including QB v1.1) | varies | pending |
| 14 | New position | Kickers v1 (full audit-first process) | 1-1.5 day | pending |
| 15 | New position | Punters v1 (full audit-first process) | 0.5-1 day | pending |
| 16 | New position | OL unit-level grading (new schema/UI + full audit) | 3-5 days | pending |
| 17 | Synthesis | Cross-position methodology writeup for article | 1-2 days | pending |

**Remaining realistic timeline: 3-5 weeks** of focused work (foundation complete; exhaustive audit phase + new positions + synthesis remaining).

## Foundation complete (2026-05-14): what's available now

- **`nflgrades validity`** — runs Pro Bowl correlation per position. Baseline numbers are in [audits/2026-05-14-validity-baseline.md](audits/2026-05-14-validity-baseline.md). Use as decision criterion for weight changes (lower validity = back out the change).
- **`nflgrades audit-candidates --position POS`** — runs the four-criterion audit on a position's candidate set. Framework in [pipeline/src/nfl_grades/grading/exhaustive_audit.py](../../pipeline/src/nfl_grades/grading/exhaustive_audit.py). QB has a starter set of 3 candidates as a worked example (NGS aggressiveness, time_to_throw, sack rate suffered). Expand `<pos>_candidates()` functions during each position's audit phase.
- **`docs/grading/audit-playbook.md`** — now has the full four-criterion framework, hold-out validation norm, and the exhaustive-audit instructions.
- **`pipeline/data/pro_bowl_selections.csv`** — 7 seasons of Pro Bowl rosters (2018-2024). Reproducible: re-pulled from Wikipedia Pro Bowl pages.

## What "exhaustive candidate audit" means (queue items 4-12)

For each position, the tool runs:

1. **Pull every relevant column** from data inventory ([data-inventory.md](data-inventory.md)).
2. **Filter by mechanical relevance.** Drop volume stats, pure usage markers, PFF-only stats with no nflverse equivalent.
3. **Score each survivor on four criteria** via `nflgrades audit-candidates --position <POS>`.
4. **Skill-tree map** the survivors.
5. **Decide per candidate:** confirm current pick, replace, add, or reject. Document the verdict.

Output per position: `docs/grading/audits/2026-XX-XX-exhaustive-<pos>.md` with full candidate table + verdict column. **The rejected candidates are documented too** — that's what makes the methodology article-defensible.

## Critical principles

1. **Grading is a definition, not an estimator.** Statistics inform reasoning; they don't replace it.
2. **Document rejected candidates.** Article credibility hinges on showing the audit log.
3. **Apply changes incrementally.** Each completed audit may produce a small weight tweak that ships immediately via the preview/regrade workflow.
4. **Hold-out validate** any change touching ≥0.10 weight: define on 2016-2023, verify on 2024-2025.

## Article-worthy claim (the eventual destination)

> *"For each position, we evaluated every plausible candidate stat against four statistical criteria: reliability (YoY r), cross-sectional discrimination, independence from existing components (correlation < 0.6), and downstream predictive validity (Pro Bowl correlation). Components in the formula are what survived all four. Components that failed are documented in [docs/grading/audits/](audits/)."*

## What's NO LONGER queued (shipped 2026-05-14)

- ~~Cross-position YoY audit~~ — done. See [audits/2026-05-14-cross-position-yoy.md](audits/2026-05-14-cross-position-yoy.md).
- ~~Pairwise correlation audit~~ — done. See [audits/2026-05-14-correlation.md](audits/2026-05-14-correlation.md).
- ~~Preview + sync + regrade tooling~~ — done. See [iteration-workflow.md](iteration-workflow.md).
- ~~Initial methodology playbook update~~ — done. Full validity + hold-out additions are in [audit-playbook.md](audit-playbook.md).
- ~~EDGE/iDL "designed component overlap" notes~~ — done. ADR-0020 and ADR-0021 have explicit Component Overlap sections.
- ~~Downstream predictive validity check~~ — done. See [audits/2026-05-14-validity-baseline.md](audits/2026-05-14-validity-baseline.md).
- ~~Exhaustive-candidate audit framework~~ — done. Framework lives in `pipeline/src/nfl_grades/grading/exhaustive_audit.py`; per-position candidate fetchers added incrementally during each position's audit (queue items 4-12).
- ~~QB exhaustive audit + QB v1.1 ship~~ — done. See [audits/2026-05-14-exhaustive-qb.md](audits/2026-05-14-exhaustive-qb.md) and [research/qb-v1-1.md](research/qb-v1-1.md). 19 candidates scored, success_rate lowered 0.25→0.10, validity improved +0.237→+0.244.
- ~~WR exhaustive audit + WR v1.3 ship~~ — done. See [audits/2026-05-14-exhaustive-wr.md](audits/2026-05-14-exhaustive-wr.md). 22 candidates scored, target_earn_rate bumped 0.10→0.15 (strongest signal), success_rate lowered 0.08→0.05 (EPA redundancy). Validity +0.280→+0.300.
- ~~RB exhaustive audit + RB v1.3 ship~~ — done. See [audits/2026-05-14-exhaustive-rb.md](audits/2026-05-14-exhaustive-rb.md). 19 candidates scored, rush_success_rate lowered 0.14→0.05 (EPA redundancy). Validity +0.243→+0.247.
- ~~RB v1.4 Path B ship (yards_after_contact)~~ — done. New migration 0015 + ingest module + grader update. Validity +0.247→+0.259. **First Path B ship from the exhaustive audit framework.** Demonstrates the methodology surfaces real new components, not just redundancy fixes.
- ~~TE exhaustive audit + TE v1.2 ship~~ — done. See [audits/2026-05-14-exhaustive-te.md](audits/2026-05-14-exhaustive-te.md). 22 candidates scored. target_earn_rate 0.10→0.15 (strongest signal), success_rate 0.08→0.05. **Validity +0.384→+0.407 — strongest Path A gain in any audit so far.** Brock Bowers rises 18→13 (addresses face-check miss).
- ~~Methodology-page percentage-share display~~ — done. Weights now display as "share of formula" (sums to 100%) on the methodology page, derived from auto-synced grades.ts; hardcoded POSITION_COMPONENTS list removed. Math unchanged; reader experience cleaner.
