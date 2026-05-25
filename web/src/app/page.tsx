import type { Metadata } from "next";

import { InfoDisclosure } from "@/components/InfoDisclosure";
import { LeaderboardTable } from "@/components/LeaderboardTable";
import { PositionPicker } from "@/components/PositionPicker";
import { SeasonPicker } from "@/components/SeasonPicker";
import {
  getGradedPositions,
  getGradedSeasons,
  getLeaderboard,
} from "@/lib/queries";

type SearchParams = Promise<{
  season?: string | string[];
  position?: string | string[];
}>;

type Props = { searchParams: SearchParams };

/**
 * Page title in the browser tab reflects the active season + position so
 * that bookmarks, history, and pinned tabs are self-describing. When the
 * URL omits one or both params we resolve the same defaults the page
 * itself uses (latest season, QB) so the bare landing page still gets
 * a descriptive title rather than just "Grades".
 */
export async function generateMetadata({
  searchParams,
}: Props): Promise<Metadata> {
  const { season: seasonParam, position: positionParam } = await searchParams;
  const seasonRaw = firstOf(seasonParam);
  const positionRaw = firstOf(positionParam);

  let season: number | null = null;
  if (seasonRaw && Number.isFinite(Number(seasonRaw))) {
    season = Number(seasonRaw);
  } else {
    const seasons = await getGradedSeasons();
    season = seasons[0] ?? null;
  }

  const position = positionRaw
    ? (POSITION_ORDER.find((p) => p.toUpperCase() === positionRaw.toUpperCase()) ??
       DEFAULT_POSITION)
    : DEFAULT_POSITION;

  if (season !== null) {
    return { title: `${position} Grades \u2014 ${season}` };
  }
  return { title: `${position} Grades` };
}

// Tabs render in this canonical order (not alphabetical) so QB appears first.
const POSITION_ORDER: readonly string[] = ["QB", "RB", "WR", "TE", "OL", "CB", "S", "EDGE", "iDL", "LB", "K", "P"];
const DEFAULT_POSITION = "QB";

/** Short phrase following "{N} qualified starters · composite of ..." */
const COMPOSITE_BLURB: Record<string, string> = {
  QB: "composite of EPA/dropback, CPOE, and success rate",
  RB: "composite of rushing efficiency (RYOE / EPA / success / yards-after-contact), receiving value, and ball security (yards-after-contact data 2018+)",
  WR: "composite of EPA/target, YAC-over-expected, separation, target earn rate, success rate, and drop rate (2022+; pre-2022 uses v1 formula)",
  TE: "composite of EPA/target, YAC-over-expected, separation, earn rate, and ball security (earn rate dropped for pure blockers — ADR-0016)",
  OL: "TEAM-LEVEL grade: composite of yards-before-contact per carry (run-block) and (sacks + QB hits) per dropback (pass-block). 50/50 split. Data 2018+",
  CB:   "composite of passer rating allowed, YAC/rec allowed, target rate, and PBU rate (data 2018+)",
  S:    "composite of coverage quality (passer rating allowed, target rate, PBU rate) and tackling (tackles/snap, missed tackle rate, backfield disruption) (data 2018+)",
  EDGE: "composite of pressure rate, sack rate, run-stop TFL rate, and missed tackle rate (data 2018+)",
  iDL:  "composite of run-stop TFL rate, pressure rate, sack rate, and missed tackle rate (data 2018+)",
  LB:   "composite of TFL rate, coverage damage (yds/tgt), tackle volume + technique, and coverage playmaking (PBU/INT) (data 2018+)",
  K:    "single-component grade: Field Goal Over Expected per attempt — each kick compared to league baseline make rate for its distance, XPs folded in. Rewards risk-taking, penalizes easy misses (data 2016+)",
  P:    "composite of net average (distance + return prevention) and inside-20 placement rate (data 2016+)",
};

