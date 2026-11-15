import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ProvisionalBadge } from "@/components/ProvisionalBadge";
import { TeamLeaderboardTable } from "@/components/TeamLeaderboardTable";
import { TeamsSeasonPicker } from "@/components/TeamsSeasonPicker";
import {
  getGradedTeamSeasons,
  getSeasonThroughWeek,
  getTeamsLeaderboard,
} from "@/lib/queries";

export async function generateTeamsIndexMetadata(
  seasonRaw?: string,
): Promise<Metadata> {
  if (seasonRaw && Number.isFinite(Number(seasonRaw))) {
    return { title: `Team Grades — ${seasonRaw}` };
  }
  return { title: "Team Grades" };
}

export async function TeamsIndex({ seasonRaw }: { seasonRaw?: string }) {
  const seasons = await getGradedTeamSeasons();
  if (seasons.length === 0) {
    return <EmptyState />;
  }

  const requested = seasonRaw ? Number(seasonRaw) : NaN;
  if (seasonRaw && !Number.isFinite(requested)) {
    notFound();
  }
  // Unknown year on the path 404s (cheap, no leaderboard query). The
  // `/teams` index itself still falls back to the latest season.
  if (seasonRaw && !seasons.includes(requested)) {
    notFound();
  }
  const activeSeason = seasons.includes(requested) ? requested : seasons[0];

  const [entries, throughWeek] = await Promise.all([
    getTeamsLeaderboard(activeSeason),
    getSeasonThroughWeek(activeSeason),
  ]);

  return (
    <main className="mx-auto max-w-[1400px] px-6 py-4 sm:py-10">
      {/* Centered column hugging the table's content width. Header
          (title + description + picker) sits left-aligned within the
          column, so its left edge tracks the table's left edge. */}
      <div className="mx-auto w-max max-w-full">
        <header>
          {/* Title-left + season-picker-right on the same row so the
              header reads compact on mobile — the picker doesn't drop
              to its own row below "Team Grades". Description hangs
              below the title block on desktop. */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
                Team Grades
              </h1>
              {throughWeek !== null && (
                <ProvisionalBadge throughWeek={throughWeek} />
              )}
            </div>
            <TeamsSeasonPicker seasons={seasons} activeSeason={activeSeason} />
          </div>
          {/* `w-0 min-w-full` lets the description fill the column
              (= table width) and wrap at the table's right edge,
              without its own max-content pushing the column wider. */}
          <p className="mt-2 hidden w-0 min-w-full text-sm text-neutral-400 md:block">
            All 32 teams ranked by composite grade. Click any row for the team
            page (roster + lineup + position breakdown). Methodology:{" "}
            <a className="underline" href="/methodology">
              see methodology
            </a>
            .
          </p>
        </header>

        <section className="mt-3 -ml-6 -mr-6 sm:ml-0 sm:mr-0 sm:mt-6">
          <TeamLeaderboardTable entries={entries} season={activeSeason} />
        </section>
      </div>
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
