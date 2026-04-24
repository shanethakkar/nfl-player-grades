import Link from "next/link";
import { notFound } from "next/navigation";

import { ComponentBreakdownTable } from "@/components/ComponentBreakdownTable";
import { GradeBadge } from "@/components/GradeBadge";
import { DATA_TIER_LABELS } from "@/lib/grades";
import { getPlayerDetail } from "@/lib/queries";
import type { DataTier, SeasonGradeDetail } from "@/types";

type PageProps = {
  params: Promise<{ id: string }>;
};

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
                {" \u00B7 "}
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
        <div className="mt-8 space-y-10">
          {grades.map((g) => (
            <SeasonGradeCard key={`${g.season}-${g.position}`} grade={g} />
          ))}
        </div>
      )}
    </main>
  );
}

function SeasonGradeCard({ grade: g }: { grade: SeasonGradeDetail }) {
  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-950/60 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">
              {g.season} {g.position}
            </h2>
            {g.team_abbr && (
              <span className="rounded border border-neutral-700 px-2 py-0.5 text-xs text-neutral-300">
                {g.team_abbr}
              </span>
            )}
            <span className="text-[10px] uppercase tracking-wide text-neutral-500">
              {DATA_TIER_LABELS[g.data_tier as DataTier]}
            </span>
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            {g.qualified
              ? `${g.percentile.toFixed(0)}th percentile among qualified ${g.position}s`
              : "Below volume threshold — grade shown for reference"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <GradeBadge
            grade={g.composite_grade}
            tier={g.data_tier as DataTier}
            qualified={g.qualified}
          />
          {g.qualified && (
            <div className="text-right text-xs text-neutral-500">
              <div className="font-mono text-neutral-300">
                z = {formatSignedZ(g.composite_z)}
              </div>
              {g.confidence !== null && (
                <div>confidence {Math.round(g.confidence * 100)}%</div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-5">
        <ComponentBreakdownTable components={g.components} />
      </div>
    </section>
  );
}

function formatSignedZ(z: number): string {
  const sign = z > 0 ? "+" : z < 0 ? "-" : "";
  return `${sign}${Math.abs(z).toFixed(2)}`;
}
