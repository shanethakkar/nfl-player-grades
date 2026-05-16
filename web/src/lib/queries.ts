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
  Conference,
  Division,
  LeaderboardEntry,
  LineupSlot,
  PlayerDetail,
  PlayerMeta,
  SeasonGradeDetail,
  StatComponentDetail,
  Team,
  TeamContext,
  TeamLineup,
  TeamRosterEntry,
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
 * All 32 teams, ordered by conference → division → name. Used by the
 * /teams index page to render the grouped logo grid.
 */
export async function getAllTeams(): Promise<Team[]> {
  const rows = await sql<Team[]>`
    SELECT team_id, abbr, name, conference, division,
           primary_color, secondary_color
    FROM teams
    ORDER BY conference, division, name
  `;
  return rows.map((r) => ({
    ...r,
    team_id: Number(r.team_id),
    conference: r.conference as Conference,
    division: r.division as Division,
  }));
}

/**
 * Seasons we have any player_seasons rows for this team — used to
 * populate the year selector on the team page. Ordered newest first.
 */
export async function getTeamSeasons(teamAbbr: string): Promise<number[]> {
  const rows = await sql<{ season: number }[]>`
    SELECT DISTINCT ps.season
    FROM player_seasons ps
    JOIN teams t ON t.team_id = ps.team_id
    WHERE t.abbr = ${teamAbbr}
    ORDER BY ps.season DESC
  `;
  return rows.map((r) => Number(r.season));
}

/**
 * Minimal team metadata for the header on /teams/[abbr]. Returns null
 * when no team matches the abbr (e.g. typo in URL).
 */
export async function getTeamByAbbr(teamAbbr: string): Promise<Team | null> {
  const rows = await sql<Team[]>`
    SELECT team_id, abbr, name, conference, division,
           primary_color, secondary_color
    FROM teams
    WHERE abbr = ${teamAbbr}
    LIMIT 1
  `;
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    team_id: Number(row.team_id),
    conference: row.conference as Conference,
    division: row.division as Division,
  };
}

/**
 * Every player who appears in player_seasons for (teamAbbr, season),
 * left-joined with their best-graded season_grades row for that season
 * (highest composite_grade wins if a player has multiple grading
 * positions — rare in practice).
 *
 * Ordering: qualified players first by grade desc, then everyone else
 * by total snaps desc. Gives a sensible default view without forcing
 * sort-on-load on the client.
 */
async function _getTeamRoster(
  teamAbbr: string,
  season: number,
): Promise<TeamRosterEntry[]> {
  const rows = await sql<TeamRosterEntry[]>`
    SELECT
      p.player_id,
      p.full_name,
      ps.position_played,
      ps.games,
      ps.games_started,
      ps.snaps_offense,
      ps.snaps_defense,
      ps.snaps_special,
      (ps.snaps_offense + ps.snaps_defense + ps.snaps_special) AS total_snaps,
      sg.composite_grade,
      sg.percentile,
      sg.qualified,
      sg.position                                              AS grading_position,
      EXISTS(
        SELECT 1 FROM player_seasons ps2
        WHERE ps2.player_id = p.player_id
          AND ps2.season    = ps.season
          AND ps2.team_id  != ps.team_id
      )                                                        AS traded_in_season
    FROM player_seasons ps
    JOIN teams   t ON t.team_id   = ps.team_id
    JOIN players p ON p.player_id = ps.player_id
    LEFT JOIN LATERAL (
      SELECT composite_grade, percentile, qualified, position
      FROM season_grades sg2
      WHERE sg2.player_id = p.player_id
        AND sg2.season    = ps.season
      ORDER BY sg2.composite_grade DESC
      LIMIT 1
    ) sg ON TRUE
    WHERE t.abbr   = ${teamAbbr}
      AND ps.season = ${season}
    ORDER BY
      (sg.qualified IS TRUE) DESC,
      sg.composite_grade DESC NULLS LAST,
      (ps.snaps_offense + ps.snaps_defense + ps.snaps_special) DESC NULLS LAST
  `;
  return rows.map((r) => ({
    player_id: Number(r.player_id),
    full_name: r.full_name,
    position_played: r.position_played,
    games: Number(r.games),
    games_started: Number(r.games_started),
    snaps_offense: Number(r.snaps_offense),
    snaps_defense: Number(r.snaps_defense),
    snaps_special: Number(r.snaps_special),
    total_snaps: Number(r.total_snaps),
    composite_grade:
      r.composite_grade === null ? null : Number(r.composite_grade),
    percentile: r.percentile === null ? null : Number(r.percentile),
    qualified: r.qualified,
    grading_position: r.grading_position,
    traded_in_season: r.traded_in_season,
  }));
}

export const getTeamRoster = unstable_cache(_getTeamRoster, ["team-roster"], {
  revalidate: 3600,
});

// ---------------------------------------------------------------------------
// Team lineup (depth-chart starters mapped onto a canonical formation).
// ---------------------------------------------------------------------------

type RawLineupRow = {
  position: string;
  depth_order: number;
  player_id: number;
  full_name: string;
  composite_grade: number | null;
  qualified: boolean | null;
  grading_position: string | null;
  grade_season: number | null;
};

