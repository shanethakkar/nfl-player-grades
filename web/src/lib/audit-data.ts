/**
 * Hardcoded audit data for the /methodology/audit page.
 *
 * Data sources:
 *   - docs/grading/audits/2026-05-14-exhaustive-{position}.md
 *   - docs/adr/00{13..25}-*-grading-formula.md
 *
 * The audit was a one-time exercise (locked 2026-05-14). When the
 * methodology evolves, update this file alongside the audit docs.
 *
 * No DB query — this data is static and fits comfortably in the JS bundle
 * (~15kB before gzip).
 */

export type Verdict =
  | "shipped"        // in the formula
  | "subsumed"       // mathematically inside another component
  | "redundant"      // independent but overlaps a chosen one
  | "noise"          // failed YoY threshold
  | "small-sample"   // event too rare to grade
  | "context-only"   // displayed on leaderboard but not scored
  | "anti-skill";    // negative YoY (regression artifact)

export type Criterion = "yoy" | "xsect" | "independence" | "validity";

export type AuditCandidate = {
  position: string;
  name: string;          // ungrouped — e.g. "fg_pct_overall"
  displayName: string;   // human-readable — e.g. "FG% (overall)"
  yoyR: number | null;
  xsectStd: number | null;
  maxR: number | null;       // max abs Pearson r vs other candidates
  maxRPartner: string | null;
  validityR: number | null;  // null when validity gate skipped (OL)
  verdict: Verdict;
  weight?: number;       // weight in formula if shipped
  rationale: string;
};

export type ValidityRow = {
  position: string;
  validity: number | null;   // null = no validity gate (OL)
  cohortN: number;
  proBowlsN: number | null;
  ceilingNote?: string;      // why the validity is what it is
};

export type FunnelRow = {
  position: string;
  totalCandidates: number;
  inFormula: number;
  cohortPerSeason: number;   // n graded per season
};

// ---------------------------------------------------------------------------
// 4-criterion framework explainer
// ---------------------------------------------------------------------------

export const CRITERIA: Array<{
  key: Criterion;
  title: string;
  short: string;
  technical: string;
  plain: string;
}> = [
  {
    key: "yoy",
    title: "Reliability",
    short: "Year over year",
    technical:
      "Pearson r between a player's value at season t and season t+1, averaged across all qualified player-season pairs.",
    plain:
      "Does the same player tend to score similarly two years in a row? If a metric jumps around at random, it's measuring noise, not skill.",
  },
  {
    key: "xsect",
    title: "Discrimination",
    short: "Cross-sectional spread",
    technical:
      "Standard deviation of the metric within a single season, in z-units. A near-zero std means everyone scores the same.",
    plain:
      "Does the metric actually separate players within a season? If everyone is at 95% on it, it can't differentiate elite from average.",
  },
  {
    key: "independence",
    title: "Independence",
    short: "Adds new info",
    technical:
      "Maximum absolute Pearson r between this candidate's z-scores and every other candidate's z-scores. ≥0.85 = strong redundancy.",
    plain:
      "If this metric is just a different way of saying what another one already says, including both is double-counting.",
  },
  {
    key: "validity",
    title: "Predictive validity",
    short: "Pro Bowl correlation",
    technical:
      "Pearson r between the metric value at season t and a 0/1 flag for whether the player made the Pro Bowl in season t+1.",
    plain:
      "Does what this metric measures actually look like \"good football\" to expert voters? An imperfect proxy, but the best public ground truth.",
  },
];

// ---------------------------------------------------------------------------
// Validity scoreboard — all 12 positions, sorted high to low
// ---------------------------------------------------------------------------

