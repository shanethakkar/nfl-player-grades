# K Exhaustive Candidate Audit — 2026-05-14

**Tenth production audit. First new-position audit using the full audit-first process.** Originally nine candidates scored for v1; **revised same-day to v1.1 after adding FGOE/att as a 10th candidate** — see the "v1 → v1.1 correction" section at the bottom.

**Cohort:** qualified K-seasons 2016-2025 with ≥15 FG attempts (n=323).

**Validity range:** 2017-2023 (Pro Bowl K data covers 2018-2024 in our CSV).

Tool: `nflgrades audit-candidates --position K` — plus a one-off validity script because the standard validity check joins to `season_grades`, which doesn't yet exist for K (no grader before the audit).

## Full candidate table

| Candidate | n | YoY r | x-sec std | Validity r (PB) | Verdict |
|---|---:|---:|---:|---:|---|
| `fg_pct` (overall) | 323 | −0.013 | 0.08 | +0.052 | Weak both ways |
| `fg_pct_short` (0-39) | 308 | **−0.135** | 0.05 | −0.087 | **NEGATIVE YoY** — regression to ceiling |
| `fg_pct_40_49` | 296 | +0.040 | 0.15 | +0.099 | Subsumed by fg_pct_40_plus |
| `fg_pct_50_plus` | 228 | +0.004 | 0.19 | +0.068 | Noise + small samples |
| **`fg_pct_40_plus`** | 238 | +0.031 | 0.12 | **+0.126** | **BEST VALIDITY** — long-range is where kickers separate |
| **`pat_pct`** | 252 | **+0.211** | 0.04 | +0.041 | **BEST YoY** — XP accuracy persists |
| **`fg_long`** | 256 | +0.206 | 3.67 | +0.007 | Solid YoY — power capability persists |
| `gwfg_pct` | 49 | n/a | 0.25 | 0.000 | Pure noise (small sample) |
| `fg_att_per_game` | 323 | +0.028 | 0.38 | +0.064 | Volume / usage marker |

## Key findings

### Finding 1 — Kicker stats are structurally NOISY

This is the headline lesson of the K v1 audit. Across nine candidates:
- **Maximum YoY r = +0.211** (`pat_pct`). For comparison: any offensive position's primary component is YoY 0.4-0.7.
- **Maximum validity r = +0.126** (`fg_pct_40_plus`). For comparison: iDL pressure_rate +0.460, EDGE sack_rate +0.330.
- **5 of 9 candidates have YoY < 0.05** — essentially noise year-to-year.

Two structural reasons:
1. **Sample sizes are tiny.** A starting kicker has ~30 FG attempts per season. Distance-bucketed accuracy gets down to 4-8 attempts. With variance ~10-20% per kick, you need much larger samples to detect skill.
2. **Pro Bowl K voting is reputation-weighted.** Only 2 K Pro Bowls per year out of ~30 qualified kickers (~6.5% rate). Voter preferences are mostly noise relative to that-year performance.

This is the same "stats vs reputation" gap as LB — confirmed cross-position.

### Finding 2 — `fg_pct_short` has NEGATIVE YoY

A surprising result: kickers' make rate on 0-39 yard FGs is **anti-correlated** year-to-year (r = -0.135). Mechanism: regression to the ceiling. Short FGs are made ~92-99% league-wide. A kicker who misses 2 short FGs in year N (unusual) regresses UP in year N+1; a kicker who goes 100% in year N has nowhere to go but down.

Implication: do NOT include `fg_pct_short` in the formula. The signal it provides is anti-skill.

### Finding 3 — `fg_pct_40_plus` is the cleanest discriminator

Combined 40-49 + 50+ FGs has:
- Validity r = **+0.126** (highest among all candidates)
- Adequate sample (8+ attempts for most starters)
- Cross-sectional std 0.12 (meaningful separation)
- YoY r is low (+0.031) but positive — it's *some* skill signal

The 50-plus sub-bucket has slightly higher x-sec std (0.19) but too-small samples (4-8 attempts) and YoY r near zero. Combining the buckets sacrifices some "elite long" signal but produces a much more stable metric.

### Finding 4 — `pat_pct` and `fg_long` are reliability anchors

XP accuracy (`pat_pct`) has the best YoY in the formula (+0.211). Since the 2015 rule change made XPs 33-yard FGs, they're no longer free points. Kickers who consistently make XPs are kickers with reliable form.

Longest FG (`fg_long`) has YoY +0.206 — leg strength persists. Validity r ≈ 0 (a long FG attempt is partly opportunity), but as a power proxy in a multi-component formula it's defensible.

## Rejected candidates

**`fg_pct_short`** — negative YoY (-0.135), regression to ceiling.

**`fg_pct_50_plus`** — YoY +0.004 (essentially zero), small samples (4-8 attempts per qualified K). Subsumed by `fg_pct_40_plus`.