/**
 * nflverse depth chart labels are inconsistent — teams variously use
 * "DE"/"LDE"/"RDE"/"EDGE", "S"/"FS"/"SS", etc. These maps collapse the
 * variations onto canonical groups so the lineup builder can pick the
 * right player for each formation slot regardless of which label the
 * team used.
 */
// nflverse depth-chart labels split differently between 4-3 and 3-4 fronts.
// In a 4-3, edges are DEs and OLBs are linebackers. In a 3-4, edges are the
// outside LBs (WLB/SLB/OLB) and the DE labels are 5-technique interior
// players. Bills 2025 are the canonical 3-4 case (LDE=Oliver, NT=Walker,
// WLB=Rousseau, SLB=Chubb). We pick the right pool at runtime based on
// whether the depth chart looks 3-4-shaped.
const EDGE_LABELS_4_3 = ["DE", "LDE", "RDE", "EDGE", "RUSH"];
const EDGE_LABELS_3_4 = ["WLB", "SLB", "OLB", "LOLB", "ROLB"];
const IDL_LABELS_4_3 = new Set(["DT", "LDT", "RDT", "NT", "DL"]);
// In 3-4, the LDE/RDE players are interior 5-techs — include them as iDL.
const IDL_LABELS_3_4 = new Set([
  "NT", "DT", "LDT", "RDT", "DL", "LDE", "RDE", "DE",
]);
const LB_LABELS_4_3 = new Set([
  "LB", "ILB", "MLB",
  "LILB", "RILB",
  "WLB", "SLB", "WILL", "MIKE", "SAM",
  // OLB still eligible — if not taken as edge, it's a coverage backer.
  "OLB", "LOLB", "ROLB",
]);
// In 3-4, the outside LBs are edges — exclude them from the LB pool.
const LB_LABELS_3_4 = new Set([
  "LB", "ILB", "MLB", "MIKE",
  "LILB", "RILB",
]);
const SLOT_CB_LABELS = new Set(["NCB", "NB", "NKL", "DB"]);
const SAFETY_LABELS = new Set(["S", "FS", "SS", "SAF"]);

