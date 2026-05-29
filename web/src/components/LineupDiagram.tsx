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
      {/* `containerType: inline-size` turns the field into a CSS
          container-query container — child elements can size with
          `cqi` units (1cqi = 1% of the field's inline size). That lets
          card text + heights scale proportionally with the field at
          every viewport, so the formation looks identical (just
          larger or smaller) instead of cards staying fixed while the
          field shrinks around them. Without this, narrow viewports
          end up with normally-sized cards on a tiny field — vertical
          neighbors overlap. */}
      <div
        className="relative aspect-[5/2] w-full overflow-hidden rounded-lg border border-neutral-800 bg-gradient-to-b from-[#0e1714] via-[#0b110f] to-[#0e1714]"
        style={{ containerType: "inline-size" }}
      >
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

        {/* Row-based layout: each Row is a non-overlapping horizontal
            band of the field with a fixed top + height (in % of field).
            Cards inside a row are positioned by x only and centered
            vertically — they cannot collide with cards in other rows
            because rows don't overlap. Card widths are tuned so the
            tightest in-row pair (DL at 29/42, 13% apart) always has
            ≥3.5% clearance. Result: zero overlap at any field width.

            Row depth allocation (top → bottom): defense fills 0-50%
            (3 rows), offense fills 52-100% (3 rows). Line of scrimmage
            sits in the 2% gap between row 3 (DL/CBs) and row 4
            (WR/OL). Gaps between adjacent rows give cards a few px of
            breathing room at the smallest viewports. */}

        {/* Defense (top half) ----------------------------------------- */}

        {/* Row 1 — Safeties (deep zone). */}
        <Row top={0} height={14}>
          <Card slot={lineup.fs} x={38} season={season} />
          <Card slot={lineup.ss} x={62} season={season} />
        </Row>

        {/* Row 2 — Linebackers + slot CB. 2 LBs in nickel (with slot
            CB present); 3 LBs in base (no slot CB). Slot CB sits at
            "wide nickel" depth (LB level), x=17 to clear the leftmost
            DL in row 3. */}
        <Row top={16} height={18}>
          <Card slot={lineup.slot_cb} x={17} season={season} />
          {lineup.lb.map((s, i) => {
            const xs =
              lineup.lb.length === 3
                ? [33, 50, 67]
                : lineup.lb.length === 2
                  ? [40, 60]
                  : [50];
            return (
              <Card key={`lb-${i}`} slot={s} x={xs[i] ?? 50} season={season} />
            );
          })}
        </Row>

        {/* Row 3 — D-line + outside corners on the line of scrimmage.
            CBs sit wide where the WRs across from them line up; DL is
            4 across in the middle (3 in 3-4 fronts). */}
        <Row top={36} height={14}>
          <Card slot={lineup.cb1} x={8} season={season} />
          {lineup.dl.map((s, i) => {
            const xs =
              lineup.dl.length === 4
                ? [29, 42, 58, 71]
                : lineup.dl.length === 3
                  ? [35, 50, 65]
                  : [50];
            return (
              <Card key={`dl-${i}`} slot={s} x={xs[i] ?? 50} season={season} />
            );
          })}
          <Card slot={lineup.cb2} x={92} season={season} />
        </Row>

        {/* Offense (bottom half) -------------------------------------- */}

        {/* Row 4 — Skill-position flanks (WR/slot/TE) + OL across the
            middle. Outside WRs are pushed wider to clear the OL "wide
            card". Row is slightly taller (16%) to comfortably fit the
            OL card, which has a touch more vertical content. */}
        <Row top={52} height={16}>
          <Card slot={lineup.wr1} x={7} season={season} />
          <Card slot={lineup.slot_wr} x={20} season={season} />
          <OLCard lineup={lineup} />
          <Card slot={lineup.te} x={80} season={season} />
          <Card slot={lineup.wr2} x={93} season={season} />
        </Row>

        {/* Row 5 — QB. Behind center, just past LOS. */}
        <Row top={70} height={14}>
          <Card slot={lineup.qb} x={50} season={season} />
        </Row>

        {/* Row 6 — RB. Deep in the backfield. */}
        <Row top={86} height={14}>
          <Card slot={lineup.rb} x={50} season={season} />
        </Row>
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

// Card width as % of the field. 9.5 leaves at least ~3% horizontal
// clearance between every pair of player cards in the same row at
// every scale — the tightest pair is the DL row at 13% center-to-
// center spacing.
const CARD_WIDTH_PCT = 9.5;

/**
 * Horizontal band on the field. Cards inside use `top: 50%` and are
 * centered vertically within the row. Because rows are absolutely-
 * positioned non-overlapping bands of the field, cards in different
 * rows physically cannot collide vertically — the entire vertical-
 * overlap class of bugs goes away.
 *
 * Math sanity check at the smallest rendered field (md breakpoint =
 * 720px wide × 288px tall, card content ~38px = 13.2% of field
 * height): every adjacent row pair has ≥2% gap (row separation) +
 * ≥0.6% card-to-card clearance once cards are centered within their
 * rows. No overlap, even at the tightest viewport the diagram
 * renders at.
 */
function Row({
  top,
  height,
  children,
}: {
  top: number;
  height: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className="absolute left-0 right-0"
      style={{ top: `${top}%`, height: `${height}%` }}
    >
      {children}
    </div>
  );
}

/**
 * Absolutely-positioned player card. `x` is % of the parent Row (which
 * spans the full field width), so x is effectively % of the field.
 * Cards are centered vertically in their row via `top: 50%`. Returns
 * null when the depth chart didn't supply a player for this slot.
 */
