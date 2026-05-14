/** Formatting helpers for grades. */

export function formatGrade(grade: number): string {
  return grade.toFixed(0);
}

export function formatCareer(grade: number, uncertainty: number): string {
  return `${grade.toFixed(0)} \u00B1 ${uncertainty.toFixed(0)}`;
}

export function gradeColor(grade: number): string {
  if (grade >= 90) return "text-emerald-400";
  if (grade >= 80) return "text-green-400";
  if (grade >= 70) return "text-lime-400";
  if (grade >= 55) return "text-yellow-400";
  if (grade >= 40) return "text-orange-400";
  return "text-red-400";
}

export function gradeHex(grade: number): string {
  if (grade >= 90) return "#34d399";
  if (grade >= 80) return "#4ade80";
  if (grade >= 70) return "#a3e635";
  if (grade >= 55) return "#facc15";
  if (grade >= 40) return "#fb923c";
  return "#f87171";
}

export const DATA_TIER_LABELS: Record<1 | 2 | 3, string> = {
  1: "Rich data",
  2: "Decent data",
  3: "Limited data",
};

// ---------------------------------------------------------------------------
// stat_components formatting
//
// Kept in this file so rendering code doesn't need to know that
// "qb_epa_per_dropback" wants 3 decimals and a leading sign.
// ---------------------------------------------------------------------------

type ComponentFormat = {
  label: string;
  /** Units/suffix appended after the formatted value (e.g. "%" or "" ). */
  suffix: string;
  /** Turn a raw numeric value into a display string (no suffix). */
  formatValue: (v: number) => string;
  /**
   * One-sentence plain-English explanation of what the metric measures.
   * Surfaced as the friendly-view tooltip on the player page so casual
   * readers can hover over "EPA / dropback" without knowing what EPA is.
   */
  description: string;
  /**
   * Singular noun for the underlying sample (e.g. "dropback", "target",
   * "rush attempt"). Used to render "based on 287 dropbacks" instead of
   * a bare integer in the friendly breakdown view.
   */
  sampleNoun: string;
};

// Percentage formatter — value is stored as a fraction [0..1] and rendered
// multiplied by 100. Fumble-rate values are tiny (~0.01) so we expose the
// decimal count instead of baking it in.
const pctFraction = (digits: number) => (v: number) =>
  (v * 100).toFixed(digits);

