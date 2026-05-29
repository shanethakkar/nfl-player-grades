import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";


import { BackLink } from "@/components/BackLink";
import { CareerGradeChart } from "@/components/CareerGradeChart";
import { CareerSummary } from "@/components/CareerSummary";
import { PlayerHeadshot } from "@/components/PlayerHeadshot";
import { SeasonGradesSection } from "@/components/SeasonGradesSection";
import { TeamLogo } from "@/components/TeamLogo";
import { getPlayerDetailBySlug } from "@/lib/queries";

type PageProps = {
  params: Promise<{ slug: string }>;
};

/**
 * Browser tab title is "{Name} — NFL Player Grades" so bookmarks,
 * tab strips, and shared links read clearly. We re-fetch the player
 * meta inside generateMetadata; Next.js dedupes the underlying DB call
 * with the page render.
 */
export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const detail = await getPlayerDetailBySlug(slug);
  if (detail === null) return { title: "Player" };
  return {
    title: `${detail.player.full_name} — NFL Player Grades`,
  };
}

export default async function PlayerPage({ params }: PageProps) {
  const { slug } = await params;
  const detail = await getPlayerDetailBySlug(slug);
  if (detail === null) notFound();

  const { player, grades } = detail;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <BackLink />

      <header className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-5">
          <PlayerHeadshot playerId={player.player_id} size={96} />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{player.full_name}</h1>
            <div className="mt-1 flex items-center gap-2 text-sm text-neutral-400">
              <span>{player.position}</span>
              {player.current_team_abbr && (
                <>
                  <span className="text-neutral-600">·</span>
                  {/* Team chip is a Link to the team profile so users
                      can pivot from "this player" → "the rest of this
                      roster" in one click. */}
                  <Link
                    href={{ pathname: `/teams/${player.current_team_abbr}` }}
                    className="group/team inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 transition-colors hover:bg-neutral-900"
                  >
                    <TeamLogo abbr={player.current_team_abbr} size={22} />
                    <span className="text-neutral-300 group-hover/team:text-neutral-100">{player.current_team_abbr}</span>
                    <span
                      aria-hidden
                      className="text-xs leading-none text-neutral-600 transition-all duration-150 group-hover/team:translate-x-0.5 group-hover/team:text-neutral-300"
                    >
                      ›
                    </span>
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {grades.length === 0 ? (
        <p className="mt-10 text-sm text-neutral-500">
          No season grades for this player yet. (Either they haven&apos;t
          played at a graded position or their position&apos;s grader
          hasn&apos;t been written — see{" "}
          <Link href="/methodology" className="underline">
            methodology
          </Link>
          .)
        </p>
      ) : (
        <>
          <CareerSummary grades={grades} />
          <CareerGradeChart grades={grades} />
          <SeasonGradesSection grades={grades} />
        </>
      )}
    </main>
  );
}
