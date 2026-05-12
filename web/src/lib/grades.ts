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
  rb_catch_pct: {
    label: "Catch rate",
    suffix: "%",
    formatValue: pctFraction(1),
    description: "Receptions divided by targets.",
    sampleNoun: "target",
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
  wr_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description: "Fumbles per reception.",
    sampleNoun: "reception",
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
  te_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    formatValue: pctFraction(2),
    description: "Fumbles per reception.",
    sampleNoun: "reception",
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

/** Converts a component z-score to a percentile string, e.g. "94th". */
export function formatPercentile(z: number | null): string {
  if (z === null || !Number.isFinite(z)) return "—";
  const raw = Math.round(normalCDF(z) * 100);
  const p = Math.max(1, Math.min(99, raw));
  return `${p}${ordinalSuffix(p)}`;
}

// ---------------------------------------------------------------------------
// Component weights — mirrors pipeline/grading/weights.py.
// These are stable design constants (ADR-0013 through ADR-0016), not
// computed values, so hardcoding here avoids a backend round-trip.
// ---------------------------------------------------------------------------

const COMPONENT_WEIGHTS: Record<string, number> = {
  // QB v1 (ADR-0013)
  qb_epa_per_dropback:      0.50,
  qb_cpoe:                  0.25,
  qb_success_rate:          0.25,
  // RB v1 (ADR-0014)
  rb_ryoe_per_attempt:      0.28,
  rb_rush_epa_per_attempt:  0.18,
  rb_rush_success_rate:     0.14,
  rb_rec_epa_per_target:    0.18,
  rb_yac_over_expected_per_rec: 0.12,
  rb_catch_pct:             0.05,
  rb_fumble_rate:          -0.05,
  // WR v1 (ADR-0015)
  wr_rec_epa_per_target:    0.35,
  wr_yac_over_expected_per_rec: 0.27,
  wr_separation:            0.10,
  wr_target_earn_rate:      0.10,
  wr_success_rate_per_target: 0.08,
  wr_fumble_rate:          -0.05,
  // TE v1 receiving/balanced path (ADR-0016)
  te_rec_epa_per_target:    0.35,
  te_yac_over_expected_per_rec: 0.27,
  te_separation:            0.07,
  te_target_earn_rate:      0.10,
  te_success_rate_per_target: 0.08,
  te_fumble_rate:          -0.05,
};

// Blocking-TE path: earn rate excluded from composite; its weight is
// redistributed to EPA and YAC in proportion (ADR-0016).
const TE_BLOCKING_WEIGHTS: Record<string, number> = {
  te_rec_epa_per_target:        0.406,
  te_yac_over_expected_per_rec: 0.314,
  te_separation:                0.07,
  te_success_rate_per_target:   0.08,
  te_fumble_rate:              -0.05,
};

/** Weight of a component in the composite, or null if not in the formula. */
export function componentWeight(name: string, role?: string | null): number | null {
  if (role === "blocking_te") return TE_BLOCKING_WEIGHTS[name] ?? null;
  return COMPONENT_WEIGHTS[name] ?? null;
}

/** Formats a weight as a percentage, e.g. "50%" or "−50%" (minus sign for negative). */
export function formatWeight(w: number | null): string {
  if (w === null) return "—";
  const pct = Math.round(Math.abs(w) * 100);
  return w < 0 ? `−${pct}%` : `${pct}%`;
}
