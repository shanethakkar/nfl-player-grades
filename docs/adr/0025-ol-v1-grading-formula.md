# ADR-0025 — OL v1 Grading Formula (TEAM-LEVEL)

**Status:** Accepted (v1 audit-first release — 2026-05-14)
**Date:** 2026-05-14

---

## Context

Offensive line is the twelfth and final position in the foundation queue. Designed audit-first per the locked methodology. This ADR is structurally different from every prior position ADR because **the grading entity is a team-season, not a player-season.**

### Why team-level (and not per-player)

nflverse data does not attribute pressures, sacks, run-blocking lanes, or pulled-block assignments to specific offensive linemen. Without paid PFF film grades, individual OL grading is not computable. The play-by-play feed records "X played QB, Y rushed, Z caught" but not "the LG missed his block."

Three options were considered:

1. **Skip OL entirely.** Honest, but leaves a gap — every other position is graded.
2. **Faked individual grades.** Distribute team OL outcomes across the 5 starters by snap share. This would invent attribution from nothing and is methodologically dishonest.
3. **Grade the OL as a UNIT per (team_id, season).** Honest about what the data supports. Matches how analysts and coaches actually discuss OL ("Eagles OL was elite in 2024", not "Lane Johnson was elite").

We chose **option 3**. The grading entity is the team-season offensive line.

---

## Data Sources

| Source | Columns used | Coverage |
|---|---|---|
| `pbp` | `posteam`, `qb_dropback`, `sack`, `qb_hit`, `rush_attempt`, `rushing_yards`, `epa`, `penalty_type`, `penalty_team` | 2018+ (limited by PFR rush availability for YBC) |
| `pfr_advstats_rush` | `rushing_yards_before_contact` summed by `team` | 2018+ |

Aggregated to one row per (team_id, season) in `team_ol_stats` (migration 0018).

---

## Schema (new tables, parallel to player-grading tables)

```sql
team_ol_stats        -- raw counts per team-season (sacks/dropbacks/rushes/YBC/etc.)
team_ol_components   -- per-component values, mirrors stat_components shape
team_ol_grades       -- composite grade per team-season, mirrors season_grades shape
```

Kept entirely separate from `season_grades` / `stat_components` so that player-centric queries don't need to learn a team-OL exception.

---

## Components (v1, 2026-05-14)

| Component | Formula | Weight | Direction |
|---|---|---|---|
| `ol_yards_before_contact_per_carry` | `yards_before_contact / rushes` | **+0.45** | higher = better |
| `ol_pressure_proxy_per_dropback` | `(sacks_allowed + qb_hits_allowed) / dropbacks` | **−0.45** | lower = better |

Sum |weights| = 0.90. **Symmetric 50/50 run-block / pass-block split.** Both metrics had nearly identical YoY reliability in the audit (+0.42 each).

---

## Qualification

Every team that played a season is graded (32/season × 8 seasons = 256 team-seasons). No qualification threshold — all teams have full-season volume on both denominators (rushes ≈ 400-550, dropbacks ≈ 500-700).

Confidence is fixed at 1.0 for the same reason.

---

## Shrinkage k Values

| Component | k | Rationale |
|---|---|---|
| `ol_yards_before_contact_per_carry` | 30 carries | Light — every team has 400+ carries |
| `ol_pressure_proxy_per_dropback` | 40 dropbacks | Light — every team has 500+ dropbacks |

Shrinkage is light because the per-team-season sample is large; we only want to bound noise from outlier early-season behavior, not pull strongly toward the mean.

---

## Design Rationale

### Yards Before Contact per carry (run-block, +0.45)

YBC isolates OL skill from RB skill. After-contact yards belong to the RB (breaking tackles, falling forward, second-effort yardage); before-contact yards belong to the OL (creating lanes, sustaining blocks long enough for the RB to reach the second level).

The audit returned YoY r = +0.424 — best of any candidate tested. The cleanest pure-OL run-block signal in the dataset.

### Pressure proxy per dropback (pass-block, −0.45)

`(sacks + qb_hits) / dropbacks` — the broadest pass-block damage signal we can compute from nflverse. Captures both extremes:
- **Sacks**: catastrophic — 7-8 yard losses, sometimes turnovers
- **QB hits**: meaningful contact even when the QB gets the throw off, often forces a subsequent miss or injury

The audit verified that standalone `sacks_allowed_per_dropback` and `qb_hits_allowed_per_dropback` are **subsumed** by this combined metric (max_r ≈ 0.86–0.96 with `pressure_proxy`). Using the combined version captures more of the OL's pass-block performance without double-counting.

We don't have full pressures (sacks + hits + hurries) because nflverse pbp doesn't track hurries. PFR has per-defender pressure totals but mapping them back to "pressures allowed by team X" requires a join we deferred for v2.

### 50/50 split

Both signals had nearly identical YoY (+0.42). Neither has a clear dominance argument. A 60/40 lean toward pass-block (modern NFL is pass-heavy) was considered but ultimately rejected as arbitrary without external evidence.

### Documentation note: PHI #5 in 2024

Eagles OL is widely considered elite, but our formula puts them at #5 in 2024 with a 22.43% pressure rate (above league average for top-tier OLs). This is QB-dependent: Jalen Hurts holds the ball longer and takes hits while extending plays, inflating the pressure_proxy for what is otherwise a strong OL. This is a known limitation of using pbp pressure data — QB style mixes into the OL signal. Documented; not fixable without per-player blame attribution.