export const VALIDITY_SCOREBOARD: ValidityRow[] = [
  { position: "iDL", validity: 0.475, cohortN: 415, proBowlsN: 45,
    ceilingNote: "Strongest — interior pressure stats align well with what voters reward." },
  { position: "EDGE", validity: 0.424, cohortN: 487, proBowlsN: 64,
    ceilingNote: "Strong — sack and pressure stats track Pro Bowl voting closely." },
  { position: "TE", validity: 0.407, cohortN: 224, proBowlsN: 32,
    ceilingNote: "Strong — receiving stats align with voter consensus." },
  { position: "WR", validity: 0.300, cohortN: 574, proBowlsN: 70,
    ceilingNote: "Moderate — EPA depends partly on QB quality." },
  { position: "RB", validity: 0.259, cohortN: 322, proBowlsN: 45,
    ceilingNote: "Moderate — rushing share is partly contextual (game script, OL)." },
  { position: "S", validity: 0.255, cohortN: 459, proBowlsN: 35,
    ceilingNote: "Moderate — INT-driven voter noise." },
  { position: "QB", validity: 0.244, cohortN: 239, proBowlsN: 53,
    ceilingNote: "Moderate — small Pro Bowl roster, surface stats matter most." },
  { position: "CB", validity: 0.220, cohortN: 731, proBowlsN: 49,
    ceilingNote: "High voter noise — CB Pro Bowl voting is heavily INT-driven." },
  { position: "LB", validity: 0.198, cohortN: 325, proBowlsN: 27,
    ceilingNote: "Reputation gap — voters reward LB reputation more than box score." },
  { position: "K", validity: 0.153, cohortN: 204, proBowlsN: 11,
    ceilingNote: "Stats-vs-reputation gap — only 2 K Pro Bowls/year, noisy voting." },
  { position: "P", validity: 0.122, cohortN: 219, proBowlsN: 11,
    ceilingNote: "Lowest — punter Pro Bowl voting is the most reputation-driven." },
  { position: "OL", validity: null, cohortN: 256, proBowlsN: null,
    ceilingNote: "No validity gate — there is no \"All-Pro OL unit\" award. Documented honestly." },
];

// ---------------------------------------------------------------------------
// Funnel — total candidates evaluated vs in formula (per position)
// ---------------------------------------------------------------------------

export const FUNNEL: FunnelRow[] = [
  { position: "QB",   totalCandidates: 19, inFormula: 3, cohortPerSeason: 35 },
  { position: "RB",   totalCandidates: 22, inFormula: 7, cohortPerSeason: 45 },
  { position: "WR",   totalCandidates: 22, inFormula: 6, cohortPerSeason: 90 },
  { position: "TE",   totalCandidates: 22, inFormula: 6, cohortPerSeason: 35 },
  { position: "OL",   totalCandidates: 13, inFormula: 2, cohortPerSeason: 32 },
  { position: "CB",   totalCandidates: 16, inFormula: 4, cohortPerSeason: 110 },
  { position: "S",    totalCandidates: 16, inFormula: 6, cohortPerSeason: 70 },
  { position: "EDGE", totalCandidates: 10, inFormula: 5, cohortPerSeason: 80 },
  { position: "iDL",  totalCandidates: 10, inFormula: 5, cohortPerSeason: 70 },
  { position: "LB",   totalCandidates: 19, inFormula: 6, cohortPerSeason: 45 },
  { position: "K",    totalCandidates: 10, inFormula: 1, cohortPerSeason: 31 },
  { position: "P",    totalCandidates: 10, inFormula: 2, cohortPerSeason: 32 },
];

export const FUNNEL_TOTALS = FUNNEL.reduce(
  (acc, row) => ({
    totalCandidates: acc.totalCandidates + row.totalCandidates,
    inFormula: acc.inFormula + row.inFormula,
    positions: acc.positions + 1,
  }),
  { totalCandidates: 0, inFormula: 0, positions: 0 },
);

// ---------------------------------------------------------------------------
// WR audit (centerpiece worked example) — all 22 candidates
// Source: docs/grading/audits/2026-05-14-exhaustive-wr.md
// ---------------------------------------------------------------------------

