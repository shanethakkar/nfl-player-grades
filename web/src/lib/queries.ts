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
 */
export async function getLeaderboard(
  season: number,
  position: string,
): Promise<LeaderboardEntry[]> {
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
      team_lookup.team_abbr,
      sc_epa.sample_size      AS n_dropbacks,
      sc_epa.raw_value        AS epa_per_dropback,
      sc_cpoe.raw_value       AS cpoe,
      sc_succ.raw_value       AS success_rate
    FROM season_grades sg
    JOIN players p ON p.player_id = sg.player_id
    LEFT JOIN LATERAL (
      SELECT pl.posteam AS team_abbr
      FROM plays pl
      WHERE pl.passer_player_id = p.gsis_id
        AND pl.season = sg.season
        AND pl.posteam IS NOT NULL
      GROUP BY pl.posteam
      ORDER BY COUNT(*) DESC
      LIMIT 1
    ) team_lookup ON TRUE
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
      AND sg.position = ${position}
    ORDER BY sg.qualified DESC, sg.composite_grade DESC
  `;
  return rows.map(coerceLeaderboardEntry);
}

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
      WHERE pl.passer_player_id = ${meta.gsis_id}
        AND pl.season = sg.season
        AND pl.posteam IS NOT NULL
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

function coerceLeaderboardEntry(row: LeaderboardEntry): LeaderboardEntry {
  return {
    ...row,
    composite_grade: Number(row.composite_grade),
    composite_z: Number(row.composite_z),
    percentile: Number(row.percentile),
    confidence: coerceNullableNumber(row.confidence),
    n_dropbacks:
      row.n_dropbacks === null || row.n_dropbacks === undefined
        ? null
        : Number(row.n_dropbacks),
    epa_per_dropback: coerceNullableNumber(row.epa_per_dropback),
    cpoe: coerceNullableNumber(row.cpoe),
    success_rate: coerceNullableNumber(row.success_rate),
  };
}