async function _getTeamLineup(
  teamAbbr: string,
  season: number,
): Promise<TeamLineup> {
  // One query: depth chart rows (week=99 end-of-season snapshot) joined
  // with each player's best-graded season_grades row.
  // Grade lookup prefers the current-season row but falls back to the
  // player's most recent prior-season grade when there isn't one yet
  // (rookies, mid-season callups, in-progress seasons). The render layer
  // shows an asterisk + tooltip when grade_season != dc.season so the
  // reader knows it's stale.
  const rows = await sql<RawLineupRow[]>`
    SELECT
      dc.position,
      dc.depth_order,
      p.player_id,
      p.full_name,
      sg.composite_grade,
      sg.qualified,
      sg.position AS grading_position,
      sg.season   AS grade_season
    FROM depth_charts dc
    JOIN teams   t ON t.team_id   = dc.team_id
    JOIN players p ON p.player_id = dc.player_id
    LEFT JOIN LATERAL (
      SELECT composite_grade, qualified, position, season
      FROM season_grades sg2
      WHERE sg2.player_id = p.player_id
        AND sg2.season   <= dc.season
      ORDER BY
        (CASE WHEN sg2.season = dc.season THEN 0 ELSE 1 END) ASC,
        sg2.season DESC,
        sg2.composite_grade DESC
      LIMIT 1
    ) sg ON TRUE
    WHERE t.abbr     = ${teamAbbr}
      AND dc.season  = ${season}
      AND dc.week    = 99
    ORDER BY dc.position, dc.depth_order
  `;

  // Team OL grade is a separate table (team_ol_grades, ADR-0025). One row
  // per (team, season). Missing pre-2018.
  const olRows = await sql<{
    composite_grade: number;
    qualified: boolean;
  }[]>`
    SELECT g.composite_grade, g.qualified
    FROM team_ol_grades g
    JOIN teams t ON t.team_id = g.team_id
    WHERE t.abbr = ${teamAbbr} AND g.season = ${season}
    LIMIT 1
  `;

  const grouped = new Map<string, RawLineupRow[]>();
  for (const r of rows) {
    const list = grouped.get(r.position) ?? [];
    list.push({ ...r, depth_order: Number(r.depth_order), player_id: Number(r.player_id) });
    grouped.set(r.position, list);
  }

  // Helper: build a slot from one raw row, attaching the canonical label.
  function toSlot(slot: string, r: RawLineupRow | undefined): LineupSlot | null {
    if (!r) return null;
    return {
      slot,
      raw_position: r.position,
      depth_order: r.depth_order,
      player_id: r.player_id,
      full_name: r.full_name,
      composite_grade:
        r.composite_grade === null ? null : Number(r.composite_grade),
      qualified: r.qualified,
      grading_position: r.grading_position,
      grade_season: r.grade_season === null ? null : Number(r.grade_season),
    };
  }

  // Pick first depth row from any of the given labels (priority order
  // matches the list). Used for DL/LB/secondary where labels vary by team.
  function pickFirstFrom(
    labels: string[],
    excludeIds: Set<number> = new Set(),
    depthOrder: number = 1,
  ): RawLineupRow | undefined {
    for (const label of labels) {
      const list = grouped.get(label) ?? [];
      const match = list.find(
        (r) => r.depth_order === depthOrder && !excludeIds.has(r.player_id),
      );
      if (match) return match;
    }
    return undefined;
  }

  // Pick top N starters across a set of labels, by depth_order asc then
  // by composite_grade desc (graded players bubble up). Excludes already-
  // picked player_ids. Used for DL (4) and LB (3).
  function pickTopNAcross(
    labelSet: Set<string>,
    n: number,
    excludeIds: Set<number>,
  ): RawLineupRow[] {
    const all: RawLineupRow[] = [];
    for (const [pos, list] of grouped.entries()) {
      if (!labelSet.has(pos)) continue;
      for (const r of list) all.push(r);
    }
    const picked: RawLineupRow[] = [];
    const taken = new Set(excludeIds);
    // Sort by depth (starters first), then by grade desc (so DE depth=1
    // with grade 80 beats DT depth=1 with grade 50 when filling slots).
    all.sort((a, b) => {
      if (a.depth_order !== b.depth_order) return a.depth_order - b.depth_order;
      const ag = a.composite_grade ?? -Infinity;
      const bg = b.composite_grade ?? -Infinity;
      return Number(bg) - Number(ag);
    });
    for (const r of all) {
      if (taken.has(r.player_id)) continue;
      picked.push(r);
      taken.add(r.player_id);
      if (picked.length === n) break;
    }
    return picked;
  }

  // --- Offense ---
  const wrList = grouped.get("WR") ?? [];
  const qb = toSlot("QB", (grouped.get("QB") ?? [])[0]);
  const rb = toSlot(
    "RB",
    (grouped.get("RB") ?? [])[0] ?? (grouped.get("HB") ?? [])[0],
  );
  const wr1 = toSlot("WR1", wrList[0]);
  const wr2 = toSlot("WR2", wrList[1]);
  const slot_wr = toSlot("SLOT", wrList[2]);
  const te = toSlot("TE", (grouped.get("TE") ?? [])[0]);

  // OL — take depth=1 from each of LT/LG/C/RG/RT.
  const ol_starters: LineupSlot[] = [];
  for (const label of ["LT", "LG", "C", "RG", "RT"]) {
    const r = (grouped.get(label) ?? []).find((x) => x.depth_order === 1);
    if (r) ol_starters.push({
      slot: label,
      raw_position: r.position,
      depth_order: r.depth_order,
      player_id: r.player_id,
      full_name: r.full_name,
      composite_grade: null, // hidden — OL is a team grade, not per-player
      qualified: null,
      grading_position: null,
      grade_season: null,
    });
  }
  const ol_team_grade = olRows[0]?.composite_grade ?? null;
  const ol_team_qualified = olRows[0]?.qualified ?? null;

  // --- Defense ---
  // Build the defensive 11 in this order so we can decide LB count based
  // on whether a slot CB exists:
  //   - 2 CBs, 1 optional slot CB
  //   - 2 safeties
  //   - 4 DL
  //   - LBs: 2 if slot CB present (modern nickel), 3 otherwise (base)
  // Total: always 11. Tracks picked player_ids to avoid double-placing
  // a player whose depth-chart position appears in multiple buckets.
  const taken = new Set<number>();

  // CBs: prefer LCB/RCB labels, otherwise CB depth 1+2.
  const cb1Raw =
    pickFirstFrom(["LCB"], taken, 1) ??
    pickFirstFrom(["CB"], taken, 1);
  if (cb1Raw) taken.add(cb1Raw.player_id);
  const cb2Raw =
    pickFirstFrom(["RCB"], taken, 1) ??
    pickFirstFrom(["CB"], taken, 2) ??
    pickFirstFrom(["CB"], taken, 1);
  if (cb2Raw) taken.add(cb2Raw.player_id);
  const cb1 = toSlot("LCB", cb1Raw);
  const cb2 = toSlot("RCB", cb2Raw);

  // Slot CB: optional — only if depth chart explicitly has one.
  const slotCbRaw = pickFirstFrom(
    Array.from(SLOT_CB_LABELS),
    taken,
    1,
  );
  if (slotCbRaw) taken.add(slotCbRaw.player_id);
  const slot_cb = toSlot("SLOT CB", slotCbRaw);

  // Safeties: prefer FS/SS labels, otherwise S depth 1+2.
  const fsRaw =
    pickFirstFrom(["FS"], taken, 1) ??
    pickFirstFrom(["S", "SAF"], taken, 1);
  if (fsRaw) taken.add(fsRaw.player_id);
  const ssRaw =
    pickFirstFrom(["SS"], taken, 1) ??
    pickFirstFrom(["S", "SAF"], taken, 2) ??
    pickFirstFrom(["S", "SAF"], taken, 1);
  if (ssRaw) taken.add(ssRaw.player_id);
  const fs = toSlot("FS", fsRaw);
  const ss = toSlot("SS", ssRaw);

  // Detect 3-4 front: depth chart has NT and no DT-equivalent. Bills 2025
  // hits this branch (LDE/RDE/NT, no DT/LDT/RDT). Routes WLB/SLB to EDGE
  // and LDE/RDE to iDL — matches how those players actually align.
  const has34Front =
    (grouped.get("NT") ?? []).length > 0 &&
    (grouped.get("DT") ?? []).length === 0 &&
    (grouped.get("LDT") ?? []).length === 0 &&
    (grouped.get("RDT") ?? []).length === 0;

  const edgeLabelsPreferred = has34Front ? EDGE_LABELS_3_4 : EDGE_LABELS_4_3;
  const edgeLabelsFallback = has34Front ? EDGE_LABELS_4_3 : EDGE_LABELS_3_4;
  const idlPool = has34Front ? IDL_LABELS_3_4 : IDL_LABELS_4_3;
  const lbPool = has34Front ? LB_LABELS_3_4 : LB_LABELS_4_3;

  // D-line — pick 2 EDGE then 2 iDL, ordered EDGE / iDL / iDL / EDGE
  // (left → right).
  const edgePicks = pickTopNAcross(
    new Set(edgeLabelsPreferred),
    2,
    taken,
  );
  for (const p of edgePicks) taken.add(p.player_id);
  // Fall back to the other front's edge labels if we couldn't fill 2 from
  // the preferred pool (e.g. a 4-3 team that only listed one DE depth=1).
  if (edgePicks.length < 2) {
    const more = pickTopNAcross(
      new Set(edgeLabelsFallback),
      2 - edgePicks.length,
      taken,
    );
    for (const p of more) taken.add(p.player_id);
    edgePicks.push(...more);
  }
  const idlPicks = pickTopNAcross(idlPool, 2, taken);
  for (const p of idlPicks) taken.add(p.player_id);

  const dlOrdered: { row: RawLineupRow; kind: "EDGE" | "iDL" }[] = [];
  if (edgePicks[0]) dlOrdered.push({ row: edgePicks[0], kind: "EDGE" });
  if (idlPicks[0]) dlOrdered.push({ row: idlPicks[0], kind: "iDL" });
  if (idlPicks[1]) dlOrdered.push({ row: idlPicks[1], kind: "iDL" });
  if (edgePicks[1]) dlOrdered.push({ row: edgePicks[1], kind: "EDGE" });
  const dl: LineupSlot[] = dlOrdered.map(({ row: r, kind }) => ({
    slot: kind,
    raw_position: r.position,
    depth_order: r.depth_order,
    player_id: r.player_id,
    full_name: r.full_name,
    composite_grade: r.composite_grade === null ? null : Number(r.composite_grade),
    qualified: r.qualified,
    grading_position: r.grading_position,
    grade_season: r.grade_season === null ? null : Number(r.grade_season),
  }));

  // LBs — 2 if we already have a slot CB on the field (nickel = 5 DBs +
  // 6 front), otherwise 3 (base defense = 4 DBs + 7 front). Either way
  // total defense = 11.
  const lbCount = slot_cb ? 2 : 3;
  const lbPicks = pickTopNAcross(lbPool, lbCount, taken);
  for (const p of lbPicks) taken.add(p.player_id);
  const lb: LineupSlot[] = lbPicks.map((r) => ({
    slot: "LB",
    raw_position: r.position,
    depth_order: r.depth_order,
    player_id: r.player_id,
    full_name: r.full_name,
    composite_grade: r.composite_grade === null ? null : Number(r.composite_grade),
    qualified: r.qualified,
    grading_position: r.grading_position,
    grade_season: r.grade_season === null ? null : Number(r.grade_season),
  }));

  // --- Special teams ---
  // nflverse depth charts sometimes omit K/P entirely for certain
  // team-seasons (BAL/CAR/MIN/SF in 2025 are missing P, for example).
  // Fall back to player_seasons + the player's listed position so the
  // lineup still shows a specialist.
  let k = toSlot(
    "K",
    (grouped.get("K") ?? [])[0] ?? (grouped.get("PK") ?? [])[0],
  );
  let p = toSlot("P", (grouped.get("P") ?? [])[0]);

  if (!k || !p) {
    const fallbacks = await sql<{
      position: string;
      player_id: number;
      full_name: string;
      composite_grade: number | null;
      qualified: boolean | null;
      grade_season: number | null;
    }[]>`
      (
        SELECT 'K' AS position, p.player_id, p.full_name,
               sg.composite_grade, sg.qualified, sg.season AS grade_season
        FROM player_seasons ps
        JOIN teams t   ON t.team_id   = ps.team_id
        JOIN players p ON p.player_id = ps.player_id
        LEFT JOIN LATERAL (
          SELECT composite_grade, qualified, season
          FROM season_grades sg2
          WHERE sg2.player_id = p.player_id
            AND sg2.season   <= ps.season
            AND sg2.position  = 'K'
          ORDER BY
            (CASE WHEN sg2.season = ps.season THEN 0 ELSE 1 END) ASC,
            sg2.season DESC
          LIMIT 1
        ) sg ON TRUE
        WHERE t.abbr = ${teamAbbr}
          AND ps.season = ${season}
          AND p.position = 'K'
        ORDER BY ps.snaps_special DESC NULLS LAST
        LIMIT 1
      )
      UNION ALL
      (
        SELECT 'P' AS position, p.player_id, p.full_name,
               sg.composite_grade, sg.qualified, sg.season AS grade_season
        FROM player_seasons ps
        JOIN teams t   ON t.team_id   = ps.team_id
        JOIN players p ON p.player_id = ps.player_id
        LEFT JOIN LATERAL (
          SELECT composite_grade, qualified, season
          FROM season_grades sg2
          WHERE sg2.player_id = p.player_id
            AND sg2.season   <= ps.season
            AND sg2.position  = 'P'
          ORDER BY
            (CASE WHEN sg2.season = ps.season THEN 0 ELSE 1 END) ASC,
            sg2.season DESC
          LIMIT 1
        ) sg ON TRUE
        WHERE t.abbr = ${teamAbbr}
          AND ps.season = ${season}
          AND p.position = 'P'
        ORDER BY ps.snaps_special DESC NULLS LAST
        LIMIT 1
      )
    `;
    for (const r of fallbacks) {
      const slot: LineupSlot = {
        slot: r.position,
        raw_position: null,
        depth_order: null,
        player_id: Number(r.player_id),
        full_name: r.full_name,
        composite_grade:
          r.composite_grade === null ? null : Number(r.composite_grade),
        qualified: r.qualified,
        grading_position: r.position,
        grade_season: r.grade_season === null ? null : Number(r.grade_season),
      };
      if (r.position === "K" && !k) k = slot;
      if (r.position === "P" && !p) p = slot;
    }
  }

  return {
    qb,
    rb,
    wr1,
    wr2,
    slot_wr,
    te,
    ol_starters,
    ol_team_grade: ol_team_grade === null ? null : Number(ol_team_grade),
    ol_team_qualified,
    dl,
    lb,
    cb1,
    cb2,
    slot_cb,
    fs,
    ss,
    k,
    p,
  };
}

