# RB Exhaustive Candidate Audit — 2026-05-14

Third production application of the four-criterion audit framework. Scored 19 plausible RB candidate stats against reliability + cross-sectional discrimination + independence + predictive validity.

**Cohort:** qualified RB-seasons 2017-2024 (n=452 for stat_components, n=449 for nflvs-derived, n=405 for NGS 2017+, n=356 for PFR 2018+).

Tool: `nflgrades audit-candidates --position RB`.

## Full candidate table

| Candidate | n | YoY r | xsect | max \|r\| existing | partner | PB r | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| **Currently-shipped (re-scored with self-excluded):** | | | | | | | |
| `rb_ryoe_per_attempt` | 353 | +0.246 | 0.51 | +0.588 | rb_rush_epa_per_attempt | +0.130 | Independent / weak validity |
| `rb_rush_epa_per_attempt` | 452 | +0.120 | 0.09 | **+0.725** | rb_rush_success_rate | +0.139 | MEANINGFUL OVERLAP |
| `rb_rush_success_rate` | 452 | +0.144 | 0.05 | **+0.713** | rb_rush_epa_per_attempt | **+0.079** | NOISE (lowest validity, highest redundancy) |
| `rb_rec_epa_per_target` | 452 | **+0.010** | 0.25 | +0.561 | rb_yac_over_expected_per_rec | +0.096 | NOISE (confirmed — v1.2 was correct) |
| `rb_yac_over_expected_per_rec` | 452 | +0.200 | 1.60 | +0.589 | rb_rec_epa_per_target | +0.101 | Modest signal |
| `rb_fumble_rate` | 452 | +0.178 | 0.01 | −0.113 | rb_rush_epa_per_attempt | +0.033 | NOISE (already at light weight) |
| **nflvs-derived:** | | | | | | | |
| `rb_yards_per_carry` | 449 | +0.317 | 0.58 | **+0.790** | rb_ryoe_per_attempt | +0.175 | MEANINGFUL OVERLAP |
| `rb_rush_td_rate` | 449 | +0.220 | 0.02 | +0.442 | rb_rush_epa_per_attempt | +0.085 | Independent / weak validity |
| `rb_rush_first_down_rate` | 449 | +0.225 | 0.04 | +0.676 | rb_rush_success_rate | +0.079 | MEANINGFUL OVERLAP |
| `rb_catch_rate` | 403 | +0.158 | 0.07 | +0.402 | rb_rec_epa_per_target | +0.041 | NOISE |
| `rb_rec_td_rate` | 403 | +0.089 | 0.03 | +0.419 | rb_rec_epa_per_target | +0.003 | NOISE |
| **NGS rushing (re-validated, all rejected previously):** | | | | | | | |
| `rb_ngs_efficiency` | 405 | +0.279 | 0.40 | **−0.653** | rb_ryoe_per_attempt | −0.061 | MEANINGFUL OVERLAP (inverse) |
| `rb_ngs_time_to_los` | 405 | +0.532 | 0.14 | −0.168 | rb_rush_success_rate | +0.069 | Style metric / weak validity |
| `rb_ngs_rush_pct_over_expected` | 360 | +0.131 | 0.04 | +0.592 | rb_ryoe_per_attempt | +0.032 | NOISE |
| `rb_ngs_pct_eight_defenders` | 405 | +0.397 | 8.22 | +0.126 | rb_ryoe_per_attempt | −0.003 | Usage marker / zero validity |
| `rb_ngs_ryoe_per_att` | 360 | +0.325 | 0.53 | **+0.961** | rb_ryoe_per_attempt | +0.142 | STRONG REDUNDANCY (duplicate) |
| **PFR rush advanced (2018+) — NEW DATA SOURCE:** | | | | | | | |
| `rb_pfr_broken_tackle_rate` | 356 | +0.175 | 0.03 | +0.332 | rb_ryoe_per_attempt | +0.186 | Review (modest YoY, decent validity) |
| **`rb_pfr_yards_after_contact`** | 356 | **+0.313** | 0.37 | +0.596 | rb_ryoe_per_attempt | **+0.192** | **STRONG ADD candidate** |
| `rb_pfr_yards_before_contact` | 356 | +0.309 | 0.47 | +0.587 | rb_rush_epa_per_attempt | +0.056 | OL signal, not RB skill |

## Headline finding

**`rb_pfr_yards_after_contact` is the strongest candidate in the audit.** Per-rush yards after first contact — measures pure RB skill (breaking tackles, falling forward, second-effort yardage). Validity **+0.192**, higher than ANY current component (max was RYOE at +0.130). Modest YoY (+0.313) and only moderate overlap with RYOE (+0.596 — RYOE captures total above-expected yards including OL/blocking; yards_after_contact isolates the post-contact portion).

