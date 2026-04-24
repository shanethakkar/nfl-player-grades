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

const COMPONENT_FORMATS: Record<string, ComponentFormat> = {
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
    // success rate stored as a fraction [0..1]; display as a percentage
    formatValue: (v) => (v * 100).toFixed(1),
  },
};

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