export const getTeamLineup = unstable_cache(_getTeamLineup, ["team-lineup"], {
  revalidate: 3600,
});

/**
 * Positions with graded rows for at least one season. Used by the UI to
 * decide what position filters to show.
 *
 * Includes "OL" if team_ol_grades has any rows (OL is team-level, lives
 * in a separate table — see ADR-0025).
 */
export async function getGradedPositions(): Promise<string[]> {
  const [playerRows, teamOlRows] = await Promise.all([
    sql<{ position: string }[]>`
      SELECT DISTINCT position
      FROM season_grades
      ORDER BY position
    `,
    sql<{ has_rows: boolean }[]>`
      SELECT EXISTS(SELECT 1 FROM team_ol_grades) AS has_rows
    `,
  ]);
  const positions = playerRows.map((r) => r.position);
  if (teamOlRows[0]?.has_rows) {
    positions.push("OL");
  }
  return positions;
}

/**
 * Attach a `gradeTrend` array (last N qualifying seasons) to each entry
 * by fetching one batched query for all player_ids on the leaderboard.
 *
 * Used by leaderboards that opt-in to inline sparklines. Currently QB
 * only as a demo — broaden once the visual treatment is approved.
 */
async function _attachGradeTrend(
  entries: LeaderboardEntry[],
  position: string,
  currentSeason: number,
  span: number = 5,
): Promise<LeaderboardEntry[]> {
  const playerIds = entries.map((e) => e.player_id);
  if (playerIds.length === 0) return entries;

  const minSeason = currentSeason - (span - 1);

  const rows = await sql<
    { player_id: number; season: number; composite_grade: number }[]
  >`
    SELECT player_id, season, composite_grade
    FROM season_grades
    WHERE position = ${position}
      AND player_id = ANY(${playerIds})
      AND season BETWEEN ${minSeason} AND ${currentSeason}
    ORDER BY player_id, season ASC
  `;

  const trendByPlayer = new Map<number, { season: number; grade: number }[]>();
  for (const r of rows) {
    const list = trendByPlayer.get(r.player_id) ?? [];
    list.push({ season: Number(r.season), grade: Number(r.composite_grade) });
    trendByPlayer.set(r.player_id, list);
  }

  return entries.map((e) => ({
    ...e,
    gradeTrend: trendByPlayer.get(e.player_id) ?? [],
  }));
}

