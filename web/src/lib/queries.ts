/**
 * Server-side data access for grade pages.
 *
 * Kept separate from `grades.ts` (which is pure formatting) so the split
 * between "reads the DB" and "formats a number" stays obvious.
 *
 * All rows come from tables written by the Python pipeline; numeric
 * columns (`DOUBLE PRECISION` / `INTEGER`) come back as JS `number`
 * from the `postgres` driver.
 */

import "server-only";

import { sql } from "./db";
import type {
  LeaderboardEntry,
  PlayerDetail,
  PlayerMeta,
  SeasonGradeDetail,
  StatComponentDetail,
} from "@/types";

/**
 * Seasons that have any graded rows (any position). Ordered newest first
 * so the UI can default to the latest.
 */
export async function getGradedSeasons(): Promise<number[]> {
  const rows = await sql<{ season: number }[]>`
    SELECT DISTINCT season
    FROM season_grades
    ORDER BY season DESC
  `;
  return rows.map((r) => Number(r.season));
}

/**
 * Positions with graded rows for at least one season. Used by the UI to
 * decide what position filters to show.
 */
export async function getGradedPositions(): Promise<string[]> {
  const rows = await sql<{ position: string }[]>`
    SELECT DISTINCT position
    FROM season_grades
    ORDER BY position
  `;
  return rows.map((r) => r.position);
}

/**
 * Full leaderboard for one (season, position).
 *
 * Returns all rows — qualified first (sorted by grade desc), then
 * unqualified below (sorted by grade desc). The UI decides what to
 * show / hide.
 *
 * Each position's query LEFT JOINs a handful of "headline" component
 * rows (~4) so the leaderboard table can show per-position stats
 * (e.g. EPA/tgt for WRs) without a per-row follow-up query. The
 * branching is deliberate: `sql` template tags don't compose cleanly
 * across conditional joins, and the four cases are short enough that
 * mild duplication reads better than a dynamic query builder.
 */
