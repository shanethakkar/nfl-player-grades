import { LeaderboardTable } from "@/components/LeaderboardTable";
import { SeasonPicker } from "@/components/SeasonPicker";
import { getGradedSeasons, getLeaderboard } from "@/lib/queries";

type SearchParams = Promise<{ season?: string | string[] }>;

type Props = { searchParams: SearchParams };

const POSITION = "QB";     // v1: only QB is graded (ADR-0013)

export default async function HomePage({ searchParams }: Props) {
  const seasons = await getGradedSeasons();
  if (seasons.length === 0) {
    return <EmptyState />;
  }

  const { season: seasonParam } = await searchParams;
  const requested = firstOf(seasonParam);
  const activeSeason =
    requested && seasons.includes(Number(requested))
      ? Number(requested)
      : seasons[0];

  const entries = await getLeaderboard(activeSeason, POSITION);
  const qualified = entries.filter((e) => e.qualified);
  const unqualified = entries.filter((e) => !e.qualified);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">QB Leaderboard</h1>
          <p className="mt-1 text-sm text-neutral-400">
            {qualified.length} qualified starter{qualified.length === 1 ? "" : "s"}
            {" \u00B7 "}composite of EPA/dropback, CPOE, and success rate
            (see <a className="underline" href="/methodology">methodology</a>)
          </p>
        </div>
        <SeasonPicker seasons={seasons} activeSeason={activeSeason} />
      </div>

      <section className="mt-6">
        <LeaderboardTable entries={qualified} />
      </section>

      {unqualified.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">
            Low-volume passers ({unqualified.length})
          </h2>
          <p className="mb-3 text-xs text-neutral-500">
            Fewer than 200 qualifying dropbacks. Grades still computed on the
            same 0-100 scale but treat them as noisy.
          </p>
          <LeaderboardTable entries={unqualified} />
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
