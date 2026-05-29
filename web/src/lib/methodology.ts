/**
 * Server-only queries powering the consumer-facing /methodology page.
 *
 * Kept apart from `queries.ts` because the methodology page consumes
 * grade data with a very different shape than the leaderboard / player
 * pages — these helpers cluster grades into the human-readable tiers
 * shown on the page (90+, 80-89, ..., <50) and surface "current top
 * three" picks per position.
 */

import "server-only";

import { unstable_cache } from "next/cache";

import { sql } from "./db";

export type TierExample = {
  player_id: number;
  slug: string;
  full_name: string;
  season: number;
  position: string;
  composite_grade: number;
};

export type TierBucket = {
  /** Stable tier id; used for React keys. */
  id: GradeTierId;
  /** Numeric range as text (e.g. "90+", "60-69", "<50"). */
  range: string;
  /** Short label that goes next to the range (e.g. "MVP-caliber"). */
  label: string;
  examples: TierExample[];
};

export type GradeTierId =
  | "tier-90"
  | "tier-80"
  | "tier-70"
  | "tier-60"
  | "tier-50"
  | "tier-sub-50";

/**
 * Tier definitions in display order. Kept in this module (not the
 * grades formatter) because the labels are page-copy, not formatting.
 */
export const GRADE_TIERS: ReadonlyArray<{
  id: GradeTierId;
  range: string;
  label: string;
  /** Inclusive lower bound. */
  min: number;
  /** Exclusive upper bound (or +Infinity for the top tier). */
  max: number;
}> = [
  { id: "tier-90", range: "90+", label: "MVP-caliber", min: 90, max: Infinity },
  { id: "tier-80", range: "80–89", label: "All-Pro level", min: 80, max: 90 },
  {
    id: "tier-70",
    range: "70–79",
    label: "Pro Bowler / above-average starter",
    min: 70,
    max: 80,
  },
  { id: "tier-60", range: "60–69", label: "Quality starter", min: 60, max: 70 },
  { id: "tier-50", range: "50–59", label: "Average / rotational", min: 50, max: 60 },
  {
    id: "tier-sub-50",
    range: "below 50",
    label: "Below average / backup",
    min: -Infinity,
    max: 50,
  },
];

/**
 * Top 3 representative player-seasons in each grade tier, drawn from
 * every qualified row across every graded season.
 *
 * Dedupe rule: one row per (player, tier). If Mahomes has six 90+
 * seasons, only his single highest 90+ season shows up — so the band
 * surfaces the broadest set of distinct players rather than a single
 * star three times.
 *
 * Ordering inside a tier is by `composite_grade DESC`, which means
 * the lowest tier surfaces players closest to 50 (high end of the
 * "below average" band). That reads better than dredging up the
 * worst-graded qualified seasons in history.
 */
async function _getGradeTierExamples(): Promise<TierBucket[]> {
  const rows = await sql<
    {
      player_id: number;
      slug: string;
      full_name: string;
      season: number;
      position: string;
      composite_grade: number;
      tier_id: GradeTierId;
    }[]
  >`
    WITH tiered AS (
      SELECT
        sg.player_id,
        p.slug,
        p.full_name,
        sg.season,
        sg.position,
        sg.composite_grade,
        CASE
          WHEN sg.composite_grade >= 90 THEN 'tier-90'
          WHEN sg.composite_grade >= 80 THEN 'tier-80'
          WHEN sg.composite_grade >= 70 THEN 'tier-70'
          WHEN sg.composite_grade >= 60 THEN 'tier-60'
          WHEN sg.composite_grade >= 50 THEN 'tier-50'
          ELSE 'tier-sub-50'
        END AS tier_id
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      WHERE sg.qualified = TRUE
    ),
    deduped AS (
      SELECT DISTINCT ON (tier_id, player_id)
        player_id, slug, full_name, season, position, composite_grade, tier_id
      FROM tiered
      ORDER BY tier_id, player_id, composite_grade DESC
    ),
    ranked AS (
      SELECT
        player_id, slug, full_name, season, position, composite_grade, tier_id,
        ROW_NUMBER() OVER (
          PARTITION BY tier_id
          ORDER BY composite_grade DESC, season DESC, player_id
        ) AS rk
      FROM deduped
    )
    SELECT player_id, slug, full_name, season, position, composite_grade, tier_id
    FROM ranked
    WHERE rk <= 3
  `;

  const byTier = new Map<GradeTierId, TierExample[]>();
  for (const r of rows) {
    const bucket = byTier.get(r.tier_id) ?? [];
    bucket.push({
      player_id: Number(r.player_id),
      slug: r.slug,
      full_name: r.full_name,
      season: Number(r.season),
      position: r.position,
      composite_grade: Number(r.composite_grade),
    });
    byTier.set(r.tier_id, bucket);
  }

  return GRADE_TIERS.map((t) => ({
    id: t.id,
    range: t.range,
    label: t.label,
    examples: byTier.get(t.id) ?? [],
  }));
}
export const getGradeTierExamples = unstable_cache(
  _getGradeTierExamples,
  ["grade-tier-examples"],
  { revalidate: 3600 },
);

export type CurrentTopEntry = {
  player_id: number;
  slug: string;
  full_name: string;
  composite_grade: number;
};

/**
 * Top N qualified players at `position` for the latest graded season.
 *
 * Used by the position cards on /methodology — every card renders
 * "see current top N" links so the page stays anchored to live data
 * instead of hardcoded names.
 */
