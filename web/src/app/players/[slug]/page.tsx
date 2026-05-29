import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";


import { BackLink } from "@/components/BackLink";
import { CareerGradeChart } from "@/components/CareerGradeChart";
import { PlayerHeadshot } from "@/components/PlayerHeadshot";
import { SeasonGradesSection } from "@/components/SeasonGradesSection";
import { TeamLogo } from "@/components/TeamLogo";
import { gradeColor } from "@/lib/grades";
import { getPlayerDetailBySlug } from "@/lib/queries";

// ISR — page HTML cached at the edge for an hour. Player profiles
// only change when the grading pipeline reruns; until then every
// visit can come from the edge cache with zero server work.
export const revalidate = 3600;

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

  // Career-summary numbers, computed inline (used to live in a
  // standalone <CareerSummary /> with 3 stat boxes — now folded into
  // the hero header as a one-line stat strip so it doesn't waste
  // vertical space). Only qualified seasons count for the headline
  // numbers; below-volume grades are too noisy to average over.
  const qualified = grades.filter((g) => g.qualified);
  const avg =
    qualified.length === 0
      ? null
      : qualified.reduce((acc, g) => acc + g.composite_grade, 0) /
        qualified.length;
  const best =
    qualified.length === 0
      ? null
      : qualified.reduce(
          (top, g) => (g.composite_grade > top.composite_grade ? g : top),
          qualified[0],
        );
  const latest = qualified[0] ?? null; // grades come back season DESC

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <BackLink />

      {/* Hero header.
          Mobile: stacks vertically — headshot on its own line above
          the name so the name has full container width and doesn't
          wrap. Grade chip is a full-width row at the bottom with the
          big number on the left and the meta label on the right —
          uses the horizontal space instead of wasting it.
          Desktop (sm+): collapses to a single row — headshot left,
          name + meta middle, grade chip right. */}
      <header className="mt-6 flex flex-col gap-5 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between sm:gap-6">
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-end sm:gap-5 md:gap-7">
          <PlayerHeadshot
            playerId={player.player_id}
            size={96}
            className="sm:hidden"
          />
          <PlayerHeadshot
            playerId={player.player_id}
            size={144}
            className="hidden sm:block"
          />
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-neutral-100 sm:text-4xl md:text-5xl">
              {player.full_name}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-neutral-400">
              <span>{player.position}</span>
              {player.current_team_abbr && (
                <>
                  <span className="text-neutral-600">·</span>
                  <Link
                    href={{ pathname: `/teams/${player.current_team_abbr}` }}
                    className="group/team inline-flex items-center gap-1.5"
                  >
                    <TeamLogo abbr={player.current_team_abbr} size={20} />
                    <span className="text-neutral-300 transition-colors group-hover/team:text-neutral-100 group-hover/team:underline">
                      {player.current_team_abbr}
                    </span>
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
            {qualified.length > 0 && avg !== null && best && (
              <>
                <div className="mt-4 h-px w-24 bg-neutral-800" />
                <p className="mt-3 text-sm text-neutral-400">
                  <span className="text-neutral-200">{qualified.length}</span>{" "}
                  graded{" "}
                  {qualified.length === 1 ? "season" : "seasons"}
                  <span className="mx-2 text-neutral-700">·</span>
                  <span className="text-neutral-200">{avg.toFixed(1)}</span>{" "}
                  average
                  <span className="mx-2 text-neutral-700">·</span>
                  <span className="text-neutral-200">
                    {best.composite_grade.toFixed(1)}
                  </span>{" "}
                  best{" "}
                  <span className="text-neutral-600">({best.season})</span>
                </p>
              </>
            )}
          </div>
        </div>

        {/* Latest-season headline grade. Mobile: full-width row with
            the number flush left and the meta label flush right —
            fills the horizontal space rather than wasting it. Desktop
            (sm+): column flush right, label below the number. */}
        {latest && (
          <div className="flex w-full items-baseline justify-between gap-4 leading-none sm:w-auto sm:flex-col sm:items-end sm:gap-2">
            <div
              className={`font-mono text-5xl font-bold tracking-tight md:text-6xl ${gradeColor(latest.composite_grade)}`}
            >
              {latest.composite_grade.toFixed(1)}
            </div>
            <div className="text-right text-[11px] font-semibold uppercase tracking-[0.15em] text-neutral-500">
              {latest.season} grade
              <span className="ml-1.5 text-neutral-600">
                · {latest.percentile.toFixed(0)} pct
              </span>
            </div>
          </div>
        )}
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
          <CareerGradeChart grades={grades} />
          <SeasonGradesSection grades={grades} />
        </>
      )}
    </main>
  );
}