/** Heading + threshold text used for the below-qualification section. */
const LOW_VOLUME_COPY: Record<string, { heading: string; threshold: string }> = {
  QB: {
    heading: "Low-volume passers",
    threshold:
      "Fewer than 200 qualifying dropbacks. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  RB: {
    heading: "Low-volume backs",
    threshold:
      "Fewer than 120 touches. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  WR: {
    heading: "Low-volume receivers",
    threshold:
      "Fewer than 50 targets. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  TE: {
    heading: "Low-volume tight ends",
    threshold:
      "Fewer than 40 targets. Grades still computed on the same 0-100 scale but treat them as noisy. Pure blocking TEs (<15 targets) are not graded at all.",
  },
  OL: {
    // OL is team-level — every team that played a season is graded. No
    // "low-volume" cohort. The collapsed section never renders for OL
    // because no rows fail qualification.
    heading: "Low-volume offensive lines",
    threshold:
      "All 32 teams are graded each season — no qualification threshold for the OL unit.",
  },
  CB: {
    heading: "Low-volume corners",
    threshold:
      "Fewer than 30 targets. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  S: {
    heading: "Low-volume safeties",
    threshold:
      "Fewer than 400 defensive snaps. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  EDGE: {
    heading: "Low-volume edge rushers",
    threshold:
      "Fewer than 400 defensive snaps. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  iDL: {
    heading: "Low-volume interior linemen",
    threshold:
      "Fewer than 400 defensive snaps. Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  LB: {
    heading: "Low-volume / rotational linebackers",
    threshold:
      "Fewer than 600 defensive snaps (LB threshold raised to suppress rotational specialists whose per-snap rates outpace every-down LBs). Grades still computed on the same 0-100 scale but treat them as noisy.",
  },
  K: {
    heading: "Low-volume kickers",
    threshold:
      "Fewer than 20 FG attempts. Grades still computed on the same 0-100 scale but treat them as noisy (rookies, mid-season callups, kickers in heavy committees).",
  },
  P: {
    heading: "Low-volume punters",
    threshold:
      "Fewer than 40 punts. Grades still computed on the same 0-100 scale but treat them as noisy (rookies, mid-season callups, punters who lost their job).",
  },
};

/** Noun used in the "{N} qualified X" header under the title. */
const QUALIFIED_NOUN: Record<string, { singular: string; plural: string }> = {
  QB: { singular: "qualified starter", plural: "qualified starters" },
  RB: { singular: "qualified back", plural: "qualified backs" },
  WR: { singular: "qualified receiver", plural: "qualified receivers" },
  TE: { singular: "qualified tight end", plural: "qualified tight ends" },
  OL: { singular: "graded OL unit", plural: "graded OL units" },
  CB:   { singular: "qualified corner",       plural: "qualified corners" },
  S:    { singular: "qualified safety",       plural: "qualified safeties" },
  EDGE: { singular: "qualified edge rusher",  plural: "qualified edge rushers" },
  iDL:  { singular: "qualified interior lineman", plural: "qualified interior linemen" },
  LB:   { singular: "qualified linebacker",       plural: "qualified linebackers" },
  K:    { singular: "qualified kicker",           plural: "qualified kickers" },
  P:    { singular: "qualified punter",           plural: "qualified punters" },
};

