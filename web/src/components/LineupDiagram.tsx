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
export function LineupDiagram({ lineup }: { lineup: TeamLineup }) {
  return (
    <div>
      <FormationDiagram lineup={lineup} />
      <MobileLineupList lineup={lineup} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Desktop: absolutely-positioned cards on a field-shaped container.
// ---------------------------------------------------------------------------

function FormationDiagram({ lineup }: { lineup: TeamLineup }) {
  return (
    <div className="hidden md:block">
      <div className="relative aspect-[5/2] w-full overflow-hidden rounded-lg border border-neutral-800 bg-gradient-to-b from-[#0e1714] via-[#0b110f] to-[#0e1714]">
        {/* Faint center line — line of scrimmage. */}
        <div
          aria-hidden
          className="absolute left-0 right-0 top-1/2 h-px bg-neutral-700/40"
        />

        {/* Defense (top half) ----------------------------------------- */}
        {/* Safeties — deep zone. */}
        <Card slot={lineup.fs} x={38} y={9} />
        <Card slot={lineup.ss} x={62} y={9} />

        {/* Linebackers — second level; 2 in nickel, 3 in base. */}
        {lineup.lb.map((s, i) => {
          const xs =
            lineup.lb.length === 3
              ? [33, 50, 67]
              : lineup.lb.length === 2
                ? [40, 60]
                : [50];
          return <Card key={`lb-${i}`} slot={s} x={xs[i] ?? 50} y={29} />;
        })}

        {/* Slot CB — between LB level and the line, when present. */}
        <Card slot={lineup.slot_cb} x={26} y={36} />

        {/* D-line + outside corners on the line of scrimmage. CBs sit
            at the same depth as the DL but wide (where the WRs across
            from them line up). DL is 4 across in the middle. */}
        <Card slot={lineup.cb1} x={8} y={44} />
        {lineup.dl.map((s, i) => {
          const xs =
            lineup.dl.length === 4
              ? [29, 42, 58, 71]
              : lineup.dl.length === 3
                ? [35, 50, 65]
                : [50];
          return <Card key={`dl-${i}`} slot={s} x={xs[i] ?? 50} y={44} />;
        })}
        <Card slot={lineup.cb2} x={92} y={44} />

        {/* Offense (bottom half) -------------------------------------- */}
        {/* WR / Slot / TE / WR flanks — outside flanks pushed wider so
            the OL wide card fits cleanly between Slot and TE. */}
        <Card slot={lineup.wr1} x={7} y={62} />
        <Card slot={lineup.slot_wr} x={20} y={64} />
        <Card slot={lineup.te} x={80} y={62} />
        <Card slot={lineup.wr2} x={93} y={62} />

        {/* OL — single wide card between the receivers. */}
        <OLCard lineup={lineup} />

        {/* QB + RB stacked behind center. */}
        <Card slot={lineup.qb} x={50} y={82} />
        <Card slot={lineup.rb} x={50} y={93} />
      </div>

      {/* Special teams strip below the field. */}
      {(lineup.k || lineup.p) && (
        <div className="mt-3 flex flex-wrap items-stretch gap-2">
          <span className="self-center text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
            Special teams
          </span>
          {lineup.k && <InlineCard slot={lineup.k} />}
          {lineup.p && <InlineCard slot={lineup.p} />}
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
}: {
  slot: LineupSlot | null;
  x: number;
  y: number;
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
      <PlayerCardInner slot={slot} />
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
      <div className="flex items-stretch gap-2 rounded-md border border-neutral-700 bg-neutral-900/80 px-2 py-1.5 shadow-md backdrop-blur-sm">
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

function PlayerCardInner({ slot }: { slot: LineupSlot }) {
  const dim = slot.qualified === false;
  return (
    <div className="rounded-md border border-neutral-700 bg-neutral-900/80 px-1.5 py-1 text-center shadow-md backdrop-blur-sm">
      <div className="text-[9px] font-semibold uppercase tracking-wider text-neutral-500">
        {slot.slot}
      </div>
      {slot.player_id ? (
        <Link
          href={{ pathname: `/players/${slot.player_id}` }}
          className="block truncate text-[11px] font-medium text-neutral-100 hover:text-white hover:underline"
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
          >
            {slot.composite_grade.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
}

function InlineCard({ slot }: { slot: LineupSlot }) {
  return (
    <div className="w-24">
      <PlayerCardInner slot={slot} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile: stacked compact list grouped by side of ball.
// ---------------------------------------------------------------------------

function MobileLineupList({ lineup }: { lineup: TeamLineup }) {
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
      <MobileSection title="Offense" rows={offenseRows} />

      {/* OL row — single bar on mobile too */}
      <MobileOLRow lineup={lineup} />

      <MobileSection title="Defense" rows={defenseRows} />
      <MobileSection title="Special teams" rows={stRows} />
    </div>
  );
}

function MobileSection({
  title,
  rows,
}: {
  title: string;
  rows: { slot: string; data: LineupSlot | null }[];
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
          />
        ))}
      </div>
    </div>
  );
}

function MobileRow({ slot, data }: { slot: string; data: LineupSlot }) {
  const dim = data.qualified === false;
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
        {slot}
      </span>
      <div className="min-w-0 flex-1">
        {data.player_id ? (
          <Link
            href={{ pathname: `/players/${data.player_id}` }}
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
        >
          {data.composite_grade.toFixed(1)}
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