export const WR_AUDIT: AuditCandidate[] = [
  // Currently shipped (after v1.3 audit)
  { position: "WR", name: "wr_rec_epa_per_target", displayName: "Receiving EPA / target",
    yoyR: 0.310, xsectStd: 0.27, maxR: 0.760, maxRPartner: "wr_success_rate_per_target",
    validityR: 0.244, verdict: "shipped", weight: 0.35,
    rationale: "Primary receiver value metric. Captures route-running and YAC in one number." },
  { position: "WR", name: "wr_yac_over_expected_per_rec", displayName: "YAC over expected",
    yoyR: 0.408, xsectStd: 0.78, maxR: 0.218, maxRPartner: "wr_separation",
    validityR: 0.156, verdict: "shipped", weight: 0.27,
    rationale: "NGS-derived. Captures broken-tackle and run-after-catch ability — distinct from EPA." },
  { position: "WR", name: "wr_separation", displayName: "Separation (NGS)",
    yoyR: 0.521, xsectStd: 0.40, maxR: 0.218, maxRPartner: "wr_yac_over_expected",
    validityR: 0.039, verdict: "shipped", weight: 0.10,
    rationale: "Best YoY of any WR candidate. Voters discount it (low validity), kept on skill-tree grounds." },
  { position: "WR", name: "wr_target_earn_rate", displayName: "Target earn rate",
    yoyR: 0.612, xsectStd: 0.054, maxR: 0.347, maxRPartner: "wr_rec_epa",
    validityR: 0.282, verdict: "shipped", weight: 0.15,
    rationale: "Bumped from 0.10 → 0.15 in v1.3 — highest validity in the formula, was underweighted." },
  { position: "WR", name: "wr_success_rate_per_target", displayName: "Success rate",
    yoyR: 0.272, xsectStd: 0.06, maxR: 0.760, maxRPartner: "wr_rec_epa",
    validityR: 0.205, verdict: "shipped", weight: 0.05,
    rationale: "Lowered 0.08 → 0.05 in v1.3 — overlaps with EPA (success = % positive-EPA targets)." },
  { position: "WR", name: "wr_drop_rate", displayName: "Drop rate (FTN)",
    yoyR: 0.124, xsectStd: 0.02, maxR: 0.108, maxRPartner: "wr_target_earn",
    validityR: -0.087, verdict: "shipped", weight: -0.05,
    rationale: "Light penalty. Real but noisy YoY — kept small to acknowledge drops without overweighting." },

  // Rejected — subsumed by chosen components
  { position: "WR", name: "wr_yards_per_reception", displayName: "Yards per reception",
    yoyR: 0.355, xsectStd: 1.86, maxR: 0.685, maxRPartner: "wr_yac_over_expected",
    validityR: 0.063, verdict: "subsumed",
    rationale: "Mostly captures YAC, which is already in the formula via YAC-OE." },
  { position: "WR", name: "wr_air_yards_per_target", displayName: "Air yards / target (NGS)",
    yoyR: 0.484, xsectStd: 1.55, maxR: 0.526, maxRPartner: "wr_target_earn",
    validityR: -0.034, verdict: "redundant",
    rationale: "Strong YoY but near-zero validity — voters don't reward depth-of-target alone." },
  { position: "WR", name: "wr_yards_per_target", displayName: "Yards per target",
    yoyR: 0.347, xsectStd: 0.93, maxR: 0.853, maxRPartner: "wr_rec_epa",
    validityR: 0.137, verdict: "subsumed",
    rationale: "Same skill as Receiving EPA / target but without the schedule-of-targets adjustment." },
  { position: "WR", name: "wr_catch_pct", displayName: "Catch percentage",
    yoyR: 0.224, xsectStd: 0.04, maxR: 0.474, maxRPartner: "wr_drop_rate",
    validityR: -0.012, verdict: "redundant",
    rationale: "Near-zero validity. Inverse of drop_rate (already in formula) when you control for catchable balls." },
  { position: "WR", name: "wr_first_down_rate", displayName: "First-down rate",
    yoyR: 0.298, xsectStd: 0.05, maxR: 0.812, maxRPartner: "wr_success_rate",
    validityR: 0.184, verdict: "subsumed",
    rationale: "Strongly correlated with success rate; same underlying \"keeps drives going\" skill." },
  { position: "WR", name: "wr_racr", displayName: "RACR (yards / air yards)",
    yoyR: 0.212, xsectStd: 0.32, maxR: 0.601, maxRPartner: "wr_yac_over_expected",
    validityR: -0.045, verdict: "redundant",
    rationale: "Mostly a YAC signal; we use YAC-OE which is more targeted." },
  { position: "WR", name: "wr_intended_air_yards", displayName: "Intended air yards (NGS)",
    yoyR: 0.487, xsectStd: 1.78, maxR: 0.844, maxRPartner: "wr_air_yards_per_target",
    validityR: -0.041, verdict: "redundant",
    rationale: "Usage marker (depth of target), not a skill signal." },
  { position: "WR", name: "wr_avg_cushion", displayName: "Avg cushion (NGS)",
    yoyR: 0.314, xsectStd: 0.95, maxR: 0.183, maxRPartner: "wr_separation",
    validityR: -0.018, verdict: "noise",
    rationale: "Pre-snap CB depth — defensive scheme indicator, not WR skill." },
  { position: "WR", name: "wr_yac", displayName: "YAC (raw, per reception)",
    yoyR: 0.442, xsectStd: 0.79, maxR: 0.731, maxRPartner: "wr_yac_over_expected",
    validityR: 0.108, verdict: "subsumed",
    rationale: "YAC-OE is the schedule-adjusted version and dominates raw YAC for skill measurement." },
  { position: "WR", name: "wr_target_share", displayName: "Target share",
    yoyR: 0.585, xsectStd: 0.061, maxR: 0.892, maxRPartner: "wr_target_earn",
    validityR: 0.245, verdict: "subsumed",
    rationale: "Almost identical to target_earn_rate (chose earn_rate because it normalizes by snaps)." },
  { position: "WR", name: "wr_wopr", displayName: "WOPR (target + air-yards composite)",
    yoyR: 0.517, xsectStd: 0.18, maxR: 0.821, maxRPartner: "wr_target_earn",
    validityR: 0.139, verdict: "subsumed",
    rationale: "Hand-tuned composite of target_share + air_yards_share — we score the components separately." },
  { position: "WR", name: "wr_air_yards_share", displayName: "Air yards share",
    yoyR: 0.544, xsectStd: 0.17, maxR: 0.737, maxRPartner: "wr_wopr",
    validityR: 0.098, verdict: "subsumed",
    rationale: "Subsumed by WOPR (which is subsumed by target_earn) — daisy-chain redundancy." },
  { position: "WR", name: "wr_contested_catch_pct", displayName: "Contested catch %",
    yoyR: 0.084, xsectStd: 0.16, maxR: 0.085, maxRPartner: "wr_drop_rate",
    validityR: 0.034, verdict: "noise",
    rationale: "Small samples (10-25 contested targets/year). YoY barely above zero." },
  { position: "WR", name: "wr_red_zone_target_share", displayName: "Red-zone target share",
    yoyR: 0.301, xsectStd: 0.11, maxR: 0.624, maxRPartner: "wr_target_earn",
    validityR: 0.218, verdict: "redundant",
    rationale: "Subsumed by overall target_earn (RZ targets are part of total)." },
  { position: "WR", name: "wr_intended_share_air_yards", displayName: "Share of team air yards (NGS)",
    yoyR: 0.498, xsectStd: 0.13, maxR: 0.913, maxRPartner: "wr_air_yards_share",
    validityR: 0.115, verdict: "subsumed",
    rationale: "Almost the same column as wr_air_yards_share." },
  { position: "WR", name: "wr_fumble_rate", displayName: "Fumble rate",
    yoyR: 0.013, xsectStd: 0.01, maxR: 0.078, maxRPartner: "wr_drop_rate",
    validityR: 0.041, verdict: "noise",
    rationale: "Removed in v1.1 — WR fumbles are too rare per season for skill signal. Was at -0.05 in v1." },
];

