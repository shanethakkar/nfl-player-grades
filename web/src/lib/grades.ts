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
  },
  qb_cpoe: {
    label: "CPOE",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
  },
  qb_success_rate: {
    label: "Success rate",
    suffix: "%",
    formatValue: pctFraction(1),
  },

  // --- RB v1 (ADR-0014) ---
  rb_ryoe_per_attempt: {
    label: "RYOE / att",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
  },
  rb_rush_epa_per_attempt: {
    label: "Rush EPA / att",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
  },
  rb_rush_success_rate: {
    label: "Rush success rate",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  rb_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
  },
  rb_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
  },
  rb_catch_pct: {
    label: "Catch rate",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  rb_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    // Fumble rates cluster around 0.5–2% so one extra decimal reads better.
    formatValue: pctFraction(2),
  },

  // --- WR v1 (ADR-0015) ---
  wr_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
  },
  wr_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
  },
  wr_separation: {
    label: "Separation",
    suffix: " yd",
    formatValue: (v) => v.toFixed(2),
  },
  wr_target_earn_rate: {
    label: "Target earn rate",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  wr_success_rate_per_target: {
    label: "Success / target",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  wr_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    formatValue: pctFraction(2),
  },

  // --- TE v1 (ADR-0016) ---
  te_rec_epa_per_target: {
    label: "Rec EPA / tgt",
    suffix: "",
    formatValue: (v) => signedFixed(v, 3),
  },
  te_yac_over_expected_per_rec: {
    label: "YAC / rec vs exp",
    suffix: "",
    formatValue: (v) => signedFixed(v, 2),
  },
  te_separation: {
    label: "Separation",
    suffix: " yd",
    formatValue: (v) => v.toFixed(2),
  },
  te_target_earn_rate: {
    label: "Target earn rate",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  te_success_rate_per_target: {
    label: "Success / target",
    suffix: "%",
    formatValue: pctFraction(1),
  },
  te_fumble_rate: {
    label: "Fumble rate",
    suffix: "%",
    formatValue: pctFraction(2),
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

/** Signed fixed-precision — "+0.123" / "-0.045". */
function signedFixed(v: number, digits: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";   // -0 renders without sign
  return `${sign}${Math.abs(v).toFixed(digits)}`;
}