async function _getCurrentTopAtPosition(
  position: string,
  limit = 3,
): Promise<{ season: number | null; entries: CurrentTopEntry[] }> {
  // OL is team-level (ADR-0025) and lives in team_ol_grades, not season_grades.
  if (position === "OL") {
    const seasonRows = await sql<{ season: number | null }[]>`
      SELECT MAX(season) AS season FROM team_ol_grades WHERE qualified = TRUE
    `;
    const season = seasonRows[0]?.season ?? null;
    if (season === null) return { season: null, entries: [] };

    const rows = await sql<
      { player_id: number; slug: string; full_name: string; composite_grade: number }[]
    >`
      SELECT
        g.team_id     AS player_id,   -- reuse field name for consistent shape
        t.abbr        AS slug,        -- OL "slug" is the team abbr; the
                                      -- methodology link path is broken
                                      -- for OL either way (no per-OL
                                      -- profile exists) — kept consistent
                                      -- with the field-reuse hack above.
        t.name        AS full_name,
        g.composite_grade
      FROM team_ol_grades g
      JOIN teams t ON t.team_id = g.team_id
      WHERE g.season = ${season} AND g.qualified = TRUE
      ORDER BY g.composite_grade DESC
      LIMIT ${limit}
    `;
    return {
      season: Number(season),
      entries: rows.map((r) => ({
        player_id: Number(r.player_id),
        slug: r.slug,
        full_name: r.full_name,
        composite_grade: Number(r.composite_grade),
      })),
    };
  }

  const seasonRows = await sql<{ season: number | null }[]>`
    SELECT MAX(season) AS season
    FROM season_grades
    WHERE position = ${position}
      AND qualified = TRUE
  `;
  const season = seasonRows[0]?.season ?? null;
  if (season === null) return { season: null, entries: [] };

  const rows = await sql<
    {
      player_id: number;
      slug: string;
      full_name: string;
      composite_grade: number;
    }[]
  >`
    SELECT
      sg.player_id,
      p.slug,
      p.full_name,
      sg.composite_grade
    FROM season_grades sg
    JOIN players p ON p.player_id = sg.player_id
    WHERE sg.season = ${season}
      AND sg.position = ${position}
      AND sg.qualified = TRUE
    ORDER BY sg.composite_grade DESC
    LIMIT ${limit}
  `;

  return {
    season: Number(season),
    entries: rows.map((r) => ({
      player_id: Number(r.player_id),
      slug: r.slug,
      full_name: r.full_name,
      composite_grade: Number(r.composite_grade),
    })),
  };
}
export const getCurrentTopAtPosition = unstable_cache(
  _getCurrentTopAtPosition,
  ["current-top-at-position"],
  { revalidate: 3600 },
);


/** One top-team row for the team-grades methodology blocks. */
export type CurrentTopTeam = {
  team_id: number;
  abbr: string;
  name: string;
  phase_grade: number;
};

/**
 * Top N teams at a phase (offense / defense / st) for the latest graded
 * season. Mirrors {@link getCurrentTopAtPosition} but reads team_grades
 * and selects the column matching the requested phase. Used by the
 * team-grades section on /methodology to anchor each phase card to a
 * live "best teams this year" block.
 */
async function _getCurrentTopTeamsByPhase(
  phase: "offense" | "defense" | "st",
  limit = 3,
): Promise<{ season: number | null; entries: CurrentTopTeam[] }> {
  const seasonRows = await sql<{ season: number | null }[]>`
    SELECT MAX(season) AS season FROM team_grades
  `;
  const season = seasonRows[0]?.season ?? null;
  if (season === null) return { season: null, entries: [] };

  // The phase column is dynamic — postgres template tags don't take
  // identifiers, so we branch and inline the right column name.
  const rows = await (async () => {
    if (phase === "offense") {
      return sql<{ team_id: number; abbr: string; name: string; phase_grade: number }[]>`
        SELECT tg.team_id, t.abbr, t.name, tg.offense_grade AS phase_grade
        FROM team_grades tg JOIN teams t ON t.team_id = tg.team_id
        WHERE tg.season = ${season}
        ORDER BY tg.offense_grade DESC
        LIMIT ${limit}
      `;
    }
    if (phase === "defense") {
      return sql<{ team_id: number; abbr: string; name: string; phase_grade: number }[]>`
        SELECT tg.team_id, t.abbr, t.name, tg.defense_grade AS phase_grade
        FROM team_grades tg JOIN teams t ON t.team_id = tg.team_id
        WHERE tg.season = ${season}
        ORDER BY tg.defense_grade DESC
        LIMIT ${limit}
      `;
    }
    return sql<{ team_id: number; abbr: string; name: string; phase_grade: number }[]>`
      SELECT tg.team_id, t.abbr, t.name, tg.st_grade AS phase_grade
      FROM team_grades tg JOIN teams t ON t.team_id = tg.team_id
      WHERE tg.season = ${season}
      ORDER BY tg.st_grade DESC
      LIMIT ${limit}
    `;
  })();

  return {
    season: Number(season),
    entries: rows.map((r) => ({
      team_id: Number(r.team_id),
      abbr: r.abbr,
      name: r.name,
      phase_grade: Number(r.phase_grade),
    })),
  };
}
export const getCurrentTopTeamsByPhase = unstable_cache(
  _getCurrentTopTeamsByPhase,
  ["current-top-teams-by-phase"],
  { revalidate: 3600 },
);