// ---------------------------------------------------------------------------
// iDL before/after — the "framework caught a real problem" case study
// Source: docs/grading/audits/2026-05-14-exhaustive-idl.md
//         docs/adr/0021-idl-v1-grading-formula.md
// ---------------------------------------------------------------------------

export const IDL_BEFORE_AFTER = {
  v1Weights: [
    { name: "idl_tfl_rate", display: "TFL rate", weight: 0.35 },
    { name: "idl_pressure_rate", display: "Pressure rate", weight: 0.30 },
    { name: "idl_sack_rate", display: "Sack rate", weight: 0.15 },
    { name: "idl_missed_tackle_rate", display: "Missed tackle rate", weight: -0.05 },
  ],
  v12Weights: [
    { name: "idl_pressure_rate", display: "Pressure rate", weight: 0.35 },
    { name: "idl_tfl_rate", display: "TFL rate", weight: 0.25 },
    { name: "idl_sack_rate", display: "Sack rate", weight: 0.20 },
    { name: "idl_tackles_per_snap", display: "Tackles per snap (NEW)", weight: 0.05 },
    { name: "idl_missed_tackle_rate", display: "Missed tackle rate", weight: -0.05 },
  ],
  problem:
    "v1 was designed around \"iDL = primarily a run-stopper.\" TFL was the heaviest weight at 35%. The exhaustive audit revealed this didn't match either the data or how voters evaluate iDL.",
  finding: [
    { metric: "Pressure rate", validity: 0.460, yoy: 0.689, weight: "0.30 → 0.35" },
    { metric: "Sack rate",     validity: 0.394, yoy: 0.450, weight: "0.15 → 0.20" },
    { metric: "TFL rate",      validity: 0.260, yoy: 0.371, weight: "0.35 → 0.25" },
  ],
  conclusion:
    "Pressure rate has BOTH the highest Pro Bowl validity AND the highest year-over-year reliability — it should be the primary iDL signal. The original \"run-stop\" assumption was an older positional archetype; modern voting rewards interior pass-rush (Aaron Donald → Chris Jones → Quinnen Williams → Dexter Lawrence lineage).",
  rebalanceImpact:
    "Validity moved +0.457 → +0.475 (largest defensive gain of any audit). Top-8 in 2024 are all consensus elite iDL: L. Williams, D. Lawrence (1st-Team All-Pro), C. Jones, Fiske (DROY runner-up), Buckner, Heyward, Vea, Q. Williams.",
  topMovers2024: [
    { player: "Cameron Heyward", v1Rank: 12, v12Rank: 6, change: "↑ 6", note: "Strong pressure year; was undervalued by v1's TFL focus" },
    { player: "Chris Jones", v1Rank: 5, v12Rank: 3, change: "↑ 2", note: "Already elite, formula now matches reputation" },
    { player: "Quinnen Williams", v1Rank: 11, v12Rank: 8, change: "↑ 3", note: "Rebalance helped pressure-first interior players" },
  ],
};

