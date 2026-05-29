/**
 * Shared number-formatting helpers. Centralized so the whole site
 * agrees on what "1,047" vs "1047" looks like (we want commas in
 * thousand-scale counts; raw integers read as developer output).
 */

const intFormatter = new Intl.NumberFormat("en-US");

/** Thousands-separated integer: `1047` → `"1,047"`. Safe for any number type. */
export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return intFormatter.format(Math.round(n));
}

/** Signed integer: `+12` / `-3` / `0`. Used for point differential. */
export function fmtSignedInt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  const rounded = Math.round(n);
  if (rounded === 0) return "0";
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${intFormatter.format(rounded)}`;
}