const COMPONENT_FORMATS: Record<string, ComponentFormat> = {
  // --- QB v1 (ADR-0013) ---
  qb_epa_per_dropback: {
    label: "EPA / dropback",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Expected Points Added per dropback. Captures total value created by sacks, scrambles, and pass plays.",
    sampleNoun: "dropback",
  },
  qb_cpoe: {
    label: "CPOE",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
    description:
      "Completion Percentage Over Expected. Accuracy adjusted for throw difficulty (depth, location, pressure).",
    sampleNoun: "throw",
  },
  qb_success_rate: {
    label: "Success rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of dropbacks that produce a positive-EPA outcome. A play that keeps the offense on schedule.",
    sampleNoun: "dropback",
  },

  // --- RB v1 (ADR-0014) ---
  rb_ryoe_per_attempt: {
    label: "RYOE / att",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
    description:
      "Rush Yards Over Expected per carry. NFL Next Gen Stats accounts for blocking, defenders in the box, and gaps.",
    sampleNoun: "rush",
  },
  rb_rush_epa_per_attempt: {
    label: "Rush EPA / att",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Expected Points Added per rush. Penalizes negative runs and rewards explosive runs.",
    sampleNoun: "rush",
  },
  rb_rush_success_rate: {
    label: "Rush success rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of rushes that stay on schedule (positive EPA). A consistency metric.",
    sampleNoun: "rush",
  },
  rb_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Receiving value per target out of the backfield or split wide.",
    sampleNoun: "target",
  },
  rb_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
    description:
      "Yards After Catch above what an average back would gain on the same throw.",
    sampleNoun: "reception",
  },
  rb_yards_after_contact_per_carry: {
    label: "YAC / carry",
    suffix: " yd",
    formatValue: (v) => v.toFixed(2),
    description:
      "Yards gained after first contact, per carry (PFR charting). Pure RB skill — breaking tackles, falling forward, second-effort yardage. Distinct from RYOE which includes pre-contact OL-created yards. Data available 2018+; pre-2018 RB grades use the v1.3 formula without this component.",
    sampleNoun: "carry",
  },
  rb_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description: "Fumbles per touch (rush + reception).",
    sampleNoun: "touch",
  },

  // --- WR v1 (ADR-0015) ---
  wr_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Expected Points Added per target. The all-in efficiency number for receivers.",
    sampleNoun: "target",
  },
  wr_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
    description:
      "Yards After Catch above what an average receiver would gain on the same throw (NGS).",
    sampleNoun: "reception",
  },
  wr_separation: {
    label: "Separation",
    suffix: " yd",
    formatValue: (v) => v.toFixed(2),
    description:
      "Average yards from the nearest defender at the moment the ball arrives (NGS).",
    sampleNoun: "target",
  },
  wr_target_earn_rate: {
    label: "Target earn rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Targets divided by team pass attempts while on the field. Measures how often the offense looked his way.",
    sampleNoun: "team pass attempt",
  },
  wr_success_rate_per_target: {
    label: "Success / target",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of targets that stay on schedule (positive EPA). A consistency metric.",
    sampleNoun: "target",
  },
  wr_drop_rate: {
    label: "Drop rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Drops as a share of catchable balls (per FTN charting). Lower is better. Data available 2022+; pre-2022 WR grades use the v1 formula without this component.",
    sampleNoun: "catchable ball",
  },

  // --- CB v1.1 (ADR-0018, revised) ---
  cb_passer_rating_allowed: {
    label: "Passer rtg allowed",
    suffix: "",
    formatValue: (v) => v.toFixed(1),
    description:
      "NFL passer rating allowed when targeted. Industry-standard coverage damage metric — combines completion %, yards, TDs, and INTs into one number. Lower is better.",
    sampleNoun: "target",
  },
  cb_yac_per_rec_allowed: {
    label: "YAC/rec allowed",
    suffix: "",
    formatValue: (v) => v.toFixed(2),
    description:
      "Yards after catch allowed per reception. Captures cushion allowed and tackling quality at the catch point — a different skill from preventing the catch.",
    sampleNoun: "target",
  },
  cb_target_rate: {
    label: "Target rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Targets per defensive snap. Lower is better — elite CBs get avoided. QBs scheme away from them regardless of outcome.",
    sampleNoun: "defensive snap",
  },
  cb_pbu_rate: {
    label: "PBU rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Pass breakups (passes defended) per target. Active play that breaks up the catch. INTs are captured separately inside passer rating allowed.",
    sampleNoun: "target",
  },

  // --- Safety v1.1 (ADR-0019 revised) ---
  s_passer_rating_allowed: {
    label: "Passer rtg allowed",
    suffix: "",
    formatValue: (v) => v.toFixed(1),
    description:
      "NFL passer rating allowed when targeted. Industry-standard coverage damage metric — combines completion %, yards, TDs, and INTs into one number. Lower is better.",
    sampleNoun: "target",
  },
  s_pbu_rate: {
    label: "PBU rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Pass breakups per target. Active play that breaks up the catch. INTs are captured separately inside passer rating allowed.",
    sampleNoun: "target",
  },
  s_target_rate: {
    label: "Target rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Targets per defensive snap. Lower is better — elite safeties get schemed around, independent of what happens when they are thrown at.",
    sampleNoun: "defensive snap",
  },
  s_tackles_per_snap: {
    label: "Tackles/snap",
    suffix: "",
    formatValue: (v) => v.toFixed(3),
    description:
      "Combined tackles per defensive snap. Safeties are expected to be reliable tacklers in both coverage and run support.",
    sampleNoun: "defensive snap",
  },
  s_missed_tackle_rate: {
    label: "Missed tkl%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Missed tackles as a share of tackle attempts. Lower is better — misses in space often turn into big gains.",
    sampleNoun: "tackle attempt",
  },
  s_backfield_disruption_per_snap: {
    label: "Disruption/100 snaps",
    suffix: "",
    formatValue: (v) => (v * 100).toFixed(2),
    description:
      "Tackles for loss plus sacks per defensive snap. Measures pass-rush versatility and the ability to stop plays behind the line.",
    sampleNoun: "defensive snap",
  },

  // --- EDGE v1 (ADR-0020) ---
  edge_pressure_rate: {
    label: "Pressure rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Total pressures (sacks + QB hits + hurries) per defensive snap. The primary measure of pass-rush impact per opportunity.",
    sampleNoun: "defensive snap",
  },
  edge_sack_rate: {
    label: "Sack rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Sacks per defensive snap. Premium outcome: extra credit for converting pressure into the most impactful pass-rush play.",
    sampleNoun: "defensive snap",
  },
  edge_tfl_rate: {
    label: "TFL rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Run-stop tackles for loss per defensive snap (sacks excluded). Measures edge-setting ability against the run.",
    sampleNoun: "defensive snap",
  },
  edge_tackles_per_snap: {
    label: "Tackles / snap",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Combined tackles per defensive snap. Captures activity level and chase-tackles — plays that don't show up as pressures, sacks, or TFLs but still measure real run-defense engagement.",
    sampleNoun: "defensive snap",
  },
  edge_missed_tackle_rate: {
    label: "Missed tackle rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Missed tackles as a share of tackle attempts. Lower is better — missed tackles in the backfield or open field cost the most.",
    sampleNoun: "tackle attempt",
  },

  // --- LB v1 (ADR-0022) ---
  lb_tfl_rate: {
    label: "TFL rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Run-stop tackles for loss per defensive snap (sacks excluded). The cleanest LB run-defense signal — actual play-making behind the line.",
    sampleNoun: "defensive snap",
  },
  lb_passer_rating_allowed: {
    label: "Passer rtg allowed",
    suffix: "",
    formatValue: (v) => v.toFixed(1),
    description:
      "NFL passer rating allowed when targeted. Industry-standard coverage damage metric — combines completion %, yards, TDs, and INTs into one number. Lower is better.",
    sampleNoun: "target",
  },
  lb_missed_tackle_rate: {
    label: "Missed tkl%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Missed tackles as a share of tackle attempts. LBs make the most tackles of any position; misses cost the most.",
    sampleNoun: "tackle attempt",
  },
  lb_pbu_rate: {
    label: "PBU rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Pass breakups per coverage target. Active play that broke up the catch. INTs are captured separately inside passer rating allowed.",
    sampleNoun: "target",
  },
  lb_tackle_rate: {
    label: "Tackles/snap",
    suffix: "",
    formatValue: (v) => v.toFixed(3),
    description:
      "Combined tackles per defensive snap. Volume signal — every-down LBs should be making plays. Some team-context dependency.",
    sampleNoun: "defensive snap",
  },
  lb_pressure_rate: {
    label: "Pressure rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Pressures per defensive snap. Small weight in LB grading: near-zero for traditional MLBs, meaningfully positive for blitz-heavy types.",
    sampleNoun: "defensive snap",
  },

  // --- iDL v1 (ADR-0021) ---
  idl_tfl_rate: {
    label: "TFL rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Run-stop tackles for loss per defensive snap (sacks excluded). The primary iDL differentiator — interior penetration that stops plays behind the line.",
    sampleNoun: "defensive snap",
  },
  idl_pressure_rate: {
    label: "Pressure rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Total pressures (sacks + QB hits + hurries) per defensive snap. Interior pass rush impact per opportunity.",
    sampleNoun: "defensive snap",
  },
  idl_sack_rate: {
    label: "Sack rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Sacks per defensive snap. Premium pass-rush outcome — interior sacks are rarer than edge sacks but equally impactful.",
    sampleNoun: "defensive snap",
  },
  idl_tackles_per_snap: {
    label: "Tackles / snap",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Combined tackles per defensive snap. Captures activity level and chase-tackles — plays that don't show up as pressures, sacks, or TFLs but still measure real run-defense engagement.",
    sampleNoun: "defensive snap",
  },
  idl_missed_tackle_rate: {
    label: "Missed tackle rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Missed tackles as a share of tackle attempts. Lower is better — iDL players make many tackles at the line of scrimmage where misses are especially costly.",
    sampleNoun: "tackle attempt",
  },

  // --- TE v1 (ADR-0016) ---
  te_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Expected Points Added per target. The all-in receiving-efficiency number.",
    sampleNoun: "target",
  },
  te_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
    description:
      "Yards After Catch above what an average TE would gain on the same throw (NGS).",
    sampleNoun: "reception",
  },
  te_separation: {
    label: "Separation",
    suffix: " yd",
    formatValue: (v) => v.toFixed(2),
    description:
      "Average yards from the nearest defender at the catch point (NGS).",
    sampleNoun: "target",
  },
  te_target_earn_rate: {
    label: "Target earn rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Targets divided by team pass attempts while on the field. Dropped from the composite for pure blocking TEs (ADR-0016).",
    sampleNoun: "team pass attempt",
  },
  te_success_rate_per_target: {
    label: "Success / target",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of targets that stay on schedule (positive EPA). A consistency metric.",
    sampleNoun: "target",
  },
  te_drop_rate: {
    label: "Drop rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Drops per catchable target. FTN charting (2022+). Light weight: YoY signal is modest (mean r ≈ +0.13) but cross-sectional discrimination and face-check are real.",
    sampleNoun: "catchable ball",
  },

  // --- K v1.1 (ADR-0023, revised — single component) ---
  k_fg_over_expected_per_att: {
    label: "FGOE / att",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
    description:
      "Field Goal Over Expected per attempt. Each kick is compared to the league baseline make rate for its distance (0-19 ~100%, 20-29 ~98%, 30-39 ~94%, 40-49 ~80%, 50-59 ~69%, 60+ ~40%, XP ~94%). A 60-yard make is worth +0.60 over expected; an XP miss is worth -0.94. Risk-asymmetric by construction — rewards making hard kicks heavily, penalizes missing easy kicks heavily, doesn't punish kickers for attempting long FGs. Replaces v1's raw make-rate formula (which active punished risk-taking).",
    sampleNoun: "FG/XP attempt",
  },

  // K context columns (displayed on the K leaderboard but NOT part of the
  // grading formula — readers see them for recognition).
  k_fg_pct: {
    label: "FG%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Overall field goal percentage (all distances). Context only — not part of the K v1.1 formula. The grade uses FGOE / att instead because raw FG% doesn't account for kick difficulty.",
    sampleNoun: "FG attempt",
  },
  k_fg_pct_40_plus: {
    label: "FG% 40+",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Field goal percentage on attempts of 40+ yards. Context only — not part of the K v1.1 formula. Was the primary v1 component but replaced by FGOE / att, which handles distance gradation continuously.",
    sampleNoun: "40+ yd FG attempt",
  },
  k_pat_pct: {
    label: "XP%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Extra-point conversion rate. Context only — XPs are folded into the FGOE / att formula as a 33-yard FG bucket (~94% baseline).",
    sampleNoun: "XP attempt",
  },
  k_fg_long: {
    label: "FG long",
    suffix: " yd",
    formatValue: (v) => v.toFixed(0),
    description:
      "Longest field goal made on the season — power capability. Context only — the audit found this signal is subsumed by FGOE / att.",
    sampleNoun: "FG attempt",
  },

  // --- P v1 (ADR-0024) ---
  p_net_avg: {
    label: "Net avg",
    suffix: " yd",
    formatValue: (v) => v.toFixed(1),
    description:
      "Net yards per punt (gross yards minus return yards). The primary punter metric — captures both leg strength and return prevention. Best YoY (r ≈ +0.36) and second-best Pro Bowl validity in the audit. Sole 'distance' signal in the formula.",
    sampleNoun: "punt",
  },
  p_inside_20_rate: {
    label: "Inside 20%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of punts pinned inside the opponent's 20-yard line. Highest Pro Bowl validity in the audit (r ≈ +0.19). Captures placement skill — orthogonal to net yardage (a 40-yard punt downed at the 5 looks identical to a 40-yard punt downed at the 35 by net average alone).",
    sampleNoun: "punt",
  },
  p_blocked_rate: {
    label: "Block%",
    suffix: "%",
    formatValue: pctFraction(2),
    description:
      "Punts blocked per attempt. Lower is better. Small weight (-0.05) in the formula because blocks are mostly snap/protection failures rather than punter skill (audit YoY r ≈ -0.05, near-zero), but conceptually a punter owns the play and a blocked punt is catastrophic — small penalty bounds the cost.",
    sampleNoun: "punt",
  },
  // P context columns (displayed but not scored)
  p_gross_avg: {
    label: "Gross avg",
    suffix: " yd",
    formatValue: (v) => v.toFixed(1),
    description:
      "Gross yards per punt (raw kick distance, ignores returns). CONTEXT ONLY — net average is the formula component because it accounts for return yardage allowed.",
    sampleNoun: "punt",
  },
  p_long_punt: {
    label: "Long",
    suffix: " yd",
    formatValue: (v) => v.toFixed(0),
    description:
      "Longest punt of the season. CONTEXT ONLY — power proxy with weak audit signal (YoY r ≈ +0.08, validity r ≈ +0.08).",
    sampleNoun: "punt",
  },
  p_touchback_rate: {
    label: "TB%",
    suffix: "%",
    formatValue: pctFraction(1),
    description:
      "Share of punts that became touchbacks (opponent gets ball at the 20). Lower is better. CONTEXT ONLY — touchback avoidance is implicitly captured by net average (touchbacks cap net at LOS-to-opponent's-20).",
    sampleNoun: "punt",
  },
};