**This is the closest equivalent we've found to `qb_rush_epa_per_rush` for QB or `wr_pfr_broken_tackle_per_rec` for WR — except this one has BETTER validity than current components, not weaker.** It's a real ADD candidate, not just a documented gap.

**Why not shipped in this revision:** requires a new ingest module for `pfr_advstats` rush data (which we don't currently ingest — we only have PFR defensive advstats). This is a Path B schema change: new migration, new ingest module, update to rb.py grader SQL, web layer changes. Estimated 0.5-1 day of work — bigger than the immediate weight tweak.

**Tracked as RB v1.4 in pending.md.** First priority schema-change ship after the remaining position audits.

## Per-candidate verdict + reasoning

### Currently shipped (v1.2 → v1.3 decisions)

**`rb_ryoe_per_attempt` — KEEP at 0.28.**
- Best YoY among rushing components (+0.246). Pre-adjusted for blocking + box count by NGS's expected-yards model. Independent of rush_epa (+0.588, modest overlap).
- Validity +0.130 — meaningful, just shy of "strong."
- Stays the primary rushing signal.

**`rb_rush_epa_per_attempt` — KEEP at 0.18.**
- Modest YoY (+0.120), best rushing validity (+0.139). Heavily redundant with success_rate (+0.725).
- Fix the redundancy on the success_rate side, not here.

**`rb_rush_success_rate` — LOWER from 0.14 → 0.05.** ← v1.3 SHIPPED
- Same EPA-vs-success-rate redundancy as QB and WR. Max |r| = +0.713 with rush_EPA — structural mathematical relationship.
- **Lowest validity of any current component (+0.079).** Highest redundancy. Clear reduction candidate.
- Now 5% share of formula; bounded.

**`rb_rec_epa_per_target` — KEEP at 0.05.**
- YoY +0.010 — essentially zero. Validates the v1.2 reduction (which used the cross-position audit's +0.027 finding; this re-measurement is even worse).
- At 0.05 the contribution is bounded; going to 0 would require schema change. Light weight is the right home.

**`rb_yac_over_expected_per_rec` — KEEP at 0.28.**
- Modest YoY (+0.200, right at the threshold), modest validity (+0.101). +0.589 overlap with rec_EPA — but rec_EPA is already lowered. This is the receiving signal.
- Keep at current weight.

**`rb_fumble_rate` — KEEP at −0.05.**
- YoY +0.178 (sub-threshold), validity +0.033. Already at light weight; the original v1.1 audit kept this because RB fumble distribution is genuinely discriminating (median 2 fumbles, max 7), distinct from WR fumble noise. Light weight is right.

### New high-value candidate (queued for Path B ship)

**`rb_pfr_yards_after_contact` — DOCUMENT as STRONG ADD; ship in v1.4.**
- Best validity in the audit (+0.192) — higher than any current RB component.
- Modest YoY (+0.313) and reasonable independence (max_r +0.596 with RYOE).
- Captures a real RB skill (post-contact yardage) currently not measured separately. Yards-after-contact differs from RYOE: RYOE includes both pre-contact (OL) and post-contact yards; yards_after_contact isolates the post-contact portion.
- Schema change required: new PFR rush ingest module + rb.py grader update + web layer.

**`rb_pfr_broken_tackle_rate` — DOCUMENT as borderline; revisit with v1.4.**
- Modest YoY (+0.175), good validity (+0.186), independent of existing components (max_r +0.332).
- Captures broken-tackle skill specifically. Conceptually overlaps with yards_after_contact (broken tackles → post-contact yards). If we add yards_after_contact, this may be redundant — score the pair when both are computable.

### Strong-redundancy rejections

**`rb_ngs_ryoe_per_att` — REJECT (duplicate).** +0.961 with our `rb_ryoe_per_attempt`. Same metric, possibly slight definitional difference. Already captured.

**`rb_yards_per_carry` — REJECT.** +0.790 with RYOE. Volume-correlated, weaker signal of same skill.

**`rb_rush_first_down_rate` — REJECT.** +0.676 with rush_success_rate (chain-moving = positive EPA = success). Same family.

### Style markers / noise

**`rb_ngs_efficiency` — REJECT.** −0.653 with RYOE (inverse — NGS efficiency measures lateral dancing; effective backs run straight). Confirmed prior research.

**`rb_ngs_rush_pct_over_expected` — REJECT.** +0.592 with RYOE + weak YoY (+0.131). Duplicate.

**`rb_ngs_pct_eight_defenders` — REJECT.** Usage marker (loaded boxes the RB faces). Validity essentially zero. Already baked into RYOE's expected-yards model.

**`rb_ngs_time_to_los` — REJECT.** Strongest YoY in the audit (+0.532!) but validity +0.069 (weak). Pure style metric — Henry (slow but powerful) and Gibbs (quick) both succeed. Doesn't predict Pro Bowl.

**`rb_pfr_yards_before_contact` — REJECT (OL signal).** YoY +0.309, max_r +0.587 with rush_EPA, validity +0.056. Measures OL quality, not RB skill. The pre-contact yardage is what the blockers create.

**`rb_rush_td_rate`, `rb_rec_td_rate`, `rb_catch_rate`** — all rejected for combinations of weak YoY, weak validity, or overlap with EPA.

## What this audit confirms

1. **EPA-vs-success-rate redundancy is a structural pattern across all positions.** Now confirmed at QB (r=0.88), WR (r=0.76), and RB (r=0.71). Mathematical, not coincidental. Should be expected at TE.

2. **`rb_rec_epa_per_target` truly is noise** at RB sample sizes (YoY +0.010 in this audit; +0.027 in the cross-position YoY audit). v1.2's reduction was the right call.

3. **`rb_pfr_yards_after_contact` is the highest-value candidate found in any audit so far.** Unlike the QB rush gap or WR broken-tackle gap (both weak validity), this one has +0.192 validity — better than current RB components. Worth a Path B ship.

4. **NGS rushing offers no additional signal.** All 5 NGS candidates rejected. The pre-adjusted RYOE we already use is the right primary rushing signal; NGS efficiency/time-to-los/pct-eight-defenders are either duplicates or style markers.

## Decision: RB v1.3 weight change

| Component | v1.2 | v1.3 | Share v1.2 | Share v1.3 |
|---|---:|---:|---:|---:|
| `rb_ryoe_per_attempt` | 0.28 | 0.28 | 29% | 32% |
| `rb_rush_epa_per_attempt` | 0.18 | 0.18 | 18% | 20% |
| **`rb_rush_success_rate`** | 0.14 | **0.05** | 14% | **6%** |
| `rb_rec_epa_per_target` | 0.05 | 0.05 | 5% | 6% |
| `rb_yac_over_expected_per_rec` | 0.28 | 0.28 | 29% | 32% |
| `rb_fumble_rate` | −0.05 | −0.05 | 5% | 6% |

Sum |w|: 0.98 → 0.89. Each surviving component gains a few percentage points of effective share as the redundant component shrinks.

**Validity gate passed:** RB composite vs next-year Pro Bowl correlation **improved from +0.243 → +0.247** post-regrade.

**Face-check 2024:** Top 4 unchanged (Henry, Gibbs, Saquon, Bucky Irving). Top 10: Henry, Gibbs, Saquon, Bucky, Jacobs, Cook, Bijan, Conner, Mason, Montgomery — all consensus or near-consensus elite. Biggest movers: Joe Mixon +4.17 (explosive), Najee Harris +2.90 (explosive), Bijan Robinson −3.29 (consistent), Montgomery −2.97 (consistent), Allgeier −3.16 (consistent). Same pattern as QB/WR — lowering success_rate weight relaxes the consistency-smoothing, so explosive-but-variable backs rise relative to high-success-rate operators.

## Queued: RB v1.4 — add `rb_yards_after_contact`

The highest-validity candidate emerged from this audit. To ship:

1. New migration: `db/migrations/00XX_pfr_rush_advstats.sql` — table for per-player-season PFR rush data.
2. New ingest module: `pipeline/src/nfl_grades/ingest/pfr_rush.py` — fetch via `nfl.load_pfr_advstats(stat_type='rush')`, aggregate to season totals.
3. Update `pipeline/src/nfl_grades/grading/rb.py`: pull yards_after_contact + carries; compute rate; add to stat_components write.
4. Update `weights.py`: add `RB_COMPONENT_YARDS_AFTER_CONTACT` + entry in `RB_V1_WEIGHTS` at ~0.10. Redistribute from existing components TBD via preview.
5. Web layer: types/index.ts, lib/grades.ts (label + description), lib/queries.ts (LEFT JOIN), LeaderboardTable.tsx (column), methodology page.
6. Full grade re-run (not regrade — schema changed).
7. ADR-0014 v1.4 revision history with the audit data.

Estimated 0.5-1 day. Tracked as a separate item in pending.md.