/**
 * OL counterpart to {@link _attachGradeTrend}. OL is team-graded so the
 * source table is `team_ol_grades` (keyed by team_id, not player_id),
 * and the LeaderboardEntry's `player_id` field already holds team_id
 * per ADR-0025 — that's how the rest of the table machinery treats OL
 * rows as if they were players.
 */
async function _attachTeamOlGradeTrend(
  entries: LeaderboardEntry[],
  currentSeason: number,
  span: number = 5,
): Promise<LeaderboardEntry[]> {
  const teamIds = entries.map((e) => e.player_id);
  if (teamIds.length === 0) return entries;

  const minSeason = currentSeason - (span - 1);

  const rows = await sql<
    { team_id: number; season: number; composite_grade: number }[]
  >`
    SELECT team_id, season, composite_grade
    FROM team_ol_grades
    WHERE team_id = ANY(${teamIds})
      AND season BETWEEN ${minSeason} AND ${currentSeason}
    ORDER BY team_id, season ASC
  `;

  const trendByTeam = new Map<number, { season: number; grade: number }[]>();
  for (const r of rows) {
    const list = trendByTeam.get(r.team_id) ?? [];
    list.push({ season: Number(r.season), grade: Number(r.composite_grade) });
    trendByTeam.set(r.team_id, list);
  }

  return entries.map((e) => ({
    ...e,
    gradeTrend: trendByTeam.get(e.player_id) ?? [],
  }));
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
  // OL is team-level (ADR-0025). Branch to the team-OL leaderboard path
  // before any of the player-grade queries — different tables entirely
  // (team_ol_grades / team_ol_components, not season_grades / stat_components).
  if (position === "OL") {
    const rows = await sql<LeaderboardEntry[]>`
      SELECT
        g.team_id                              AS player_id,        -- React key reuse
        t.name                                 AS full_name,        -- "Baltimore Ravens"
        'OL'                                   AS position,
        g.season,
        g.composite_grade,
        g.composite_z,
        g.percentile,
        g.qualified,
        g.confidence,
        g.data_tier,
        NULL                                   AS role,
        t.abbr                                 AS team_abbr,
        ts.rushes                              AS n_plays,          -- sample-size column
        ts.dropbacks                           AS n_dropbacks_ol,
        c_ybc.raw_value                        AS ol_yards_before_contact_per_carry,
        c_pp.raw_value                         AS ol_pressure_proxy_per_dropback,
        -- CONTEXT columns (not in formula)
        CASE WHEN COALESCE(ts.rushes, 0) > 0
             THEN ts.rush_yards::float / ts.rushes
             ELSE NULL END                     AS ol_rush_yards_per_carry,
        CASE WHEN COALESCE(ts.dropbacks, 0) > 0
             THEN ts.sacks_allowed::float / ts.dropbacks
             ELSE NULL END                     AS ol_sack_rate,
        ts.sacks_allowed                       AS ol_sacks_allowed,
        CASE WHEN COALESCE(ts.rushes, 0) + COALESCE(ts.dropbacks, 0) > 0
             THEN (COALESCE(ts.false_starts, 0) + COALESCE(ts.holdings, 0))::float
                  / (COALESCE(ts.rushes, 0) + COALESCE(ts.dropbacks, 0))
             ELSE NULL END                     AS ol_penalty_rate
      FROM team_ol_grades g
      JOIN teams t ON t.team_id = g.team_id
      LEFT JOIN team_ol_stats ts
        ON ts.team_id = g.team_id AND ts.season = g.season
      LEFT JOIN team_ol_components c_ybc
        ON c_ybc.team_id = g.team_id AND c_ybc.season = g.season
       AND c_ybc.component_name = 'ol_yards_before_contact_per_carry'
      LEFT JOIN team_ol_components c_pp
        ON c_pp.team_id = g.team_id AND c_pp.season = g.season
       AND c_pp.component_name = 'ol_pressure_proxy_per_dropback'
      WHERE g.season = ${season}
      ORDER BY g.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachTeamOlGradeTrend(entries, season);
  }

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
        sc_succ.raw_value       AS success_rate,
        -- Context columns (box-score volume; NOT in formula)
        qbs.pass_yards          AS qb_pass_yards,
        qbs.pass_tds            AS qb_pass_tds,
        qbs.interceptions       AS qb_interceptions,
        qbs.rush_yards          AS qb_rush_yards,
        qbs.rush_tds            AS qb_rush_tds
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
      LEFT JOIN qb_season_stats qbs
        ON qbs.player_id = sg.player_id
       AND qbs.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'QB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "QB", season);
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
        sc_fumble.raw_value     AS rb_fumble_rate,
        -- Context (NOT in formula)
        sps.rush_yards          AS skill_rush_yards,
        sps.rush_tds            AS skill_rush_tds,
        sps.receptions          AS skill_receptions,
        sps.rec_yards           AS skill_rec_yards,
        sps.rec_tds             AS skill_rec_tds
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
      LEFT JOIN skill_player_season_stats sps
        ON sps.player_id = sg.player_id
       AND sps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'RB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "RB", season);
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
        sc_ball.raw_value       AS drop_rate,
        -- Context (NOT in formula)
        sps.receptions          AS skill_receptions,
        sps.rec_yards           AS skill_rec_yards,
        sps.rec_tds             AS skill_rec_tds
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
      LEFT JOIN skill_player_season_stats sps
        ON sps.player_id = sg.player_id
       AND sps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = ${position}
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, position, season);
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
        sc_pbu.raw_value         AS cb_pbu_rate,
        -- Context (NOT in formula)
        (COALESCE(dps.tackles_solo, 0) + COALESCE(dps.tackle_assists, 0)) AS def_tackles_combined,
        dps.sacks                AS def_sacks,
        dps.tackles_for_loss     AS def_tackles_for_loss,
        dps.interceptions        AS def_interceptions,
        dps.forced_fumbles       AS def_forced_fumbles
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
      LEFT JOIN defensive_player_season_stats dps
        ON dps.player_id = sg.player_id
       AND dps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'CB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "CB", season);
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
        sc_dis.raw_value              AS s_backfield_disruption_per_snap,
        -- Context (NOT in formula)
        (COALESCE(dps.tackles_solo, 0) + COALESCE(dps.tackle_assists, 0)) AS def_tackles_combined,
        dps.sacks                     AS def_sacks,
        dps.tackles_for_loss          AS def_tackles_for_loss,
        dps.interceptions             AS def_interceptions,
        dps.forced_fumbles            AS def_forced_fumbles
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
      LEFT JOIN defensive_player_season_stats dps
        ON dps.player_id = sg.player_id
       AND dps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'S'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "S", season);
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
        sc_miss.raw_value             AS edge_missed_tackle_rate,
        -- Context (NOT in formula)
        (COALESCE(dps.tackles_solo, 0) + COALESCE(dps.tackle_assists, 0)) AS def_tackles_combined,
        dps.sacks                     AS def_sacks,
        dps.tackles_for_loss          AS def_tackles_for_loss,
        dps.interceptions             AS def_interceptions,
        dps.forced_fumbles            AS def_forced_fumbles
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
      LEFT JOIN defensive_player_season_stats dps
        ON dps.player_id = sg.player_id
       AND dps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'EDGE'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "EDGE", season);
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
        sc_prs.raw_value              AS lb_pressure_rate,
        -- Context (NOT in formula)
        (COALESCE(dps.tackles_solo, 0) + COALESCE(dps.tackle_assists, 0)) AS def_tackles_combined,
        dps.sacks                     AS def_sacks,
        dps.tackles_for_loss          AS def_tackles_for_loss,
        dps.interceptions             AS def_interceptions,
        dps.forced_fumbles            AS def_forced_fumbles
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
      LEFT JOIN defensive_player_season_stats dps
        ON dps.player_id = sg.player_id
       AND dps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'LB'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "LB", season);
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
        sc_miss.raw_value             AS idl_missed_tackle_rate,
        -- Context (NOT in formula)
        (COALESCE(dps.tackles_solo, 0) + COALESCE(dps.tackle_assists, 0)) AS def_tackles_combined,
        dps.sacks                     AS def_sacks,
        dps.tackles_for_loss          AS def_tackles_for_loss,
        dps.interceptions             AS def_interceptions,
        dps.forced_fumbles            AS def_forced_fumbles
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
      LEFT JOIN defensive_player_season_stats dps
        ON dps.player_id = sg.player_id
       AND dps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'iDL'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "iDL", season);
  }

  if (position === "K") {
    // K v1.1 (ADR-0023 revised): single formula component is FGOE / att.
    // Context columns (FG%, FG% 40+, XP%, FG long) pulled directly from
    // kicker_stats — they're displayed for reader recognition but NOT part
    // of the grade.
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
        sc_fgoe.sample_size           AS n_fg_att,
        sc_fgoe.raw_value             AS k_fg_over_expected_per_att,
        -- Context columns (not in formula)
        CASE WHEN COALESCE(ks.fg_att, 0) > 0
             THEN ks.fg_made::float / ks.fg_att
             ELSE NULL END            AS k_fg_pct,
        CASE WHEN COALESCE(ks.fg_att_40_49, 0) + COALESCE(ks.fg_att_50_59, 0) + COALESCE(ks.fg_att_60_plus, 0) > 0
             THEN (COALESCE(ks.fg_made_40_49, 0) + COALESCE(ks.fg_made_50_59, 0) + COALESCE(ks.fg_made_60_plus, 0))::float
                  / (COALESCE(ks.fg_att_40_49, 0) + COALESCE(ks.fg_att_50_59, 0) + COALESCE(ks.fg_att_60_plus, 0))
             ELSE NULL END            AS k_fg_pct_40_plus,
        CASE WHEN COALESCE(ks.pat_att, 0) > 0
             THEN ks.pat_made::float / ks.pat_att
             ELSE NULL END            AS k_pat_pct,
        ks.fg_long                    AS k_fg_long
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      LEFT JOIN stat_components sc_fgoe
        ON sc_fgoe.player_id = sg.player_id
       AND sc_fgoe.season = sg.season
       AND sc_fgoe.component_name = 'k_fg_over_expected_per_att'
      LEFT JOIN kicker_stats ks
        ON ks.player_id = sg.player_id AND ks.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'K'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "K", season);
  }

  if (position === "P") {
    // P v1.1 (ADR-0024 revised): formula = net_avg + inside_20_rate.
    // Context columns (gross_avg, blocked_rate, long, touchback_rate) pulled
    // from punter_stats — displayed but NOT scored. Block% was in v1's
    // formula but removed in v1.1 (audit YoY/validity near zero, and most
    // blocks are snap/protection failures rather than punter skill).
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
        sc_net.sample_size            AS n_punts,
        sc_net.raw_value              AS p_net_avg,
        sc_i20.raw_value              AS p_inside_20_rate,
        -- Context columns (not in formula)
        CASE WHEN COALESCE(ps.punts, 0) > 0
             THEN ps.blocked::float / ps.punts
             ELSE NULL END            AS p_blocked_rate,
        CASE WHEN COALESCE(ps.punts, 0) > 0
             THEN ps.gross_yards::float / ps.punts
             ELSE NULL END            AS p_gross_avg,
        ps.long_punt                  AS p_long_punt,
        CASE WHEN COALESCE(ps.punts, 0) > 0
             THEN ps.touchbacks::float / ps.punts
             ELSE NULL END            AS p_touchback_rate
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons psn
        ON psn.player_id = sg.player_id AND psn.season = sg.season
      LEFT JOIN teams t ON t.team_id = psn.team_id
      LEFT JOIN stat_components sc_net
        ON sc_net.player_id = sg.player_id
       AND sc_net.season = sg.season
       AND sc_net.component_name = 'p_net_avg'
      LEFT JOIN stat_components sc_i20
        ON sc_i20.player_id = sg.player_id
       AND sc_i20.season = sg.season
       AND sc_i20.component_name = 'p_inside_20_rate'
      LEFT JOIN punter_stats ps
        ON ps.player_id = sg.player_id AND ps.season = sg.season
      WHERE sg.season = ${season}
        AND sg.position = 'P'
      ORDER BY sg.qualified DESC, sg.composite_grade DESC
    `;
    const entries = rows.map(coerceLeaderboardEntry);
    return await _attachGradeTrend(entries, "P", season);
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
  const entries = rows.map(coerceLeaderboardEntry);
  return await _attachGradeTrend(entries, position, season);
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
    qb_pass_yards: coerceNullableInt(row.qb_pass_yards),
    qb_pass_tds: coerceNullableInt(row.qb_pass_tds),
    qb_interceptions: coerceNullableInt(row.qb_interceptions),
    qb_rush_yards: coerceNullableInt(row.qb_rush_yards),
    qb_rush_tds: coerceNullableInt(row.qb_rush_tds),
    // RB-only
    n_touches: coerceNullableInt(row.n_touches),
    rb_ryoe_per_attempt: coerceNullableNumber(row.rb_ryoe_per_attempt),
    rb_rush_epa_per_attempt: coerceNullableNumber(row.rb_rush_epa_per_attempt),
    rb_rush_success_rate: coerceNullableNumber(row.rb_rush_success_rate),
    rb_yac_over_expected_per_rec: coerceNullableNumber(row.rb_yac_over_expected_per_rec),
    rb_yards_after_contact_per_carry: coerceNullableNumber(row.rb_yards_after_contact_per_carry),
    rb_fumble_rate: coerceNullableNumber(row.rb_fumble_rate),
    // Shared skill-position CONTEXT (RB/WR/TE box-score volume; not in formula)
    skill_rush_yards: coerceNullableInt(row.skill_rush_yards),
    skill_rush_tds: coerceNullableInt(row.skill_rush_tds),
    skill_receptions: coerceNullableInt(row.skill_receptions),
    skill_rec_yards: coerceNullableInt(row.skill_rec_yards),
    skill_rec_tds: coerceNullableInt(row.skill_rec_tds),
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
    // Shared defensive CONTEXT (CB/S/EDGE/iDL/LB box-score volume; not in formula)
    def_tackles_combined: coerceNullableInt(row.def_tackles_combined),
    def_sacks: coerceNullableNumber(row.def_sacks),
    def_tackles_for_loss: coerceNullableNumber(row.def_tackles_for_loss),
    def_interceptions: coerceNullableInt(row.def_interceptions),
    def_forced_fumbles: coerceNullableInt(row.def_forced_fumbles),
    // K-only
    n_fg_att: coerceNullableInt(row.n_fg_att),
    k_fg_over_expected_per_att: coerceNullableNumber(row.k_fg_over_expected_per_att),
    k_fg_pct: coerceNullableNumber(row.k_fg_pct),
    k_fg_pct_40_plus: coerceNullableNumber(row.k_fg_pct_40_plus),
    k_pat_pct: coerceNullableNumber(row.k_pat_pct),
    k_fg_long: coerceNullableNumber(row.k_fg_long),
    // P-only
    n_punts: coerceNullableInt(row.n_punts),
    p_net_avg: coerceNullableNumber(row.p_net_avg),
    p_inside_20_rate: coerceNullableNumber(row.p_inside_20_rate),
    p_blocked_rate: coerceNullableNumber(row.p_blocked_rate),
    p_gross_avg: coerceNullableNumber(row.p_gross_avg),
    p_long_punt: coerceNullableNumber(row.p_long_punt),
    p_touchback_rate: coerceNullableNumber(row.p_touchback_rate),
    // OL-only (team-level, ADR-0025)
    n_plays: coerceNullableInt(row.n_plays),
    n_dropbacks_ol: coerceNullableInt(row.n_dropbacks_ol),
    ol_yards_before_contact_per_carry: coerceNullableNumber(row.ol_yards_before_contact_per_carry),
    ol_pressure_proxy_per_dropback: coerceNullableNumber(row.ol_pressure_proxy_per_dropback),
    ol_rush_yards_per_carry: coerceNullableNumber(row.ol_rush_yards_per_carry),
    ol_sack_rate: coerceNullableNumber(row.ol_sack_rate),
    ol_sacks_allowed: coerceNullableInt(row.ol_sacks_allowed),
    ol_penalty_rate: coerceNullableNumber(row.ol_penalty_rate),
    // Empty by default; leaderboard branches that opt in (currently QB
    // only) will populate this via _attachGradeTrend.
    gradeTrend: [],
  };
}