// ---------------------------------------------------------------------------
// Featured rejections — the "audit log" highlights
// Hand-picked across positions for the recurring patterns story
// ---------------------------------------------------------------------------

export const REJECTION_HIGHLIGHTS: Array<{
  position: string;
  candidate: string;
  reason: string;
  pattern: "subsumed" | "noise" | "anti-skill" | "context-only" | "small-sample";
  detail: string;
  yoy: number | null;
  validity: number | null;
}> = [
  {
    position: "K", candidate: "FG% (0-39 yards)",
    reason: "Negative YoY — regression to ceiling, not skill",
    pattern: "anti-skill",
    detail: "Short FGs are made ~95-99% league-wide. A kicker who misses 2 shorts in year 1 regresses UP next year. The metric is anti-correlated with itself year-over-year.",
    yoy: -0.135, validity: -0.087,
  },
  {
    position: "K", candidate: "Game-winning FG %",
    reason: "Pure noise (n=49)",
    pattern: "small-sample",
    detail: "GWFG happens 2-5 times per kicker per season. Validity returned 0.000. \"Clutch kicker\" is reputation, not stat.",
    yoy: null, validity: 0.000,
  },
  {
    position: "P", candidate: "Block rate",
    reason: "Snap/protection failure, not punter skill",
    pattern: "noise",
    detail: "v1 included it at -0.05 on \"punter conceptually owns the play\" grounds. v1.1 removed it after recognizing the audit said no signal. Most blocks are snap or protection issues.",
    yoy: -0.046, validity: -0.046,
  },
  {
    position: "P", candidate: "EPA per punt",
    reason: "Doesn't dominate — context-contaminated",
    pattern: "subsumed",
    detail: "K v1.1 used FGOE because it cleanly dominated raw FG%. The same approach for P (EPA per punt) lost to plain net average — punt EPA mixes punter skill with returner / coverage / wind.",
    yoy: 0.269, validity: 0.163,
  },
  {
    position: "S", candidate: "ADoT allowed",
    reason: "Scheme indicator, not skill",
    pattern: "noise",
    detail: "Average depth of target a safety faces — varies by scheme (free safety vs strong safety vs box) more than by skill.",
    yoy: 0.235, validity: -0.032,
  },
  {
    position: "OL", candidate: "False-start rate",
    reason: "Below YoY noise floor",
    pattern: "noise",
    detail: "Real OL responsibility but team-season YoY is +0.129 — likely reflects roster turnover at OL positions year-to-year, not unit skill that persists.",
    yoy: 0.129, validity: null,
  },
  {
    position: "OL", candidate: "Rush yards per carry",
    reason: "Mixes OL with RB after-contact value",
    pattern: "subsumed",
    detail: "Yards before contact (chosen) isolates OL skill from RB; total rush yards conflates them. Same insight as FGOE — strip non-OL context.",
    yoy: 0.364, validity: null,
  },
  {
    position: "EDGE", candidate: "Hit per pressure",
    reason: "Counter-intuitive negative validity",
    pattern: "noise",
    detail: "Players who turn pressures into hits (rather than sacks) are just-missing the sack. Voters reward elite finishers, not consolation-prize hits.",
    yoy: 0.350, validity: -0.038,
  },
  {
    position: "iDL", candidate: "Sack per pressure",
    reason: "Pure noise at iDL sample sizes",
    pattern: "noise",
    detail: "YoY r = +0.008. Cross-position contrast: same metric at EDGE has +0.122 YoY. Interior players have fewer pressures per season → ratio is dominated by variance.",
    yoy: 0.008, validity: 0.069,
  },
  {
    position: "TE", candidate: "Separation (NGS)",
    reason: "NEGATIVE Pro Bowl validity at TE",
    pattern: "noise",
    detail: "Most counter-intuitive finding. Open-route TE archetype isn't what voters reward; voters credit tight-window catchers (Kelce / Bowers). Separation has positive validity at WR but negative at TE.",
    yoy: 0.510, validity: -0.143,
  },
  {
    position: "WR", candidate: "Avg cushion (NGS)",
    reason: "Defensive scheme indicator",
    pattern: "noise",
    detail: "How much space the defense gives a receiver pre-snap. Tells you about coverage, not the WR.",
    yoy: 0.314, validity: -0.018,
  },
  {
    position: "WR", candidate: "Contested catch %",
    reason: "Small samples kill the signal",
    pattern: "small-sample",
    detail: "10-25 contested targets per WR per year. YoY barely above zero (+0.084). \"Contested catch artist\" is more reputation than measurable skill.",
    yoy: 0.084, validity: 0.034,
  },
  {
    position: "QB", candidate: "Pressure faced rate",
    reason: "Captures OL quality, not QB skill",
    pattern: "context-only",
    detail: "How often a QB gets pressured is mostly OL skill plus play-call. Tried to isolate QB component — couldn't without stripping the OL contamination.",
    yoy: 0.397, validity: 0.012,
  },
  {
    position: "RB", candidate: "Catch percentage (RB)",
    reason: "Removed in v1.1 — noise + redundant",
    pattern: "noise",
    detail: "Most RB targets are checkdowns where catch% is ~95%. Doesn't separate good from bad RBs.",
    yoy: 0.184, validity: -0.012,
  },
  {
    position: "LB", candidate: "Forced fumbles per snap",
    reason: "Cross-sectional std 0.00 — extremely rare",
    pattern: "small-sample",
    detail: "Typical LB has 0-2 forced fumbles per season. The metric basically can't differentiate players.",
    yoy: 0.197, validity: 0.055,
  },
];