// TE role labels stored on season_grades.role (see ADR-0016). Kept here so
// the web app has a single translation from the pipeline's string enum to
// user-facing copy.
export const TE_ROLE_LABELS: Record<string, string> = {
  receiving_te: "Receiving TE",
  balanced_te: "Balanced TE",
  blocking_te: "Blocking TE",
};

export function teRoleLabel(role: string | null | undefined): string | null {
  if (!role) return null;
  return TE_ROLE_LABELS[role] ?? role;
}

export const CB_ROLE_LABELS: Record<string, string> = {
  outside_cb: "Outside CB",
  hybrid_cb:  "Hybrid CB",
  slot_cb:    "Slot CB",
};

export function cbRoleLabel(role: string | null | undefined): string | null {
  if (!role) return null;
  return CB_ROLE_LABELS[role] ?? role;
}

export function componentLabel(componentName: string): string {
  return COMPONENT_FORMATS[componentName]?.label ?? componentName;
}

export function componentDescription(componentName: string): string | null {
  return COMPONENT_FORMATS[componentName]?.description ?? null;
}

/**
 * Human-readable sample size — "287 dropbacks" instead of just "287".
 * Falls back to the bare number when we have no noun or the value is
 * missing.
 */
export function formatSample(
  componentName: string,
  size: number | null,
): string {
  if (size === null || !Number.isFinite(size)) return "—";
  const fmt = COMPONENT_FORMATS[componentName];
  if (!fmt) return String(size);
  const noun = size === 1 ? fmt.sampleNoun : `${fmt.sampleNoun}s`;
  return `${size} ${noun}`;
}