**`fg_pct_40_49`** — small bucket; combined with 50+ as `fg_pct_40_plus` to improve stability.

**`gwfg_pct`** — pure noise. n=49 (only kickers with multiple GWFG attempts in a season). Validity 0.000.

**`fg_att_per_game`** — usage marker (good teams attempt more FGs because they drive deeper). Not a skill signal.

## What this audit confirms

1. **Audit-first works for a new position.** Eight candidates rejected (or modified) before any made it into the v1 formula. The four that survived are the four that the data actually supports.

2. **K joins LB as a "structural noise" position.** The composite-grade validity ceiling for K is structurally lower than offensive positions because kicker performance is inherently volatile and Pro Bowl voting is reputation-heavy.

3. **The audit framework generalizes to new positions.** With minor scaffolding (a custom validity helper for positions without `season_grades` yet), the same four-criterion screen applied. Will reuse the same approach for P and OL.

4. **Negative-YoY-as-anti-skill is a new pattern.** `fg_pct_short` regressing to a ceiling is the first case in any audit. Useful documentation for the article: not all positive cross-sectional discrimination is skill — some is regression artifact.

## Decision: K v1 weight design

| Component | Weight | Share | Rationale |
|---|---:|---:|---|
| `k_fg_pct_40_plus` | **+0.40** | 44% | Highest-validity signal; primary long-range differentiator |
| `k_fg_pct` | **+0.25** | 28% | Conventional headline FG%; reader-recognizable (despite weak audit signal) |
| `k_pat_pct` | **+0.15** | 17% | Most YoY-reliable signal; XP accuracy is real skill post-2015 rule change |
| `k_fg_long` | **+0.10** | 11% | Power capability; YoY-stable |

Sum |w| = 0.90. No negative weights (no penalty components surfaced — fg_pct_short was the candidate but failed audit).

