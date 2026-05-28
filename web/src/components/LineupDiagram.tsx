import Link from "next/link";

import { gradeColor } from "@/lib/grades";
import type { LineupSlot, TeamLineup } from "@/types";

/**
 * Visual lineup of a team's depth-chart starters.
 *
 * Desktop (md+): formation diagram with defense on top, offense on
 * bottom, line of scrimmage in the middle. OL is a single wide card
 * showing the team OL grade (ADR-0025) with the five starter names
 * inside. Kicker + punter sit in a strip below the field.
 *
 * Mobile (<md): the diagram doesn't fit gracefully at narrow widths,
 * so we render a compact stacked list grouped by side of ball.
 */
export function LineupDiagram({
  lineup,
  season,
}: {
  lineup: TeamLineup;
  season: number;
}) {
  return (
    <div>
      <FormationDiagram lineup={lineup} season={season} />
      <MobileLineupList lineup={lineup} season={season} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Desktop: absolutely-positioned cards on a field-shaped container.
// ---------------------------------------------------------------------------

function FormationDiagram({
  lineup,
  season,
}: {
  lineup: TeamLineup;
  season: number;
}) {
  // Formation label: derived from what we placed on the field. Slot CB
  // means we drew nickel personnel (5 DBs, 2 LBs); otherwise it's base
  // (4 DBs, 3 LBs). DL is always 4 in this diagram.
  const formationLabel = lineup.slot_cb ? "4-2-5 Nickel" : "4-3 Base";

  return (
    <div className="hidden md:block">
      <div className="relative aspect-[5/2] w-full overflow-hidden rounded-lg border border-neutral-800 bg-gradient-to-b from-[#0e1714] via-[#0b110f] to-[#0e1714]">
        {/* Faint yard-line hairlines — 10/30/70/90% with the line of
            scrimmage at 50%. Very low opacity so they read as "this is a
            field" without imitating a literal football graphic. */}
        <div
          aria-hidden
          className="absolute left-0 right-0 top-[10%] h-px bg-neutral-700/15"
        />
        <div
          aria-hidden
          className="absolute left-0 right-0 top-[30%] h-px bg-neutral-700/15"
        />
        {/* Line of scrimmage — slightly stronger. */}
        <div
          aria-hidden
          className="absolute left-0 right-0 top-1/2 h-px bg-neutral-700/40"
        />
        <div
          aria-hidden
          className="absolute left-0 right-0 top-[70%] h-px bg-neutral-700/15"
        />
        <div
          aria-hidden
          className="absolute left-0 right-0 top-[90%] h-px bg-neutral-700/15"
        />

        {/* Formation type — corner annotation, low contrast on purpose. */}
        <div
          aria-hidden
          className="pointer-events-none absolute right-3 top-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-neutral-600"
        >
          {formationLabel}
        </div>

        {/* Defense (top half) ----------------------------------------- */}
        {/* Safeties — deep zone. */}
        <Card slot={lineup.fs} x={38} y={9} season={season} />
        <Card slot={lineup.ss} x={62} y={9} season={season} />

        {/* Linebackers — second level; 2 in nickel, 3 in base. */}
        {lineup.lb.map((s, i) => {
          const xs =
            lineup.lb.length === 3
              ? [33, 50, 67]
              : lineup.lb.length === 2
                ? [40, 60]
                : [50];
          return (
            <Card key={`lb-${i}`} slot={s} x={xs[i] ?? 50} y={29} season={season} />
          );
        })}

        {/* Slot CB — lined up over the slot WR (x≈20), between LB level
            and the line of scrimmage. */}
        <Card slot={lineup.slot_cb} x={20} y={36} season={season} />

        {/* D-line + outside corners on the line of scrimmage. CBs sit
            at the same depth as the DL but wide (where the WRs across
            from them line up). DL is 4 across in the middle. */}
        <Card slot={lineup.cb1} x={8} y={44} season={season} />
        {lineup.dl.map((s, i) => {
          const xs =
            lineup.dl.length === 4
              ? [29, 42, 58, 71]
              : lineup.dl.length === 3
                ? [35, 50, 65]
                : [50];
          return (
            <Card key={`dl-${i}`} slot={s} x={xs[i] ?? 50} y={44} season={season} />
          );
        })}
        <Card slot={lineup.cb2} x={92} y={44} season={season} />

        {/* Offense (bottom half) -------------------------------------- */}
        {/* WR / Slot / TE / WR flanks — outside flanks pushed wider so
            the OL wide card fits cleanly between Slot and TE. */}
        <Card slot={lineup.wr1} x={7} y={62} season={season} />
        <Card slot={lineup.slot_wr} x={20} y={64} season={season} />
        <Card slot={lineup.te} x={80} y={62} season={season} />
        <Card slot={lineup.wr2} x={93} y={62} season={season} />

        {/* OL — single wide card between the receivers. */}
        <OLCard lineup={lineup} />

        {/* QB + RB stacked behind center. QB nudged up so it doesn't
            butt against the RB card directly below. */}
        <Card slot={lineup.qb} x={50} y={78} season={season} />
        <Card slot={lineup.rb} x={50} y={93} season={season} />
      </div>

      {/* Special teams strip below the field. */}
      {(lineup.k || lineup.p) && (
        <div className="mt-3 flex flex-wrap items-stretch gap-2">
          <span className="self-center text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
            Special teams
          </span>
          {lineup.k && <InlineCard slot={lineup.k} season={season} />}
          {lineup.p && <InlineCard slot={lineup.p} season={season} />}
        </div>
      )}
    </div>
  );
}

const CARD_WIDTH_PCT = 11;

/**
 * Absolutely-positioned player card. x/y are % of the container; the
 * card is translated so x/y refer to its center. Returns null when
 * the depth chart didn't supply a player for this slot.
 */
function Card({
  slot,
  x,
  y,
  season,
}: {
  slot: LineupSlot | null;
  x: number;
  y: number;
  season: number;
}) {
  if (!slot) return null;
  return (
    <div
      className="absolute"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        width: `${CARD_WIDTH_PCT}%`,
        minWidth: 86,
        maxWidth: 120,
        transform: "translate(-50%, -50%)",
      }}
    >
      <PlayerCardInner slot={slot} season={season} />
    </div>
  );
}

