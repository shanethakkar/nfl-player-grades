import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/BackLink";
import { LineupDiagram } from "@/components/LineupDiagram";
import { RosterTable } from "@/components/RosterTable";
import { TeamGradeCard } from "@/components/TeamGradeCard";
import { TeamLogo } from "@/components/TeamLogo";
import { TeamSeasonPicker } from "@/components/TeamSeasonPicker";
import { TeamSwitcher } from "@/components/TeamSwitcher";
import {
  getAllTeams,
  getTeamByAbbr,
  getTeamGrade,
  getTeamGradeComponents,
  getTeamGradeHistory,
  getTeamLineup,
  getTeamRoster,
  getTeamSeasons,
} from "@/lib/queries";

// ISR — page HTML cached at the edge for an hour. Queries are cached
// for the same TTL via `unstable_cache`. Team data only refreshes when
// the pipeline runs (Bowls in season, audits otherwise).
export const revalidate = 3600;

type PageProps = {
  params: Promise<{ abbr: string }>;
  searchParams: Promise<{ season?: string | string[] }>;
};

function firstOf(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export async function generateMetadata({
  params,
  searchParams,
}: PageProps): Promise<Metadata> {
  const { abbr } = await params;
  const { season } = await searchParams;
  const team = await getTeamByAbbr(abbr.toUpperCase());
  if (!team) return { title: "Team — NFL Player Grades" };
  const seasonStr = firstOf(season);
  if (seasonStr && Number.isFinite(Number(seasonStr))) {
    return { title: `${team.name} — ${seasonStr}` };
  }
  return { title: `${team.name} — NFL Player Grades` };
}

export default async function TeamPage({ params, searchParams }: PageProps) {
  const { abbr: abbrRaw } = await params;
  const { season: seasonRaw } = await searchParams;
  const abbr = abbrRaw.toUpperCase();

  const [team, allTeams] = await Promise.all([
    getTeamByAbbr(abbr),
    getAllTeams(),
  ]);
  if (!team) notFound();

  const seasons = await getTeamSeasons(abbr);
  // Resolve the active season: ?season= param if valid, otherwise the
  // newest season we have player_seasons rows for.
  const seasonParam = firstOf(seasonRaw);
  const requested = seasonParam ? Number(seasonParam) : NaN;
  const activeSeason =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? null);

  const [roster, lineup, teamGrade, teamGradeComponents, teamGradeHistory] =
    activeSeason !== null
      ? await Promise.all([
          getTeamRoster(abbr, activeSeason),
          getTeamLineup(abbr, activeSeason),
          getTeamGrade(abbr, activeSeason),
          getTeamGradeComponents(abbr, activeSeason),
          getTeamGradeHistory(abbr),
        ])
      : [[], null, null, [], []];

  return (
    <main className="mx-auto max-w-[1400px] px-6 py-10">
      <BackLink />

      <div className="mt-4 mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-4">
          <TeamLogo abbr={team.abbr} size={56} />
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-neutral-100">
              {team.name}
            </h1>
            <p className="mt-1 text-sm text-neutral-400">
              {team.conference} {team.division}
              {" · "}
              {roster.length === 0
                ? "No roster data for this season"
                : `${roster.length} players`}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TeamSwitcher
            teams={allTeams}
            activeAbbr={abbr}
            activeSeason={activeSeason}
          />
          {activeSeason !== null && (
            <TeamSeasonPicker
              abbr={abbr}
              seasons={seasons}
              activeSeason={activeSeason}
            />
          )}
        </div>
      </div>

      {teamGrade && activeSeason !== null && (
        <section className="mb-10">
          <TeamGradeCard
            summary={teamGrade}
            components={teamGradeComponents}
            history={teamGradeHistory}
            season={activeSeason}
          />
        </section>
      )}

      <section className="mb-12">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Starting lineup
        </h2>
        {lineup === null ? (
          <p className="text-sm text-neutral-500">
            No depth chart available for this season.
          </p>
        ) : (
          <LineupDiagram lineup={lineup} season={activeSeason} />
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Full roster
        </h2>
        {activeSeason === null ? (
          <p className="text-sm text-neutral-500">
            No roster data available for {team.name}.
          </p>
        ) : (
          <RosterTable entries={roster} />
        )}
      </section>
    </main>
  );
}