export function formatComponentValue(
  componentName: string,
  value: number | null,
): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const fmt = COMPONENT_FORMATS[componentName];
  if (!fmt) return value.toFixed(3);
  return `${fmt.formatValue(value)}${fmt.suffix}`;
}

/** Z-score formatter (all components use the same format). */
export function formatZ(z: number | null): string {
  if (z === null || !Number.isFinite(z)) return "—";
  return signedFixed(z, 2);
}

/**
 * Plain-English label for where a z-score falls vs. the position pool.
 * Used in the friendly breakdown view in lieu of the raw z-score.
 *
 * Bands match how a normal-ish distribution reads to a fan:
 *   |z| < 0.5  → average
 *   |z| < 1.5  → above / below average
 *   |z| >= 1.5 → well above / well below average
 *
 * Returns both a label and a tone ("good" / "bad" / "neutral") so the
 * caller can colour the cell consistently with the grade colour scale.
 */
export type ZBand = {
  label: string;
  tone: "good" | "bad" | "neutral";
};

export function zBand(z: number | null): ZBand {
  if (z === null || !Number.isFinite(z)) {
    return { label: "—", tone: "neutral" };
  }
  if (z >= 1.5) return { label: "well above average", tone: "good" };
  if (z >= 0.5) return { label: "above average", tone: "good" };
  if (z <= -1.5) return { label: "well below average", tone: "bad" };
  if (z <= -0.5) return { label: "below average", tone: "bad" };
  return { label: "average", tone: "neutral" };
}

