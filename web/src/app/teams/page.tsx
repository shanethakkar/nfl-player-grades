import type { Metadata } from "next";

import { TeamLeaderboardTable } from "@/components/TeamLeaderboardTable";
import { TeamsSeasonPicker } from "@/components/TeamsSeasonPicker";
import { getGradedTeamSeasons, getTeamsLeaderboard } from "@/lib/queries";

type SearchParams = Promise<{ season?: string | string[] }>;

type Props = { searchParams: SearchParams };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { season } = await searchParams;
  const s = firstOf(season);
  if (s && Number.isFinite(Number(s))) {
    return { title: `Team Grades — ${s}` };
  }
  return { title: "Team Grades" };
}

export default async function TeamsIndexPage({ searchParams }: Props) {
  const seasons = await getGradedTeamSeasons();
  if (seasons.length === 0) {
    return <EmptyState />;
  }

  const { season: seasonRaw } = await searchParams;
  const requested = firstOf(seasonRaw);
  const activeSeason =
    requested && seasons.includes(Number(requested))
      ? Number(requested)
      : seasons[0];

  const entries = await getTeamsLeaderboard(activeSeason);

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-4 sm:py-10">
      {/* Title + description stack on top, picker drops onto its own row
          below the blurb. Cleaner than crowding the picker beside the
          title when there's no second control to anchor it. */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          Team Grades
        </h1>
        <p className="mt-1 hidden text-sm text-neutral-400 md:block">
          All 32 teams ranked by composite grade. Click any row for the team
          page (roster + lineup + position breakdown). Methodology:{" "}
          <a className="underline" href="/methodology">
            see methodology
          </a>
          .
        </p>
        <div className="mt-3 md:mt-4">
          <TeamsSeasonPicker seasons={seasons} activeSeason={activeSeason} />
        </div>
      </div>

      <section className="mt-3 -ml-6 -mr-6 sm:ml-0 sm:mr-0 sm:mt-6">
        <TeamLeaderboardTable entries={entries} season={activeSeason} />
      </section>
    </main>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20 text-center">
      <h1 className="text-2xl font-semibold">No team grades yet</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Run{" "}
        <code className="rounded bg-neutral-800 px-1.5 py-0.5">
          nflgrades grade-teams --season 2024
        </code>{" "}
        in the pipeline to populate <code>team_grades</code>, then reload.
      </p>
    </main>
  );
}

function firstOf(v: string | string[] | undefined): string | undefined {
  if (v === undefined) return undefined;
  return Array.isArray(v) ? v[0] : v;
}
