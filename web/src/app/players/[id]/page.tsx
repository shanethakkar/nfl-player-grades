import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CareerGradeChart } from "@/components/CareerGradeChart";
import { CareerSummary } from "@/components/CareerSummary";
import { SeasonGradesSection } from "@/components/SeasonGradesSection";
import { getPlayerDetail } from "@/lib/queries";

type PageProps = {
  params: Promise<{ id: string }>;
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
  const { id } = await params;
  const playerId = Number(id);
  if (!Number.isFinite(playerId) || playerId <= 0) {
    return { title: "Player" };
  }
  const detail = await getPlayerDetail(playerId);
  if (detail === null) return { title: "Player" };
  return {
    title: `${detail.player.full_name} — NFL Player Grades`,
  };
}

export default async function PlayerPage({ params }: PageProps) {
  const { id } = await params;
  const playerId = Number(id);
  if (!Number.isFinite(playerId) || playerId <= 0) notFound();

  const detail = await getPlayerDetail(playerId);
  if (detail === null) notFound();

  const { player, grades } = detail;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <Link
        href="/"
        className="text-sm text-neutral-400 hover:text-neutral-100"
      >
        ← back to leaderboard
      </Link>

      <header className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{player.full_name}</h1>
          <p className="mt-1 text-sm text-neutral-400">
            {player.position}
            {player.current_team_abbr && (
              <>
                {" · "}
                <span className="text-neutral-300">{player.current_team_abbr}</span>
              </>
            )}
            {player.gsis_id && (
              <span className="ml-3 text-xs text-neutral-600">
                gsis {player.gsis_id}
              </span>
            )}
          </p>
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