/** Signed fixed-precision — "+0.123" / "-0.045". */
function signedFixed(v: number, digits: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";   // -0 renders without sign
  return `${sign}${Math.abs(v).toFixed(digits)}`;
}

// Normal CDF (Abramowitz & Stegun rational approximation, max error ~7.5e-8).
function normalCDF(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp((-z * z) / 2);
  const p =
    d * t * (0.3193815 + t * (-0.3565638 + t * (1.7814779 + t * (-1.8212560 + t * 1.3302744))));
  return z > 0 ? 1 - p : p;
}

function ordinalSuffix(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return "th";
  switch (n % 10) {
    case 1:  return "st";
    case 2:  return "nd";
    case 3:  return "rd";
    default: return "th";
  }
}

/** Raw numeric percentile from a z-score, clamped to [1, 99]. */
export function zToPercentile(z: number | null): number | null {
  if (z === null || !Number.isFinite(z)) return null;
  const raw = Math.round(normalCDF(z) * 100);
  return Math.max(1, Math.min(99, raw));
}

/** Converts a component z-score to a percentile string, e.g. "94th". */
export function formatPercentile(z: number | null): string {
  if (z === null || !Number.isFinite(z)) return "—";
  const raw = Math.round(normalCDF(z) * 100);
  const p = Math.max(1, Math.min(99, raw));
  return `${p}${ordinalSuffix(p)}`;
}