export default async function HomePage({ searchParams }: Props) {
  const [seasons, gradedPositions] = await Promise.all([
    getGradedSeasons(),
    getGradedPositions(),
  ]);
  if (seasons.length === 0) {
    return <EmptyState />;
  }

  const { season: seasonParam, position: positionParam } = await searchParams;

  const requestedSeason = firstOf(seasonParam);
  const activeSeason =
    requestedSeason && seasons.includes(Number(requestedSeason))
      ? Number(requestedSeason)
      : seasons[0];

  // Only accept positions that (a) are in our canonical tab order and
  // (b) have at least one row in season_grades. That way we never show a
  // tab that would render an empty table — if, say, TE hasn't been graded
  // yet for any season, we omit it entirely.
  const availablePositions = POSITION_ORDER.filter((p) =>
    gradedPositions.includes(p),
  );
  const pickerPositions =
    availablePositions.length > 0 ? availablePositions : [DEFAULT_POSITION];

  const requestedPositionRaw = firstOf(positionParam);
  // Match case-insensitively so the URL can be ?position=idl or ?position=iDL,
  // but always resolve to the canonical mixed-case form from POSITION_ORDER
  // (e.g. "iDL"). Otherwise position codes like iDL never match.
  const requestedPosition = requestedPositionRaw
    ? pickerPositions.find(
        (p) => p.toUpperCase() === requestedPositionRaw.toUpperCase(),
      )
    : undefined;
  const activePosition =
    requestedPosition ??
    (pickerPositions.includes(DEFAULT_POSITION)
      ? DEFAULT_POSITION
      : pickerPositions[0]);

  const entries = await getLeaderboard(activeSeason, activePosition);
  const qualified = entries.filter((e) => e.qualified);
  const unqualified = entries.filter((e) => !e.qualified);

  const noun =
    QUALIFIED_NOUN[activePosition] ?? QUALIFIED_NOUN[DEFAULT_POSITION];
  const blurb =
    COMPOSITE_BLURB[activePosition] ?? COMPOSITE_BLURB[DEFAULT_POSITION];
  const lowVolume =
    LOW_VOLUME_COPY[activePosition] ?? LOW_VOLUME_COPY[DEFAULT_POSITION];

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-4 sm:py-10">
      <div className="flex items-center justify-between gap-3 md:flex-wrap md:items-end md:gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {/* Below md the position name lives in the dropdown to the
                right, so the H1 carries only "Grades" \u2014 no redundant
                "QB" both in the title and the picker. md+ restores the
                "QB Grades" form since the pill picker doesn't repeat the
                title. */}
            <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
              <span className="hidden md:inline">{activePosition} </span>
              Grades
            </h1>
            <span className="md:hidden">
              <InfoDisclosure label="About these grades">
                {qualified.length}{" "}
                {qualified.length === 1 ? noun.singular : noun.plural}
                {" \u00B7 "}
                {blurb} (see{" "}
                <a className="underline" href="/methodology">
                  methodology
                </a>
                )
              </InfoDisclosure>
            </span>
          </div>
          <p className="mt-1 hidden text-sm text-neutral-400 md:block">
            {qualified.length}{" "}
            {qualified.length === 1 ? noun.singular : noun.plural}
            {" \u00B7 "}
            {blurb} (see{" "}
            <a className="underline" href="/methodology">
              methodology
            </a>
            )
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 md:gap-3">
          <PositionPicker
            positions={pickerPositions}
            activePosition={activePosition}
            activeSeason={activeSeason}
          />
          <SeasonPicker
            seasons={seasons}
            activeSeason={activeSeason}
            activePosition={activePosition}
          />
        </div>
      </div>

      {activePosition === "OL" && (
        <p className="mt-3 text-xs text-neutral-500">
          OL is graded as a team unit. Public play-by-play data
          doesn&rsquo;t attribute individual blocks to specific linemen.
        </p>
      )}

      <section
        className={
          (activePosition === "OL" ? "mt-2" : "mt-3 sm:mt-6") +
          " -ml-6 -mr-6 sm:ml-0 sm:mr-0"
        }
      >
        <LeaderboardTable entries={qualified} position={activePosition} />
      </section>

      {unqualified.length > 0 && (
        <section className="mt-10">
          {/* Collapsed by default. The qualified table is the headline; the
              low-volume rows are a noisy footnote most readers don't need.
              Keeping it as native <details> means it works without JS and
              lets the URL hash (#low-volume) deep-link straight to it. */}
          <details
            id="low-volume"
            className="group/lv rounded-lg border border-neutral-800"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-neutral-400 hover:text-neutral-200">
              <span>
                {lowVolume.heading}{" "}
                <span className="ml-1 font-normal normal-case text-neutral-500">
                  ({unqualified.length})
                </span>
              </span>
              <span
                aria-hidden
                className="text-xs text-neutral-500 transition-transform group-open/lv:rotate-180"
              >
                {"\u25BC"}
              </span>
            </summary>
            <div className="border-t border-neutral-800 px-4 py-4">
              <p className="mb-3 text-xs text-neutral-500">
                {lowVolume.threshold}
              </p>
              <LeaderboardTable
                entries={unqualified}
                position={activePosition}
              />
            </div>
          </details>
        </section>
      )}
    </main>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20 text-center">
      <h1 className="text-2xl font-semibold">No grades yet</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Run <code className="rounded bg-neutral-800 px-1.5 py-0.5">
          nflgrades grade --season 2024
        </code>{" "}
        in the pipeline to populate <code>season_grades</code>, then reload.
      </p>
    </main>
  );
}

function firstOf(p: string | string[] | undefined): string | undefined {
  if (p === undefined) return undefined;
  return Array.isArray(p) ? p[0] : p;
}