/**
 * Wide OL card: single rectangle in the middle of the offense row.
 * Grade chip on the left, five starter slots on the right.
 * No per-player grade — OL is graded as a unit (ADR-0025).
 */
function OLCard({ lineup }: { lineup: TeamLineup }) {
  const grade = lineup.ol_team_grade;
  const dim = lineup.ol_team_qualified === false;
  return (
    <div
      className="absolute"
      style={{
        left: "50%",
        top: "63%",
        width: "44%",
        maxWidth: 540,
        transform: "translate(-50%, -50%)",
      }}
    >
      <div
        className={
          "flex items-stretch gap-2 rounded-md border border-neutral-700 bg-neutral-900/85 px-2 py-1.5 backdrop-blur-sm " +
          "shadow-[0_4px_12px_-4px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.05)] " +
          "transition-all duration-150 hover:-translate-y-0.5 hover:border-neutral-600 " +
          "hover:shadow-[0_8px_20px_-6px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.08)]"
        }
      >
        {/* Grade column */}
        <div className="flex flex-shrink-0 flex-col items-center justify-center border-r border-neutral-800 pr-2.5">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-neutral-500">
            OL
          </span>
          {grade === null ? (
            <span className="font-mono text-sm text-neutral-600">—</span>
          ) : (
            <span
              className={`font-mono text-lg font-semibold leading-none ${gradeColor(grade)} ${dim ? "opacity-60" : ""}`}
            >
              {grade.toFixed(1)}
            </span>
          )}
        </div>
        {/* Five-slot starter row */}
        <div className="grid flex-1 grid-cols-5 gap-1 text-center text-[10px] text-neutral-300">
          {["LT", "LG", "C", "RG", "RT"].map((label) => {
            const starter = lineup.ol_starters.find((s) => s.slot === label);
            return (
              <div key={label} className="min-w-0">
                <div className="text-[9px] uppercase tracking-wider text-neutral-500">
                  {label}
                </div>
                <div className="truncate font-medium text-neutral-200">
                  {starter ? lastName(starter.full_name) : "—"}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PlayerCardInner({
  slot,
  season,
}: {
  slot: LineupSlot;
  season: number;
}) {
  const dim = slot.qualified === false;
  // Grade from a prior season: player didn't have a current-season grade
  // (rookie this year, mid-season callup, in-progress season). We still
  // show the prior grade — fades to "*" with a hover tooltip so the
  // reader knows it's stale.
  const isPriorGrade =
    slot.composite_grade !== null &&
    slot.grade_season !== null &&
    slot.grade_season !== season;
  return (
    <div
      className={
        "group/card rounded-md border border-neutral-700 bg-neutral-900/85 px-1.5 py-1 text-center backdrop-blur-sm " +
        // Depth: drop shadow + inset top highlight (the 1px white-ish line
        // at the top of the card simulates a light edge — gives an object
        // feel without going skeuomorphic).
        "shadow-[0_4px_12px_-4px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.05)] " +
        // Hover lift: card raises 2px, shadow deepens, border brightens.
        // Subtle but tactile — clearly responds to the cursor.
        "transition-all duration-150 hover:-translate-y-0.5 hover:border-neutral-600 " +
        "hover:shadow-[0_8px_20px_-6px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.08)]"
      }
    >
      <div className="text-[9px] font-semibold uppercase tracking-wider text-neutral-500">
        {slot.slot}
      </div>
      {slot.player_id && slot.slug ? (
        <Link
          href={{ pathname: `/players/${slot.slug}` }}
          className="block truncate text-[11px] font-medium text-neutral-100 group-hover/card:text-white"
        >
          {slot.full_name}
        </Link>
      ) : (
        <div className="truncate text-[11px] font-medium text-neutral-500">—</div>
      )}
      <div className="leading-none">
        {slot.composite_grade === null ? (
          <span className="text-[11px] text-neutral-600">—</span>
        ) : (
          <span
            className={`font-mono text-sm font-semibold ${gradeColor(slot.composite_grade)} ${dim ? "opacity-60" : ""}`}
            title={
              isPriorGrade
                ? `${slot.grade_season} grade — not graded yet in ${season}`
                : undefined
            }
          >
            {slot.composite_grade.toFixed(1)}
            {isPriorGrade && (
              <span className="text-neutral-500" aria-hidden>
                *
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}

function InlineCard({ slot, season }: { slot: LineupSlot; season: number }) {
  return (
    <div className="w-24">
      <PlayerCardInner slot={slot} season={season} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile: stacked compact list grouped by side of ball.
// ---------------------------------------------------------------------------

function MobileLineupList({
  lineup,
  season,
}: {
  lineup: TeamLineup;
  season: number;
}) {
  const offenseRows: { slot: string; data: LineupSlot | null }[] = [
    { slot: "QB", data: lineup.qb },
    { slot: "RB", data: lineup.rb },
    { slot: "WR1", data: lineup.wr1 },
    { slot: "WR2", data: lineup.wr2 },
    { slot: "SLOT", data: lineup.slot_wr },
    { slot: "TE", data: lineup.te },
  ];
  const defenseRows: { slot: string; data: LineupSlot | null }[] = [
    ...lineup.dl.map((s) => ({ slot: s.slot, data: s as LineupSlot | null })),
    ...lineup.lb.map((s) => ({ slot: s.slot, data: s as LineupSlot | null })),
    { slot: "LCB", data: lineup.cb1 },
    { slot: "SLOT CB", data: lineup.slot_cb },
    { slot: "RCB", data: lineup.cb2 },
    { slot: "FS", data: lineup.fs },
    { slot: "SS", data: lineup.ss },
  ];
  const stRows: { slot: string; data: LineupSlot | null }[] = [
    { slot: "K", data: lineup.k },
    { slot: "P", data: lineup.p },
  ];

  return (
    <div className="md:hidden">
      <MobileSection title="Offense" rows={offenseRows} season={season} />

      {/* OL row — single bar on mobile too */}
      <MobileOLRow lineup={lineup} />

      <MobileSection title="Defense" rows={defenseRows} season={season} />
      <MobileSection title="Special teams" rows={stRows} season={season} />
    </div>
  );
}

function MobileSection({
  title,
  rows,
  season,
}: {
  title: string;
  rows: { slot: string; data: LineupSlot | null }[];
  season: number;
}) {
  const filtered = rows.filter((r) => r.data !== null);
  if (filtered.length === 0) return null;
  return (
    <div className="mb-4">
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {title}
      </h3>
      <div className="divide-y divide-neutral-800 overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950">
        {filtered.map((r, i) => (
          <MobileRow
            key={`${r.slot}-${r.data!.player_id ?? i}`}
            slot={r.slot}
            data={r.data!}
            season={season}
          />
        ))}
      </div>
    </div>
  );
}

function MobileRow({
  slot,
  data,
  season,
}: {
  slot: string;
  data: LineupSlot;
  season: number;
}) {
  const dim = data.qualified === false;
  const isPriorGrade =
    data.composite_grade !== null &&
    data.grade_season !== null &&
    data.grade_season !== season;
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {slot}
      </span>
      <div className="min-w-0 flex-1">
        {data.player_id && data.slug ? (
          <Link
            href={{ pathname: `/players/${data.slug}` }}
            className="truncate text-sm font-medium text-neutral-100 hover:text-white hover:underline"
          >
            {data.full_name}
          </Link>
        ) : (
          <span className="text-sm text-neutral-500">—</span>
        )}
      </div>
      {data.composite_grade === null ? (
        <span className="text-sm text-neutral-600">—</span>
      ) : (
        <span
          className={`font-mono text-sm font-semibold ${gradeColor(data.composite_grade)} ${dim ? "opacity-60" : ""}`}
          title={
            isPriorGrade
              ? `${data.grade_season} grade — not graded yet in ${season}`
              : undefined
          }
        >
          {data.composite_grade.toFixed(1)}
          {isPriorGrade && (
            <span className="text-neutral-500" aria-hidden>
              *
            </span>
          )}
        </span>
      )}
    </div>
  );
}

function MobileOLRow({ lineup }: { lineup: TeamLineup }) {
  const grade = lineup.ol_team_grade;
  const dim = lineup.ol_team_qualified === false;
  return (
    <div className="mb-4">
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        Offensive line
      </h3>
      <div className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2.5">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-[11px] text-neutral-500">Team grade</span>
          {grade === null ? (
            <span className="text-sm text-neutral-600">—</span>
          ) : (
            <span
              className={`font-mono text-base font-semibold ${gradeColor(grade)} ${dim ? "opacity-60" : ""}`}
            >
              {grade.toFixed(1)}
            </span>
          )}
        </div>
        <div className="grid grid-cols-5 gap-1 text-center text-[10px]">
          {["LT", "LG", "C", "RG", "RT"].map((label) => {
            const starter = lineup.ol_starters.find((s) => s.slot === label);
            return (
              <div key={label} className="min-w-0">
                <div className="text-[9px] uppercase tracking-wider text-neutral-500">
                  {label}
                </div>
                <div className="truncate font-medium text-neutral-200">
                  {starter ? lastName(starter.full_name) : "—"}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Last name only, for the OL row where the full name doesn't fit. */
function lastName(full: string | null): string {
  if (!full) return "—";
  const parts = full.trim().split(/\s+/);
  return parts[parts.length - 1] ?? full;
}