// ---------------------------------------------------------------------------
// Component weights — mirrors pipeline/grading/weights.py.
// Both dicts below are kept in sync by `pipeline/scripts/sync_weights_to_web.py`.
// Edit weights.py, then run that script. Do not hand-edit between
// AUTOGEN-BEGIN / AUTOGEN-END markers.
// ---------------------------------------------------------------------------

// AUTOGEN-BEGIN weights
const COMPONENT_WEIGHTS: Record<string, number> = {
  qb_epa_per_dropback:                0.50,
  qb_cpoe:                            0.25,
  qb_success_rate:                    0.10,
  rb_ryoe_per_attempt:                0.28,
  rb_rush_epa_per_attempt:            0.18,
  rb_rush_success_rate:               0.05,
  rb_rec_epa_per_target:              0.05,
  rb_yac_over_expected_per_rec:       0.28,
  rb_yards_after_contact_per_carry:   0.10,
  rb_fumble_rate:                    -0.05,
  wr_rec_epa_per_target:              0.35,
  wr_yac_over_expected_per_rec:       0.27,
  wr_separation:                      0.10,
  wr_target_earn_rate:                0.15,
  wr_success_rate_per_target:         0.05,
  wr_drop_rate:                      -0.05,
  te_rec_epa_per_target:              0.35,
  te_yac_over_expected_per_rec:       0.27,
  te_separation:                      0.07,
  te_target_earn_rate:                0.15,
  te_success_rate_per_target:         0.05,
  te_drop_rate:                      -0.05,
  cb_passer_rating_allowed:          -0.35,
  cb_yac_per_rec_allowed:            -0.15,
  cb_target_rate:                    -0.05,
  cb_pbu_rate:                        0.12,
  s_passer_rating_allowed:           -0.30,
  s_pbu_rate:                         0.12,
  s_target_rate:                     -0.05,
  s_tackles_per_snap:                 0.07,
  s_missed_tackle_rate:              -0.09,
  s_backfield_disruption_per_snap:    0.09,
  edge_pressure_rate:                 0.35,
  edge_sack_rate:                     0.30,
  edge_tfl_rate:                      0.15,
  edge_tackles_per_snap:              0.05,
  edge_missed_tackle_rate:           -0.10,
  idl_pressure_rate:                  0.35,
  idl_tfl_rate:                       0.25,
  idl_sack_rate:                      0.20,
  idl_tackles_per_snap:               0.05,
  idl_missed_tackle_rate:            -0.05,
  lb_tfl_rate:                        0.20,
  lb_passer_rating_allowed:          -0.15,
  lb_missed_tackle_rate:             -0.15,
  lb_pbu_rate:                        0.05,
  lb_tackle_rate:                     0.13,
  lb_pressure_rate:                   0.10,
  k_fg_over_expected_per_att:         1.00,
  p_net_avg:                          0.55,
  p_inside_20_rate:                   0.30,
  p_blocked_rate:                    -0.05,
};