export async function getLeaderboard(
  season: number,
  position: string,
): Promise<LeaderboardEntry[]> {
  // The base SELECT + team_lookup LATERAL is identical across positions.
  // The `postgres` library lets us interpolate a `sql` fragment, but
  // fragments can't be conditionally composed either — so we just pick
  // one of four template literals below. QB is unchanged for drift-proof
  // backwards compatibility.
  if (position === "QB") {
    const rows = await sql<LeaderboardEntry[]>`
      SELECT
        sg.player_id,
        p.full_name,
        sg.position,
        sg.season,
        sg.composite_grade,
        sg.composite_z,
        sg.percentile,
        sg.qualified,
        sg.confidence,
        sg.data_tier,
        sg.role,
        team_lookup.team_abbr,
        sc_epa.sample_size      AS n_dropbacks,
        sc_epa.raw_value        AS epa_per_dropback,
        sc_cpoe.raw_value       AS cpoe,
        sc_succ.raw_value       AS success_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      ${teamLookupLateralForSgP}
      LEFT JOIN stat_components sc_epa
        ON sc_epa.player_id = sg.player_id
       AND sc_epa.season = sg.season
       AND sc_epa.component_name = 'qb_epa_per_dropback'
      LEFT JOIN stat_components sc_cpoe
        ON sc_cpoe.player_id = sg.player_id
       AND sc_cpoe.season = sg.season
       AND sc_cpoe.component_name = 'qb_cpoe'
      LEFT JOIN stat_components sc_succ
        ON sc_succ.player_id = sg.player_id
       AND sc_succ.season = sg.season
       AND sc_succ.component_name = 'qb_success_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'QB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "RB") {
    // RB headline columns: Touches / RYOE-per-att / Rush EPA-per-att /
    // Rush Success%. Sample size for "touches" is taken from the
    // fumble_rate component (whose denominator is carries + receptions
    // per RB_V1_SAMPLE_SIZE_COLS); RYOE/EPA/success all share n_carries
    // but we don't need n_carries separately in the UI.
    const rows = await sql<LeaderboardEntry[]>`
      SELECT
        sg.player_id,
        p.full_name,
        sg.position,
        sg.season,
        sg.composite_grade,
        sg.composite_z,
        sg.percentile,
        sg.qualified,
        sg.confidence,
        sg.data_tier,
        sg.role,
        team_lookup.team_abbr,
        sc_fumble.sample_size   AS n_touches,
        sc_ryoe.raw_value       AS rb_ryoe_per_attempt,
        sc_epa.raw_value        AS rb_rush_epa_per_attempt,
        sc_succ.raw_value       AS rb_rush_success_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      ${teamLookupLateralForSgP}
      LEFT JOIN stat_components sc_fumble
        ON sc_fumble.player_id = sg.player_id
       AND sc_fumble.season = sg.season
       AND sc_fumble.component_name = 'rb_fumble_rate'
      LEFT JOIN stat_components sc_ryoe
        ON sc_ryoe.player_id = sg.player_id
       AND sc_ryoe.season = sg.season
       AND sc_ryoe.component_name = 'rb_ryoe_per_attempt'
      LEFT JOIN stat_components sc_epa
        ON sc_epa.player_id = sg.player_id
       AND sc_epa.season = sg.season
       AND sc_epa.component_name = 'rb_rush_epa_per_attempt'
      LEFT JOIN stat_components sc_succ
        ON sc_succ.player_id = sg.player_id
       AND sc_succ.season = sg.season
       AND sc_succ.component_name = 'rb_rush_success_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'RB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "WR" || position === "TE") {
    // WR/TE share the same headline columns (same component names modulo
    // the wr_/te_ prefix). Branch on prefix rather than duplicating the
    // outer scaffolding.
    const prefix = position === "WR" ? "wr" : "te";
    const cEpa = `${prefix}_rec_epa_per_target`;
    const cYac = `${prefix}_yac_over_expected_per_rec`;
    const cEarn = `${prefix}_target_earn_rate`;
    const rows = await sql<LeaderboardEntry[]>`
      SELECT
        sg.player_id,
        p.full_name,
        sg.position,
        sg.season,
        sg.composite_grade,
        sg.composite_z,
        sg.percentile,
        sg.qualified,
        sg.confidence,
        sg.data_tier,
        sg.role,
        team_lookup.team_abbr,
        sc_epa.sample_size      AS n_targets,
        sc_epa.raw_value        AS rec_epa_per_target,
        sc_yac.raw_value        AS yac_over_expected_per_rec,
        sc_earn.raw_value       AS target_earn_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      ${teamLookupLateralForSgP}
      LEFT JOIN stat_components sc_epa
        ON sc_epa.player_id = sg.player_id
       AND sc_epa.season = sg.season
       AND sc_epa.component_name = ${cEpa}
      LEFT JOIN stat_components sc_yac
        ON sc_yac.player_id = sg.player_id
       AND sc_yac.season = sg.season
       AND sc_yac.component_name = ${cYac}
      LEFT JOIN stat_components sc_earn
        ON sc_earn.player_id = sg.player_id
       AND sc_earn.season = sg.season
       AND sc_earn.component_name = ${cEarn}
      WHERE sg.season = ${season}
        AND sg.position = ${position}
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  // Any other position (none today) — return the minimum shape.
  const rows = await sql<LeaderboardEntry[]>`
    SELECT
      sg.player_id,
      p.full_name,
      sg.position,
      sg.season,
      sg.composite_grade,
      sg.composite_z,
      sg.percentile,
      sg.qualified,
      sg.confidence,
      sg.data_tier,
      sg.role,
      team_lookup.team_abbr
    FROM season_grades sg
    JOIN players p ON p.player_id = sg.player_id
    ${teamLookupLateralForSgP}
    WHERE sg.season = ${season}
      AND sg.position = ${position}
    ORDER BY sg.qualified DESC, sg.composite_grade DESC
  `;
  return rows.map(coerceLeaderboardEntry);
}

/**
 * Shared LATERAL join that resolves a player's primary team for a season
 * by majority offensive snap involvement (passer / rusher / receiver).
 * Assumes `sg` (season_grades alias) and `p` (players alias) are in scope.
 */
const teamLookupLateralForSgP = sql`
  LEFT JOIN LATERAL (
    SELECT pl.posteam AS team_abbr
    FROM plays pl
    WHERE pl.season = sg.season
      AND pl.posteam IS NOT NULL
      AND (
           pl.passer_player_id   = p.gsis_id
        OR pl.rusher_player_id   = p.gsis_id
        OR pl.receiver_player_id = p.gsis_id
      )
    GROUP BY pl.posteam
    ORDER BY COUNT(*) DESC
    LIMIT 1
  ) team_lookup ON TRUE
`;

/**
 * Player detail: metadata + every season grade they have + each grade's
 * component breakdown. Components are nested inside their season.
 *
 * Returns null if the player has no grade rows (either they don't exist
 * or haven't been graded yet).
 */
export async function getPlayerDetail(
  playerId: number,
): Promise<PlayerDetail | null> {
  const metaRows = await sql<
    {
      player_id: number;
      gsis_id: string | null;
      full_name: string;
      position: string;
      current_team_abbr: string | null;
    }[]
  >`
    SELECT
      p.player_id,
      p.gsis_id,
      p.full_name,
      p.position,
      t.abbr AS current_team_abbr
    FROM players p
    LEFT JOIN teams t ON t.team_id = p.current_team_id
    WHERE p.player_id = ${playerId}
  `;
  if (metaRows.length === 0) return null;
  const meta: PlayerMeta = metaRows[0];

  const gradeRows = await sql<
    {
      season: number;
      position: string;
      composite_grade: number;
      composite_z: number;
      percentile: number;
      qualified: boolean;
      confidence: number | null;
      data_tier: number;
      team_abbr: string | null;
    }[]
  >`
    SELECT
      sg.season,
      sg.position,
      sg.composite_grade,
      sg.composite_z,
      sg.percentile,
      sg.qualified,
      sg.confidence,
      sg.data_tier,
      team_lookup.team_abbr
    FROM season_grades sg
    LEFT JOIN LATERAL (
      SELECT pl.posteam AS team_abbr
      FROM plays pl
      WHERE pl.season = sg.season
        AND pl.posteam IS NOT NULL
        AND (
             pl.passer_player_id   = ${meta.gsis_id}
          OR pl.rusher_player_id   = ${meta.gsis_id}
          OR pl.receiver_player_id = ${meta.gsis_id}
        )
      GROUP BY pl.posteam
      ORDER BY COUNT(*) DESC
      LIMIT 1
    ) team_lookup ON TRUE
    WHERE sg.player_id = ${playerId}
    ORDER BY sg.season DESC, sg.position
  `;

  const componentRows = await sql<
    {
      season: number;
      component_name: string;
      raw_value: number | null;
      adjusted_value: number | null;
      z_score: number | null;
      sample_size: number | null;
    }[]
  >`
    SELECT
      season, component_name, raw_value, adjusted_value, z_score, sample_size
    FROM stat_components
    WHERE player_id = ${playerId}
    ORDER BY season DESC, component_name
  `;

  const componentsBySeason = new Map<number, StatComponentDetail[]>();
  for (const row of componentRows) {
    const bucket = componentsBySeason.get(row.season) ?? [];
    bucket.push({
      component_name: row.component_name,
      raw_value: coerceNullableNumber(row.raw_value),
      adjusted_value: coerceNullableNumber(row.adjusted_value),
      z_score: coerceNullableNumber(row.z_score),
      sample_size: row.sample_size === null ? null : Number(row.sample_size),
    });
    componentsBySeason.set(row.season, bucket);
  }

  const grades: SeasonGradeDetail[] = gradeRows.map((g) => ({
    season: g.season,
    position: g.position,
    composite_grade: Number(g.composite_grade),
    composite_z: Number(g.composite_z),
    percentile: Number(g.percentile),
    qualified: g.qualified,
    confidence: coerceNullableNumber(g.confidence),
    data_tier: g.data_tier,
    team_abbr: g.team_abbr,
    components: componentsBySeason.get(g.season) ?? [],
  }));

  return { player: meta, grades };
}

/**
 * The `postgres` driver returns `DOUBLE PRECISION` as JS number, but a
 * future migration to `NUMERIC` would change that silently. Coerce
 * defensively so downstream formatting never sees strings.
 */
function coerceNullableNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return v;
  const parsed = Number(v);
  return Number.isFinite(parsed) ? parsed : null;
}

function coerceNullableInt(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const parsed = Number(v);
  return Number.isFinite(parsed) ? parsed : null;
}

function coerceLeaderboardEntry(row: LeaderboardEntry): LeaderboardEntry {
  return {
    ...row,
    composite_grade: Number(row.composite_grade),
    composite_z: Number(row.composite_z),
    percentile: Number(row.percentile),
    confidence: coerceNullableNumber(row.confidence),
    // QB-only
    n_dropbacks: coerceNullableInt(row.n_dropbacks),
    epa_per_dropback: coerceNullableNumber(row.epa_per_dropback),
    cpoe: coerceNullableNumber(row.cpoe),
    success_rate: coerceNullableNumber(row.success_rate),
    // RB-only
    n_touches: coerceNullableInt(row.n_touches),
    rb_ryoe_per_attempt: coerceNullableNumber(row.rb_ryoe_per_attempt),
    rb_rush_epa_per_attempt: coerceNullableNumber(row.rb_rush_epa_per_attempt),
    rb_rush_success_rate: coerceNullableNumber(row.rb_rush_success_rate),
    // WR/TE shared
    n_targets: coerceNullableInt(row.n_targets),
    rec_epa_per_target: coerceNullableNumber(row.rec_epa_per_target),
    yac_over_expected_per_rec: coerceNullableNumber(
      row.yac_over_expected_per_rec,
    ),
    target_earn_rate: coerceNullableNumber(row.target_earn_rate),
  };
}
