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

import { unstable_cache } from "next/cache";

import { sql } from "./db";
import type {
  LeaderboardEntry,
  PlayerDetail,
  PlayerMeta,
  SeasonGradeDetail,
  StatComponentDetail,
  TeamContext,
  TopQb,
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
async function _getLeaderboard(
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
        sc_succ.raw_value       AS rb_rush_success_rate,
        sc_rec_epa.raw_value    AS rec_epa_per_target,
        sc_yac_oe.raw_value     AS rb_yac_over_expected_per_rec,
        sc_yac_carry.raw_value  AS rb_yards_after_contact_per_carry,
        sc_fumble.raw_value     AS rb_fumble_rate
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
      LEFT JOIN stat_components sc_rec_epa
        ON sc_rec_epa.player_id = sg.player_id
       AND sc_rec_epa.season = sg.season
       AND sc_rec_epa.component_name = 'rb_rec_epa_per_target'
      LEFT JOIN stat_components sc_yac_oe
        ON sc_yac_oe.player_id = sg.player_id
       AND sc_yac_oe.season = sg.season
       AND sc_yac_oe.component_name = 'rb_yac_over_expected_per_rec'
      LEFT JOIN stat_components sc_yac_carry
        ON sc_yac_carry.player_id = sg.player_id
       AND sc_yac_carry.season = sg.season
       AND sc_yac_carry.component_name = 'rb_yards_after_contact_per_carry'
      WHERE sg.season = ${season}
        AND sg.position = 'RB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "WR" || position === "TE") {
    // WR/TE share the same headline columns (same component names modulo
    // the wr_/te_ prefix). Branch on prefix rather than duplicating the
    // outer scaffolding. Both positions now use drop_rate (FTN) as the
    // "hands" slot — WR v1.2 + TE v1.1 (2026-05-14).
    const prefix = position === "WR" ? "wr" : "te";
    const cEpa  = `${prefix}_rec_epa_per_target`;
    const cYac  = `${prefix}_yac_over_expected_per_rec`;
    const cSep  = `${prefix}_separation`;
    const cSucc = `${prefix}_success_rate_per_target`;
    const cEarn = `${prefix}_target_earn_rate`;
    const cBallSec = `${prefix}_drop_rate`;
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
        sc_sep.raw_value        AS separation,
        sc_succ.raw_value       AS success_rate_per_target,
        sc_earn.raw_value       AS target_earn_rate,
        sc_ball.raw_value       AS drop_rate
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
      LEFT JOIN stat_components sc_sep
        ON sc_sep.player_id = sg.player_id
       AND sc_sep.season = sg.season
       AND sc_sep.component_name = ${cSep}
      LEFT JOIN stat_components sc_succ
        ON sc_succ.player_id = sg.player_id
       AND sc_succ.season = sg.season
       AND sc_succ.component_name = ${cSucc}
      LEFT JOIN stat_components sc_earn
        ON sc_earn.player_id = sg.player_id
       AND sc_earn.season = sg.season
       AND sc_earn.component_name = ${cEarn}
      LEFT JOIN stat_components sc_ball
        ON sc_ball.player_id = sg.player_id
       AND sc_ball.season = sg.season
       AND sc_ball.component_name = ${cBallSec}
      WHERE sg.season = ${season}
        AND sg.position = ${position}
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "CB") {
    // CB headline columns (ADR-0018 v1.1): passer rating allowed, YAC, target rate, PBU.
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
        t.abbr                   AS team_abbr,
        sc_pra.sample_size       AS n_targets,
        sc_pra.raw_value         AS cb_passer_rating_allowed,
        sc_yac.raw_value         AS cb_yac_per_rec_allowed,
        sc_tgt.raw_value         AS cb_target_rate,
        sc_pbu.raw_value         AS cb_pbu_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_pra
        ON sc_pra.player_id = sg.player_id
       AND sc_pra.season = sg.season
       AND sc_pra.component_name = 'cb_passer_rating_allowed'
      LEFT JOIN stat_components sc_yac
        ON sc_yac.player_id = sg.player_id
       AND sc_yac.season = sg.season
       AND sc_yac.component_name = 'cb_yac_per_rec_allowed'
      LEFT JOIN stat_components sc_tgt
        ON sc_tgt.player_id = sg.player_id
       AND sc_tgt.season = sg.season
       AND sc_tgt.component_name = 'cb_target_rate'
      LEFT JOIN stat_components sc_pbu
        ON sc_pbu.player_id = sg.player_id
       AND sc_pbu.season = sg.season
       AND sc_pbu.component_name = 'cb_pbu_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'CB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "S") {
    // Safety headline columns (ADR-0019 v1.1): passer rating allowed, PBU, tackles/snap.
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
        t.abbr                        AS team_abbr,
        sc_tgt.sample_size            AS n_snaps,
        sc_pra.raw_value              AS s_passer_rating_allowed,
        sc_tgt.raw_value              AS s_target_rate,
        sc_pbu.raw_value              AS s_pbu_rate,
        sc_tkl.raw_value              AS s_tackles_per_snap,
        sc_miss.raw_value             AS s_missed_tackle_rate,
        sc_dis.raw_value              AS s_backfield_disruption_per_snap
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_tgt
        ON sc_tgt.player_id = sg.player_id
       AND sc_tgt.season = sg.season
       AND sc_tgt.component_name = 's_target_rate'
      LEFT JOIN stat_components sc_pra
        ON sc_pra.player_id = sg.player_id
       AND sc_pra.season = sg.season
       AND sc_pra.component_name = 's_passer_rating_allowed'
      LEFT JOIN stat_components sc_pbu
        ON sc_pbu.player_id = sg.player_id
       AND sc_pbu.season = sg.season
       AND sc_pbu.component_name = 's_pbu_rate'
      LEFT JOIN stat_components sc_tkl
        ON sc_tkl.player_id = sg.player_id
       AND sc_tkl.season = sg.season
       AND sc_tkl.component_name = 's_tackles_per_snap'
      LEFT JOIN stat_components sc_miss
        ON sc_miss.player_id = sg.player_id
       AND sc_miss.season = sg.season
       AND sc_miss.component_name = 's_missed_tackle_rate'
      LEFT JOIN stat_components sc_dis
        ON sc_dis.player_id = sg.player_id
       AND sc_dis.season = sg.season
       AND sc_dis.component_name = 's_backfield_disruption_per_snap'
      WHERE sg.season = ${season}
        AND sg.position = 'S'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "EDGE") {
    // EDGE headline columns (ADR-0020): pressure rate, sack rate, TFL rate.
    // Team resolved via player_seasons (EDGE players don't appear in plays as offensive players).
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
        t.abbr                        AS team_abbr,
        sc_press.sample_size          AS n_snaps,
        sc_press.raw_value            AS edge_pressure_rate,
        sc_sack.raw_value             AS edge_sack_rate,
        sc_tfl.raw_value              AS edge_tfl_rate,
        sc_tps.raw_value              AS edge_tackles_per_snap,
        sc_miss.raw_value             AS edge_missed_tackle_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_press
        ON sc_press.player_id = sg.player_id
       AND sc_press.season = sg.season
       AND sc_press.component_name = 'edge_pressure_rate'
      LEFT JOIN stat_components sc_sack
        ON sc_sack.player_id = sg.player_id
       AND sc_sack.season = sg.season
       AND sc_sack.component_name = 'edge_sack_rate'
      LEFT JOIN stat_components sc_tfl
        ON sc_tfl.player_id = sg.player_id
       AND sc_tfl.season = sg.season
       AND sc_tfl.component_name = 'edge_tfl_rate'
      LEFT JOIN stat_components sc_tps
        ON sc_tps.player_id = sg.player_id
       AND sc_tps.season = sg.season
       AND sc_tps.component_name = 'edge_tackles_per_snap'
      LEFT JOIN stat_components sc_miss
        ON sc_miss.player_id = sg.player_id
       AND sc_miss.season = sg.season
       AND sc_miss.component_name = 'edge_missed_tackle_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'EDGE'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "LB") {
    // LB headline columns (ADR-0022).
    // Team resolved via player_seasons.
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
        t.abbr                        AS team_abbr,
        sc_tfl.sample_size            AS n_snaps,
        sc_tfl.raw_value              AS lb_tfl_rate,
        sc_pra.raw_value              AS lb_passer_rating_allowed,
        sc_miss.raw_value             AS lb_missed_tackle_rate,
        sc_pbu.raw_value              AS lb_pbu_rate,
        sc_tkl.raw_value              AS lb_tackle_rate,
        sc_prs.raw_value              AS lb_pressure_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_tfl
        ON sc_tfl.player_id = sg.player_id
       AND sc_tfl.season = sg.season
       AND sc_tfl.component_name = 'lb_tfl_rate'
      LEFT JOIN stat_components sc_pra
        ON sc_pra.player_id = sg.player_id
       AND sc_pra.season = sg.season
       AND sc_pra.component_name = 'lb_passer_rating_allowed'
      LEFT JOIN stat_components sc_miss
        ON sc_miss.player_id = sg.player_id
       AND sc_miss.season = sg.season
       AND sc_miss.component_name = 'lb_missed_tackle_rate'
      LEFT JOIN stat_components sc_pbu
        ON sc_pbu.player_id = sg.player_id
       AND sc_pbu.season = sg.season
       AND sc_pbu.component_name = 'lb_pbu_rate'
      LEFT JOIN stat_components sc_tkl
        ON sc_tkl.player_id = sg.player_id
       AND sc_tkl.season = sg.season
       AND sc_tkl.component_name = 'lb_tackle_rate'
      LEFT JOIN stat_components sc_prs
        ON sc_prs.player_id = sg.player_id
       AND sc_prs.season = sg.season
       AND sc_prs.component_name = 'lb_pressure_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'LB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  if (position === "iDL") {
    // iDL headline columns (ADR-0021): TFL rate, pressure rate, sack rate, missed tackle rate.
    // Team resolved via player_seasons (iDL players don't appear in plays as offensive players).
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
        t.abbr                        AS team_abbr,
        sc_tfl.sample_size            AS n_snaps,
        sc_tfl.raw_value              AS idl_tfl_rate,
        sc_press.raw_value            AS idl_pressure_rate,
        sc_sack.raw_value             AS idl_sack_rate,
        sc_tps.raw_value              AS idl_tackles_per_snap,
        sc_miss.raw_value             AS idl_missed_tackle_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_tfl
        ON sc_tfl.player_id = sg.player_id
       AND sc_tfl.season = sg.season
       AND sc_tfl.component_name = 'idl_tfl_rate'
      LEFT JOIN stat_components sc_press
        ON sc_press.player_id = sg.player_id
       AND sc_press.season = sg.season
       AND sc_press.component_name = 'idl_pressure_rate'
      LEFT JOIN stat_components sc_sack
        ON sc_sack.player_id = sg.player_id
       AND sc_sack.season = sg.season
       AND sc_sack.component_name = 'idl_sack_rate'
      LEFT JOIN stat_components sc_tps
        ON sc_tps.player_id = sg.player_id
       AND sc_tps.season = sg.season
       AND sc_tps.component_name = 'idl_tackles_per_snap'
      LEFT JOIN stat_components sc_miss
        ON sc_miss.player_id = sg.player_id
       AND sc_miss.season = sg.season
       AND sc_miss.component_name = 'idl_missed_tackle_rate'
      WHERE sg.season = ${season}
        AND sg.position = 'iDL'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    return rows.map(coerceLeaderboardEntry);
  }

  // Any other position — return the minimum shape.
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
 * Header autocomplete query.
 *
 * Restricted to players who appear in `season_grades` for at least one
 * season — otherwise the index would be dominated by linemen, kickers,
 * and the long tail of practice-squad bodies in `players`. Ranking
 * prefers the player's best-ever composite, with a recency tiebreaker
 * so an active star outranks a retired one with the same peak.
 *
 * `q` is case-insensitive substring match against `full_name`. We also
 * surface the player's most recent graded position + team so the
 * dropdown can disambiguate (e.g. "Brian Robinson" the RB vs. anyone
 * else who shares a name).
 */
export type PlayerSearchHit = {
  player_id: number;
  full_name: string;
  position: string;
  team_abbr: string | null;
  best_grade: number;
  latest_season: number;
};

export async function searchPlayers(
  q: string,
  limit = 8,
): Promise<PlayerSearchHit[]> {
  const trimmed = q.trim();
  if (trimmed.length < 2) return [];
  const pattern = `%${trimmed.replace(/[%_]/g, "\\$&")}%`;
  const rows = await sql<
    {
      player_id: number;
      full_name: string;
      position: string;
      team_abbr: string | null;
      best_grade: number;
      latest_season: number;
    }[]
  >`
    WITH matches AS (
      SELECT
        p.player_id,
        p.full_name,
        sg.position,
        sg.season,
        sg.composite_grade,
        ROW_NUMBER() OVER (
          PARTITION BY p.player_id
          ORDER BY sg.season DESC
        ) AS recency_rank,
        MAX(sg.composite_grade) OVER (PARTITION BY p.player_id) AS best_grade,
        MAX(sg.season) OVER (PARTITION BY p.player_id) AS latest_season
      FROM players p
      JOIN season_grades sg ON sg.player_id = p.player_id
      WHERE p.full_name ILIKE ${pattern} ESCAPE '\\'
    )
    SELECT
      m.player_id,
      m.full_name,
      m.position,
      m.best_grade,
      m.latest_season,
      team_lookup.team_abbr
    FROM matches m
    JOIN players p ON p.player_id = m.player_id
    LEFT JOIN LATERAL (
      SELECT pl.posteam AS team_abbr
      FROM plays pl
      WHERE pl.season = m.latest_season
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
    WHERE m.recency_rank = 1
    ORDER BY m.best_grade DESC, m.latest_season DESC, m.full_name ASC
    LIMIT ${limit}
  `;
  return rows.map((r) => ({
    player_id: Number(r.player_id),
    full_name: r.full_name,
    position: r.position,
    team_abbr: r.team_abbr,
    best_grade: Number(r.best_grade),
    latest_season: Number(r.latest_season),
  }));
}

/**
 * Player detail: metadata + every season grade they have + each grade's
 * component breakdown. Components are nested inside their season.
 *
 * Returns null if the player has no grade rows (either they don't exist
 * or haven't been graded yet).
 */
async function _getPlayerDetail(
  playerId: number,
): Promise<PlayerDetail | null> {
  // Three independent queries — run in parallel.
  const [metaRows, gradeRows, componentRows] = await Promise.all([
    sql<
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
    `,
    sql<
      {
        season: number;
        position: string;
        composite_grade: number;
        composite_z: number;
        percentile: number;
        qualified: boolean;
        confidence: number | null;
        data_tier: number;
        role: string | null;
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
        sg.role,
        sg.team_abbr
      FROM season_grades sg
      WHERE sg.player_id = ${playerId}
      ORDER BY sg.season DESC, sg.position
    `,
    sql<
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
    `,
  ]);

  if (metaRows.length === 0) return null;
  const meta: PlayerMeta = metaRows[0];

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

  // Team/offense context for non-QB grades (ADR-0017). One batch for all
  // of the player's seasons at once so we avoid N+1 queries.
  const nonQbGradeKeys = gradeRows
    .filter((g) => g.position !== "QB" && g.team_abbr)
    .map((g) => ({
      player_id: playerId,
      season: g.season,
      position: g.position,
      team_abbr: g.team_abbr as string,
    }));
  const contextByKey = await getTeamContexts(nonQbGradeKeys);

  const grades: SeasonGradeDetail[] = gradeRows.map((g) => ({
    season: g.season,
    position: g.position,
    composite_grade: Number(g.composite_grade),
    composite_z: Number(g.composite_z),
    percentile: Number(g.percentile),
    qualified: g.qualified,
    confidence: coerceNullableNumber(g.confidence),
    data_tier: g.data_tier,
    role: g.role,
    team_abbr: g.team_abbr,
    components: componentsBySeason.get(g.season) ?? [],
    context:
      g.team_abbr && g.position !== "QB"
        ? contextByKey.get(
            contextKey({
              season: g.season,
              team_abbr: g.team_abbr,
              position: g.position,
              player_id: playerId,
            }),
          ) ?? null
        : null,
  }));

  return { player: meta, grades };
}

// ---------------------------------------------------------------------------
// Team/offense context for ADR-0017 mitigation
//
// Given the set of (season, team, position, player) tuples from a player's
// non-QB grade rows, returns a Map<context-key, TeamContext>. Three
// underlying queries:
//   1. Team offense EPA + rank for every season in the set.
//   2. Lead QB + grade for every (team, season) in the set.
//   3. Top-15 volume cutoff per (season, position) — used to fire the
//      ADR-0017 inline note only on high-volume receivers.
// All three are single queries regardless of how many seasons a player
// has, so the whole context fetch is 3 roundtrips.
// ---------------------------------------------------------------------------

type ContextKey = {
  season: number;
  team_abbr: string;
  position: string;
  player_id: number;
};

function contextKey(k: ContextKey): string {
  return `${k.season}:${k.team_abbr}:${k.position}:${k.player_id}`;
}

async function getTeamContexts(
  keys: ContextKey[],
): Promise<Map<string, TeamContext>> {
  if (keys.length === 0) return new Map();

  const seasons = Array.from(new Set(keys.map((k) => k.season)));

  // All three queries are independent — run in parallel.
  const [epaRows, qbRows, volumeRows] = await Promise.all([
    // --- Query 1: team EPA/play + rank per season (pre-computed table) ---
    sql<
      {
        season: number;
        posteam: string;
        epa_per_play: number;
        rk: number;
        n_teams: number;
      }[]
    >`
      SELECT season, team_abbr AS posteam, epa_per_play, epa_rank AS rk, n_teams
      FROM team_season_epa
      WHERE season = ANY(${seasons})
    `,

    // --- Query 2: lead QB per (team, season) + their season_grades row ---
    // Dropback definition: pass attempt OR sack OR QB scramble. Matches
    // QB v1 feature extraction (ADR-0013).
    sql<
      {
        season: number;
        team_abbr: string;
        player_id: number;
        full_name: string;
        n_dropbacks: number;
        composite_grade: number | null;
        qualified: boolean | null;
      }[]
    >`
      WITH qb_team_dropbacks AS (
        SELECT
          pl.passer_player_id AS gsis_id,
          pl.posteam          AS team_abbr,
          pl.season,
          COUNT(*)::int       AS n_dropbacks
        FROM plays pl
        WHERE pl.season = ANY(${seasons})
          AND pl.posteam IS NOT NULL
          AND pl.passer_player_id IS NOT NULL
          AND (pl.pass_attempt = TRUE OR pl.sack = TRUE OR pl.qb_scramble = TRUE)
        GROUP BY 1, 2, 3
      ),
      lead_qb AS (
        SELECT DISTINCT ON (season, team_abbr)
          season, team_abbr, gsis_id, n_dropbacks
        FROM qb_team_dropbacks
        ORDER BY season, team_abbr, n_dropbacks DESC
      )
      SELECT
        lq.season,
        lq.team_abbr,
        p.player_id,
        p.full_name,
        lq.n_dropbacks,
        sg.composite_grade,
        sg.qualified
      FROM lead_qb lq
      JOIN players p ON p.gsis_id = lq.gsis_id
      LEFT JOIN season_grades sg
        ON sg.player_id = p.player_id
       AND sg.season = lq.season
       AND sg.position = 'QB'
    `,

    // --- Query 3: top-15 volume per (season, position) ---
    // Volume proxy = sample_size on the "touches" (RB) or "targets" (WR/TE)
    // component, pulled from stat_components. RANK, then filter rk <= 15.
    sql<
      {
        season: number;
        position: string;
        player_id: number;
      }[]
    >`
      WITH volume_components AS (
        SELECT
          sc.player_id,
          sc.season,
          CASE
            WHEN sc.component_name = 'rb_fumble_rate'                THEN 'RB'
            WHEN sc.component_name = 'wr_rec_epa_per_target'         THEN 'WR'
            WHEN sc.component_name = 'te_rec_epa_per_target'         THEN 'TE'
          END AS position,
          sc.sample_size AS volume
        FROM stat_components sc
        WHERE sc.season = ANY(${seasons})
          AND sc.component_name IN (
            'rb_fumble_rate',
            'wr_rec_epa_per_target',
            'te_rec_epa_per_target'
          )
          AND sc.sample_size IS NOT NULL
      ),
      ranked AS (
        SELECT
          player_id, season, position, volume,
          RANK() OVER (
            PARTITION BY season, position
            ORDER BY volume DESC NULLS LAST
          )::int AS rk
        FROM volume_components
      )
      SELECT player_id, season, position
      FROM ranked
      WHERE rk <= 15
    `,
  ]);

  const epaByKey = new Map<string, { epa_per_play: number; rk: number; n_teams: number }>();
  for (const r of epaRows) {
    epaByKey.set(`${r.season}:${r.posteam}`, {
      epa_per_play: Number(r.epa_per_play),
      rk: Number(r.rk),
      n_teams: Number(r.n_teams),
    });
  }

  const qbByKey = new Map<string, TopQb>();
  for (const r of qbRows) {
    qbByKey.set(`${r.season}:${r.team_abbr}`, {
      player_id: Number(r.player_id),
      full_name: r.full_name,
      composite_grade:
        r.composite_grade === null ? null : Number(r.composite_grade),
      qualified: r.qualified,
      dropbacks: Number(r.n_dropbacks),
    });
  }

  const highVolumeSet = new Set(
    volumeRows.map((r) => `${r.season}:${r.position}:${r.player_id}`),
  );

  // --- Assemble ---
  const out = new Map<string, TeamContext>();
  for (const k of keys) {
    const epa = epaByKey.get(`${k.season}:${k.team_abbr}`);
    const qb = qbByKey.get(`${k.season}:${k.team_abbr}`) ?? null;
    if (!epa) continue;
    out.set(contextKey(k), {
      team_abbr: k.team_abbr,
      season: k.season,
      team_epa_per_play: epa.epa_per_play,
      team_epa_rank: epa.rk,
      team_epa_total: epa.n_teams,
      top_qb: qb,
      player_high_volume: highVolumeSet.has(
        `${k.season}:${k.position}:${k.player_id}`,
      ),
    });
  }
  return out;
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

// ---------------------------------------------------------------------------
// Cached public exports
// Wrap the internal async functions with unstable_cache so repeated requests
// for the same player / leaderboard hit Next.js's data cache instead of the
// DB. TTL 1 hour — grades only change when the pipeline runs (at most daily).
// ---------------------------------------------------------------------------

export const getLeaderboard = unstable_cache(
  _getLeaderboard,
  ["leaderboard"],
  { revalidate: 3600 },
);

export const getPlayerDetail = unstable_cache(
  _getPlayerDetail,
  ["player-detail"],
  { revalidate: 3600 },
);

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
    rb_yac_over_expected_per_rec: coerceNullableNumber(row.rb_yac_over_expected_per_rec),
    rb_yards_after_contact_per_carry: coerceNullableNumber(row.rb_yards_after_contact_per_carry),
    rb_fumble_rate: coerceNullableNumber(row.rb_fumble_rate),
    // WR/TE shared
    n_targets: coerceNullableInt(row.n_targets),
    rec_epa_per_target: coerceNullableNumber(row.rec_epa_per_target),
    yac_over_expected_per_rec: coerceNullableNumber(row.yac_over_expected_per_rec),
    separation: coerceNullableNumber(row.separation),
    success_rate_per_target: coerceNullableNumber(row.success_rate_per_target),
    target_earn_rate: coerceNullableNumber(row.target_earn_rate),
    drop_rate: coerceNullableNumber(row.drop_rate),
    // CB-only
    cb_passer_rating_allowed: coerceNullableNumber(row.cb_passer_rating_allowed),
    cb_yac_per_rec_allowed: coerceNullableNumber(row.cb_yac_per_rec_allowed),
    cb_target_rate: coerceNullableNumber(row.cb_target_rate),
    cb_pbu_rate: coerceNullableNumber(row.cb_pbu_rate),
    // S-only
    n_snaps: coerceNullableInt(row.n_snaps),
    s_passer_rating_allowed: coerceNullableNumber(row.s_passer_rating_allowed),
    s_target_rate: coerceNullableNumber(row.s_target_rate),
    s_pbu_rate: coerceNullableNumber(row.s_pbu_rate),
    s_tackles_per_snap: coerceNullableNumber(row.s_tackles_per_snap),
    s_missed_tackle_rate: coerceNullableNumber(row.s_missed_tackle_rate),
    s_backfield_disruption_per_snap: coerceNullableNumber(row.s_backfield_disruption_per_snap),
    // EDGE-only
    edge_pressure_rate: coerceNullableNumber(row.edge_pressure_rate),
    edge_sack_rate: coerceNullableNumber(row.edge_sack_rate),
    edge_tfl_rate: coerceNullableNumber(row.edge_tfl_rate),
    edge_tackles_per_snap: coerceNullableNumber(row.edge_tackles_per_snap),
    edge_missed_tackle_rate: coerceNullableNumber(row.edge_missed_tackle_rate),
    // iDL-only
    idl_tfl_rate: coerceNullableNumber(row.idl_tfl_rate),
    idl_pressure_rate: coerceNullableNumber(row.idl_pressure_rate),
    idl_sack_rate: coerceNullableNumber(row.idl_sack_rate),
    idl_tackles_per_snap: coerceNullableNumber(row.idl_tackles_per_snap),
    idl_missed_tackle_rate: coerceNullableNumber(row.idl_missed_tackle_rate),
    // LB-only
    lb_tfl_rate: coerceNullableNumber(row.lb_tfl_rate),
    lb_passer_rating_allowed: coerceNullableNumber(row.lb_passer_rating_allowed),
    lb_missed_tackle_rate: coerceNullableNumber(row.lb_missed_tackle_rate),
    lb_pbu_rate: coerceNullableNumber(row.lb_pbu_rate),
    lb_tackle_rate: coerceNullableNumber(row.lb_tackle_rate),
    lb_pressure_rate: coerceNullableNumber(row.lb_pressure_rate),
  };
}