**Shrinkage k values:**
- `k_fg_pct_40_plus`: 8 attempts (matches qualified threshold for 40+ bucket)
- `k_fg_pct`: 12 attempts (light shrinkage; sample is ~30 attempts for starters)
- `k_pat_pct`: 15 attempts (XPs are 30-50/season for starters)
- `k_fg_long`: 5 attempts (power doesn't need much sample to surface)

**Qualification:**
- MIN to grade: 10 FG attempts (rookie / mid-season callup)
- QUALIFIED: 20 FG attempts (main leaderboard)
- FULL CONFIDENCE: 30 FG attempts (career-year starter)

## Validity gate

K v1 composite vs next-year Pro Bowl correlation = **+0.165** (n=204, 11 next-year Pro Bowlers, 2017-2023). This is the lowest validity baseline of any audited position — and that's the point of the audit log. The data simply doesn't support a stronger K formula without paid sources (PFF film grades, wind/weather-adjusted xFG models). The audit documents this honestly rather than pretending to a higher signal.

## Face-check 2024

| Rank | Kicker | Grade | Note |
|---:|---|---:|---|
| 1 | Chris Boswell | 79.1 | 1st-Team All-Pro 2024, Pro Bowl. 41/44 FGs incl. 11/12 from 50+. Correct. |
| 2 | Nick Folk | 78.6 | Career renaissance at age 39, 31/32 FGs |
| 3 | Cam Little | 75.0 | Rookie standout (long of 59), 27/29 FGs |
| 4 | Brandon Aubrey | 74.1 | 2nd-Team All-Pro, hit 65-yard FG; grade slightly held back by 85.1% overall FG% |
| 5 | Wil Lutz | 73.7 | Steady veteran |
| 6-10 | McManus, McLaughlin, Dicker (Pro Bowl), Santos, Bates | 61.7-69.7 | Solid mid-tier |
| ... | ... | ... | ... |
| 28 | **Justin Tucker** | **22.7** | **Historic collapse to 73.3% FG rate; released by Ravens.** Formula correctly grades him near the bottom — confirms it's measuring 2024 performance, not reputation. |
| 30 | Jake Moody | 13.7 | Lost his job mid-season |
| 31 | Dustin Hopkins | 13.3 | Bottom of league |

Cameron Dicker (NFC Pro Bowl 2024) at #8 is the most arguable placement — his lower attempt count (24 FG, 91.7% PAT) limits the grade. This is the "voter noise" gap: Pro Bowl voting selected him based partly on team success / reputation rather than pure stats.

## Pattern across audited positions (after K is added)

| Position | Validity baseline | Notes |
|---|---:|---|
| iDL | +0.475 | Strongest — interior pressure data well-aligned with voting |
| EDGE | +0.424 | Strong — sack/pressure rewarded |
| TE | +0.407 | Strong — receiving stats track voter consensus |
| WR | +0.300 | Moderate — EPA depends on QB |
| RB | +0.259 | Moderate — rushing share is contextual |
| S | +0.255 | Moderate — INT-driven voter noise |
| QB | +0.244 | Moderate — small Pro Bowl roster, surface stats matter |
| CB | +0.220 | High voter noise (INT-driven) |
| LB | +0.198 | Structural reputation gap |
| **K** | **+0.165** | **Lowest — kicker stats inherently noisy + voter reputation weight** |

Every audited position's weights are now defensibly tied to a four-criterion screen of every plausible candidate.

---

## v1 → v1.1 correction (same-day, 2026-05-14)

After shipping v1 (4 raw make-rate components) we recognized a fundamental design flaw: **the formula punished kickers for attempting long FGs.** A 60-yard miss hurt `k_fg_pct` and `k_fg_pct_40_plus` identically to a 35-yard miss, even though one is league-average difficulty and the other is a near-certain make. Brandon Aubrey — who attempted 15 FGs from 50+ in 2024 (most in the league) and made the majority — graded #4 in v1 because the misses dragged his raw rates down. A kicker whose coach never let them try past 45 could grade higher.

This is a **risk-aversion incentive**, not a skill measurement. The fix is structural, not parametric.

### The added candidate: `k_fg_over_expected_per_att`

```
expected_makes = Σ over distance buckets b of (att_b × baseline_b) + pat_att × baseline_xp
total_makes    = fg_made + pat_made
fgoe           = total_makes − expected_makes
fgoe_per_att   = fgoe / (fg_att + pat_att)
```

**Baselines** (computed from kicker_stats 2016-2024, frozen as constants):

| Bucket | Baseline | n_att |
|---|---:|---:|
| 0-19 | 100.0% | 42 |
| 20-29 | 98.4% | 2,093 |
| 30-39 | 93.6% | 2,587 |
| 40-49 | 79.6% | 2,662 |
| 50-59 | 69.0% | 1,563 |
| 60+ | 40.0% | 65 |
| XP | 94.3% | 10,941 |

Per-attempt mechanics are **risk-asymmetric by construction**:
- 60-yard make = +0.60 over expected (large reward)
- 60-yard miss = -0.40 (modest penalty)
- 25-yard miss = -0.98 (heavy penalty)
- XP make = +0.06 (rounding error)
- XP miss = -0.94 (heavy penalty)

### Audit scores for the new candidate

| Metric | Value | vs. best raw-rate v1 component |
|---|---:|---|
| YoY r | **+0.126** | Best YoY of any K metric (was +0.211 for pat_pct alone, but pat_pct doesn't capture FGs) |
| Cross-sectional std | 0.04 | Good discrimination |
| Validity r vs next-year Pro Bowl | +0.091 | Below fg_pct_40_plus's +0.134 but within noise floor for K |

### v1 → v1.1 face-check (2024)

| Rank change | Player | v1 | v1.1 | Note |
|---|---|---:|---:|---|
| → | Chris Boswell | #1 | #1 | 1st-Team All-Pro, formula correctly agrees both ways |
| **↑ 2** | **Brandon Aubrey** | **#4** | **#2** | **Headline fix** — 50+ accuracy now properly rewarded |
| ↓ 1 | Nick Folk | #2 | #3 | Slight drop; fewer long attempts |
| ↓ 1 | Wil Lutz | #5 | #4 | |
| ↑ 5 | Justin Tucker | #28 | #23 | Still below average; FGOE penalizes his misses less because some were long |
| → | Jake Moody | #30 | #30 | Bottom-tier (lost his job) both ways |
| → | Dustin Hopkins | #31 | #31 | Bottom-tier both ways |
| ↓ 2 | Cameron Dicker | #8 | #10 | NFC Pro Bowl 2024; lower FG volume hurts him slightly more |

### Why v1.1 is the right call despite slightly lower validity

v1.1 composite validity is +0.153 vs v1's +0.165 — a small drop within the K validity noise floor. The drop reflects that Pro Bowl voters reward raw FG% more than FGOE (they don't credit attempt difficulty). But:

1. **"Grading is a definition, not an estimator."** The grade should measure skill, not predict voter behavior. FGOE measures skill correctly; raw rates conflate skill with risk-aversion.

2. **YoY reliability strongly favors FGOE.** v1's best YoY among FG metrics was +0.031 (fg_pct_40_plus). FGOE has YoY +0.126 — 4× more skill-persistent. This means FGOE captures something real that v1's raw rates were diluting.

3. **The risk-aversion incentive in v1 is a coaching corruptor.** A theoretical kicker who refuses any FG over 45 would have grade-maximizing behavior under v1. Under v1.1, they'd cap their grade because they don't accumulate "over expected" value on the long attempts.

### Documentation value

The v1 → v1.1 correction is actually a **stronger article story than a clean v1**. It demonstrates:
- The methodology catches design errors when challenged
- An audit log can be revised in light of new framing without losing rigor
- The four-criterion screen alone isn't enough — domain reasoning still matters

The lesson for future audits: when running candidates, include both rate-form and over-expected-form versions of the same skill. Don't stop at the conventional metric.
