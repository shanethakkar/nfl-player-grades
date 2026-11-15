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

/**
 * Canonical player-leaderboard hrefs. Season and position live in the
 * path so `/` can be statically prerendered and ISR'd. `/` is the
 * latest season + QB; other combinations are `/season/[season]`,
 * `/position/[position]`, and `/season/[season]/position/[position]`.
 * Old `?season=` / `?position=` links are redirected in next.config.mjs.
 */
export function homeHref(
  season?: number | null,
  position?: string | null,
  latestSeason?: number | null,
): Route {
  const pos = position && position !== "QB" ? position : null;
  const seasonInPath =
    season != null && (latestSeason == null || season !== latestSeason)
      ? season
      : null;
  if (seasonInPath && pos) {
    return `/season/${seasonInPath}/position/${pos}` as Route;
  }
  if (seasonInPath) return `/season/${seasonInPath}` as Route;
  if (pos) return `/position/${pos}` as Route;
  return "/";
}
