import type { Route } from "next";

/**
 * Canonical team-profile and team-leaderboard hrefs.
 *
 * Season lives in the path so these pages can be statically prerendered
 * and ISR'd. `/teams/[abbr]` and `/teams` are the latest season; an
 * explicit year is `/teams/[abbr]/[season]` and `/teams/season/[season]`.
 * Old `?season=` links are redirected in next.config.mjs.
 */
export function teamHref(abbr: string, season?: number | null): Route {
  if (season == null) return `/teams/${abbr}` as Route;
  return `/teams/${abbr}/${season}` as Route;
}

export function teamsIndexHref(season?: number | null): Route {
  if (season == null) return "/teams";
  return `/teams/season/${season}` as Route;
}