function Card({
  slot,
  x,
  season,
}: {
  slot: LineupSlot | null;
  x: number;
  season: number;
}) {
  if (!slot) return null;
  // No min/max width — the card scales purely as a % of the field, so
  // the whole formation stays proportional. Card text uses `cqi`-based
  // sizing in PlayerCardInner so heights scale too. Together: the
  // formation looks identical at every viewport, just larger or
  // smaller. No fixed pixel constraint can break the proportions.
  return (
    <div
      className="absolute"
      style={{
        left: `${x}%`,
        top: "50%",
        width: `${CARD_WIDTH_PCT}%`,
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
  // OL sits inside Row 4 (skill+OL). `top: 50%` centers it vertically
  // in the row, same convention as the player cards. Width stays at
  // 44% of the field so it spans from ~28% to ~72% — outside the
  // slot_wr × TE x-range, so they never collide.
  return (
    <div
      className="absolute"
      style={{
        left: "50%",
        top: "50%",
        width: "44%",
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
        {/* Grade column. Text sizes match the player cards' cqi-based
            scaling so the OL card grows/shrinks in proportion with
            the rest of the formation. */}
        <div className="flex flex-shrink-0 flex-col items-center justify-center border-r border-neutral-800 pr-2.5">
          <span className="text-[clamp(7px,0.85cqi,9px)] font-semibold uppercase tracking-wider text-neutral-500">
            OL
          </span>
          {grade === null ? (
            <span className="font-mono text-[clamp(11px,1.4cqi,14px)] text-neutral-600">—</span>
          ) : (
            <span
              className={`font-mono text-[clamp(13px,1.75cqi,18px)] font-semibold leading-none ${gradeColor(grade)} ${dim ? "opacity-60" : ""}`}
            >
              {grade.toFixed(1)}
            </span>
          )}
        </div>
        {/* Five-slot starter row */}
        <div className="grid flex-1 grid-cols-5 gap-1 text-center text-[clamp(8px,1cqi,10px)] text-neutral-300">
          {["LT", "LG", "C", "RG", "RT"].map((label) => {
            const starter = lineup.ol_starters.find((s) => s.slot === label);
            return (
              <div key={label} className="min-w-0">
                <div className="text-[clamp(7px,0.85cqi,9px)] uppercase tracking-wider text-neutral-500">
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

  // Whole card is the click target when there's a player to link to.
  // The card body's hover styles (lift + shadow + border brighten)
  // stay attached to the inner `group/card` div so they fire on
  // hover of the Link itself — every visible pixel of the card
  // navigates to the player profile.
  const cardClass =
    "group/card rounded-md border border-neutral-700 bg-neutral-900/85 px-1.5 py-1 text-center backdrop-blur-sm " +
    // Depth: drop shadow + inset top highlight (the 1px white-ish line
    // at the top of the card simulates a light edge — gives an object
    // feel without going skeuomorphic).
    "shadow-[0_4px_12px_-4px_rgba(0,0,0,0.6),inset_0_1px_0_rgba(255,255,255,0.05)] " +
    // Hover lift: card raises 2px, shadow deepens, border brightens.
    "transition-all duration-150 hover:-translate-y-0.5 hover:border-neutral-600 " +
    "hover:shadow-[0_8px_20px_-6px_rgba(0,0,0,0.7),inset_0_1px_0_rgba(255,255,255,0.08)]";

  // Font sizes use `cqi` (1cqi = 1% of the field's inline size) so
  // card text scales with the field, not the viewport. The field is
  // set up as a container-query container in FormationDiagram.
  // `clamp(min, cqi, max)` floors at a readable minimum on narrow
  // fields and caps at the original design size on wide fields.
  // When the inner card is rendered outside the field (e.g.
  // InlineCard in the special-teams strip), `cqi` falls back to 0
  // and clamp resolves to the floor — also readable.
  const body = (
    <>
      <div className="text-[clamp(7px,0.85cqi,9px)] font-semibold uppercase tracking-wider text-neutral-500">
        {slot.slot}
      </div>
      {slot.player_id && slot.slug ? (
        // Chevron fades in on card hover. The Link sits one level up
        // (around the whole card) so this span is just the name
        // display — no click handling here.
        <div className="inline-flex max-w-full items-center gap-0.5 text-[clamp(8px,1.05cqi,11px)] font-medium text-neutral-100 group-hover/card:text-white">
          <span className="truncate">{slot.full_name}</span>
          <span
            aria-hidden
            className="text-[clamp(7px,0.85cqi,9px)] leading-none text-neutral-600 opacity-0 transition-all duration-150 group-hover/card:translate-x-0.5 group-hover/card:text-neutral-300 group-hover/card:opacity-100"
          >
            ›
          </span>
        </div>
      ) : (
        <div className="truncate text-[clamp(8px,1.05cqi,11px)] font-medium text-neutral-500">—</div>
      )}
      <div className="leading-none">
        {slot.composite_grade === null ? (
          <span className="text-[clamp(8px,1.05cqi,11px)] text-neutral-600">—</span>
        ) : (
          <span
            className={`font-mono text-[clamp(10px,1.4cqi,14px)] font-semibold ${gradeColor(slot.composite_grade)} ${dim ? "opacity-60" : ""}`}
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
    </>
  );

  if (slot.player_id && slot.slug) {
    return (
      <Link
        href={{ pathname: `/players/${slot.slug}` }}
        className={`block ${cardClass}`}
      >
        {body}
      </Link>
    );
  }
  return <div className={cardClass}>{body}</div>;
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
            className="group/lnk inline-flex max-w-full items-center gap-1 truncate text-sm font-medium text-neutral-100 hover:text-white"
          >
            <span className="truncate">{data.full_name}</span>
            <span
              aria-hidden
              className="text-xs leading-none text-neutral-600 transition-all duration-150 group-hover/lnk:translate-x-0.5 group-hover/lnk:text-neutral-300"
            >
              ›
            </span>
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