---

## Validity Gate — Intentionally Skipped

Per the locked plan and user decision: there is no "All-Pro OL unit" award. The closest proxy — counting next-year individual Pro Bowl OL per team — is too noisy to use as a hard gate (some Pro Bowls go to bad-unit veterans on reputation, e.g., Trent Williams on weaker 49ers lines).

We document the team-Pro-Bowl-OL-count as a possible future validity proxy but do not use it for v1 ship decisions. The audit relied on three criteria only: reliability (YoY), cross-sectional discrimination, and independence (max_r vs other candidates).

---

## Rejected Candidates (audit log)

13 candidates tested. Results in [docs/grading/audits/2026-05-14-exhaustive-ol.md](../grading/audits/2026-05-14-exhaustive-ol.md).

**Subsumed by the chosen pair:**
- `sacks_allowed_per_dropback` — max_r +0.863 with pressure_proxy
- `qb_hits_allowed_per_dropback` — max_r +0.957 with pressure_proxy
- `sack_per_contact` — max_r +0.620 with sacks_allowed
- `rush_yards_per_carry` — max_r +0.825 with rush_explosive_rate; mixes OL with RB after-contact
- `rush_epa_per_carry` — max_r +0.839 with rush_success_rate; mixes OL with RB and scheme
- `rush_success_rate` — max_r +0.839 with rush_epa
- `rush_explosive_rate` — max_r +0.825 with rush_yards
- `rush_stuff_rate` — independent (max_r −0.548) but YoY +0.219 (weak)

**Failed YoY (noise):**
- `false_start_rate` — YoY +0.129 (below 0.20 threshold)
- `holding_rate` — YoY +0.177
- `ol_penalty_rate` — YoY +0.168

The penalty exclusion deserves explicit defense. False starts and holding ARE the OL — those are literally OL players committing penalties, conceptually owned by the unit. We considered including them at small weight on definitional grounds. We rejected this because:

1. The audit YoY is decisively below the noise threshold (0.13–0.18 vs 0.20 floor).
2. We made the same "include despite weak signal on conceptual grounds" mistake with **P v1 blocked_rate** and reversed it within hours when the user pointed out that low audit signal means the metric isn't measuring what we think it's measuring.
3. Penalty rates likely reflect roster turnover at OL positions year-to-year — not unit-level skill that persists.

If a v2 audit shows penalty signal at smaller cohort or different bucketing, we can revisit.

---

## Alternatives Considered

**Single component (parallel to K v1.1's FGOE-only formula):** Considered using just `pressure_proxy` or just YBC. Rejected because pass-block and run-block are conceptually distinct skills and both passed the audit at equivalent strength. A 1-component formula would force ignoring a real signal.

**Three components with stuff_rate (+0.40 / +0.40 / -0.10):** Considered. Stuff rate is independent (audit max_r −0.548) and is a real concept ("got blown up at the line"). Rejected because YoY +0.219 is just barely above the noise floor and adding a third component for marginal signal violates parsimony.

**60/40 pass-heavy split:** `pressure_proxy −0.55, YBC +0.35`. Reflects modern NFL where pass blocking matters more. Rejected as arbitrary — both signals had equal audit strength, and we didn't want to bake in an editorial preference without data support.

**Per-player OL grading (synthetic blame attribution):** See "Why team-level" above. Rejected as methodologically dishonest given nflverse data limitations.

**Reusing `season_grades` with synthetic player_id = team_id:** Considered for backwards compatibility. Rejected because every player-centric query (player profile, name resolution, snap-counts join) would need a team-OL exception. Cleaner to have separate tables.

---

## Known Limitations

**No hangtime / no QB pocket-time isolation.** Pressure proxy mixes OL skill with QB style (Hurts vs Goff face dramatically different "pressure" rates for the same OL quality).

**No hurry data.** Full pressure (sacks + hits + hurries) would be richer than our (sacks + hits). PFR has it per-defender; mapping that to team-allowed totals requires a join we deferred.

**No scheme adjustment.** Wide-zone teams generate more YBC than gap-scheme teams at equal OL talent. Our metric doesn't normalize.

**No injury context.** A team that lost its starting LT and RG mid-season isn't the same OL it started with. We grade the team-season aggregate as if it were one unit.

**No All-Pro OL unit award means no validity gate.** This is by design (see above) but means OL is the only graded position without a Pro Bowl validity check.

---

## Consequences

- OL grades available 2018+ (PFR rush limit).
- Pipeline requires: `team_ol_stats` table (migration 0018), pbp ingest (already running), pfr_advstats_rush (already running for RB v1.4).
- Web: OL appears as a position tab between TE and CB in the UX. Backend: separate table; frontend: shows up alongside players.
- Player profile pages are unchanged — OL data lives in different tables and players don't have OL grades attached.

---

## Future Work

**v2 candidates:**
- True pressure rate (sacks + hits + hurries / dropbacks) by joining PFR per-defender data back to team-opponent.
- Pocket-time-adjusted pressure rate (subtract expected pressure given QB time-to-throw).
- Scheme-adjusted YBC (rate vs expected given personnel and box count).
- Pro Bowl OL count as a sanity-check (not gate).
- Pass-block / run-block grade split if user wants two grades surfaced separately.

Any v2 add will go through the same three-criterion audit before shipping.