const TE_BLOCKING_WEIGHTS: Record<string, number> = {
  te_rec_epa_per_target:         0.435,
  te_yac_over_expected_per_rec:  0.335,
  te_separation:                  0.07,
  te_success_rate_per_target:     0.05,
  te_drop_rate:                  -0.05,
};
// AUTOGEN-END weights

/** Weight of a component in the composite, or null if not in the formula. */
export function componentWeight(name: string, role?: string | null): number | null {
  if (role === "blocking_te") return TE_BLOCKING_WEIGHTS[name] ?? null;
  return COMPONENT_WEIGHTS[name] ?? null;
}

// ---------------------------------------------------------------------------
// Percentage / share helpers.
//
// The composite combiner normalizes by sum(|weights|). What a reader cares
// about is "this component is X% of the grade" — i.e., the weight divided
// by the sum of magnitudes for THIS position's formula. Helpers below
// surface that share-of-formula percentage so the methodology page and
// future article writeups can claim "EPA is 59% of the QB grade" without
// the reader needing to know the denominator.
// ---------------------------------------------------------------------------

/** Lowercase position prefix used in component names (e.g. "qb", "wr", "idl"). */
function positionPrefix(positionKey: string): string {
  return positionKey.toLowerCase();
}

/** Sum of |weights| for the position's main composite. */
function positionWeightTotal(positionKey: string): number {
  const prefix = positionPrefix(positionKey);
  let total = 0;
  for (const [name, w] of Object.entries(COMPONENT_WEIGHTS)) {
    if (name.startsWith(`${prefix}_`)) total += Math.abs(w);
  }
  return total;
}

const TE_BLOCKING_TOTAL = Object.values(TE_BLOCKING_WEIGHTS).reduce(
  (a, w) => a + Math.abs(w),
  0,
);

/**
 * Component's share of its position's composite, as a signed percentage
 * string. E.g. "59%" for QB EPA in v1.1 (0.50 / 0.85); "−5%" for WR drop
 * rate (0.05 / 0.95). Returns "—" if the component or position isn't in
 * the formula.
 */
export function componentSharePercent(
  name: string,
  role?: string | null,
): string {
  let raw: number | undefined;
  let total: number;
  if (role === "blocking_te") {
    raw = TE_BLOCKING_WEIGHTS[name];
    total = TE_BLOCKING_TOTAL;
  } else {
    raw = COMPONENT_WEIGHTS[name];
    const positionKey = name.split("_")[0];
    total = positionWeightTotal(positionKey);
  }
  if (raw === undefined || total === 0) return "—";
  const pct = Math.round((Math.abs(raw) / total) * 100);
  return raw < 0 ? `−${pct}%` : `${pct}%`;
}

/**
 * All components in the formula for a position, in their canonical order.
 * Reads from the auto-synced COMPONENT_WEIGHTS / TE_BLOCKING_WEIGHTS dicts
 * so the methodology page never drifts from weights.py.
 */
export function positionComponents(
  positionKey: string,
  role?: string | null,
): Array<{ name: string; weight: number }> {
  if (role === "blocking_te" && positionKey.toUpperCase() === "TE") {
    return Object.entries(TE_BLOCKING_WEIGHTS).map(([name, weight]) => ({
      name,
      weight,
    }));
  }
  const prefix = positionPrefix(positionKey);
  return Object.entries(COMPONENT_WEIGHTS)
    .filter(([name]) => name.startsWith(`${prefix}_`))
    .map(([name, weight]) => ({ name, weight }));
}

/**
 * Formats a raw weight as a percentage of 1.0, e.g. "50%" or "−50%".
 *
 * NOTE: this is the *raw weight* expressed as a percent (i.e., the weight
 * value times 100). Use ``componentSharePercent`` instead when you want
 * "share of the formula" — that's what readers expect when they see the
 * methodology page.
 */
export function formatWeight(w: number | null): string {
  if (w === null) return "—";
  const pct = Math.round(Math.abs(w) * 100);
  return w < 0 ? `−${pct}%` : `${pct}%`;
}