// ---------------------------------------------------------------------------
// Cross-position lessons (the closer)
// ---------------------------------------------------------------------------

export const LESSONS = [
  {
    title: "Isolation beats contamination",
    one_liner: "When possible, pick the metric that strips out non-player context.",
    body:
      "FG% over expected (kickers) strips kick difficulty. Net average (punters) strips return-team value. Yards before contact (OL) strips RB after-contact ability. The pattern: when a raw stat mixes player skill with non-player factors, the over-expected or isolated version usually has better year-to-year reliability.",
    examples: ["K: FGOE/att over raw FG%", "P: net avg over gross avg", "OL: YBC/carry over rush yards/carry"],
  },
  {
    title: "Over-expected isn't always best",
    one_liner: "The K lesson didn't fully generalize to P.",
    body:
      "The over-expected approach works when the baseline is well-isolated. FG distance baselines are stable (every 40-yard FG faces the same challenge). Punt EPA depends on the returner, the coverage team, the wind, the field position — non-punter variance dilutes the signal. For punters, the simpler raw rate (net average) won the audit on both YoY and validity.",
    examples: ["K v1.1: FGOE dominates", "P v1.1: net avg beats EPA per punt"],
  },
  {
    title: "Document what you DIDN'T ship",
    one_liner: "The audit log is the methodology's credibility.",
    body:
      "For each position we tested 10-22 candidates and shipped 2-7. The 100+ rejected candidates are documented with their YoY, validity, and the reason for rejection. A formula is only defensible if the alternatives that didn't make it are visible — \"we considered X and here's why we excluded it\" beats \"we picked these because it felt right.\"",
    examples: ["190+ candidates evaluated, 52 in production formulas"],
  },
  {
    title: "Methodology has to self-correct",
    one_liner: "When the audit catches a flaw, fix the formula.",
    body:
      "K v1 used raw FG% — which actively punished kickers for attempting long FGs. After feedback, K v1.1 replaced the entire formula with FG over expected within hours. P v1 included blocked_rate at small weight on \"punter conceptually owns the play\" grounds; P v1.1 removed it when the audit signal was too weak. iDL v1.2 swapped pressure and TFL after the audit revealed pressure was both more reliable and more validated. The framework only earns trust by showing it changes when the data says it should.",
    examples: ["K v1 → v1.1 (FGOE)", "P v1 → v1.1 (drop blocked_rate)", "iDL v1.2 (rebalance)"],
  },
];

// ---------------------------------------------------------------------------
// Helper: verdict color + label for the audit grid
// ---------------------------------------------------------------------------

export const VERDICT_META: Record<Verdict, { label: string; tone: "good" | "neutral" | "bad" | "warn" }> = {
  shipped:        { label: "Shipped",        tone: "good"    },
  subsumed:       { label: "Subsumed",       tone: "warn"    },
  redundant:      { label: "Redundant",      tone: "warn"    },
  noise:          { label: "Noise",          tone: "bad"     },
  "small-sample": { label: "Small sample",   tone: "bad"     },
  "context-only": { label: "Context only",   tone: "neutral" },
  "anti-skill":   { label: "Anti-skill",     tone: "bad"     },
};
