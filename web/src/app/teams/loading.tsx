import { Skeleton } from "@/components/Skeleton";

/**
 * Loading skeleton for the team-grades landing page. Same shape as the
 * player-grades skeleton (centered column, header + table) but with
 * fewer rows (32 teams cap).
 */
export default function TeamsLoading() {
  return (
    <main className="mx-auto max-w-[1400px] px-6 py-4 sm:py-10">
      <div className="mx-auto w-full max-w-[900px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Skeleton className="h-8 w-44 md:h-10 md:w-56" />
          <Skeleton className="h-9 w-24 md:w-72" />
        </div>
        <Skeleton className="mt-3 hidden h-4 w-full md:block" />

        <div className="mt-6 overflow-hidden rounded-lg border border-neutral-800">
          {Array.from({ length: 12 }).map((_, i) => (
            <SkeletonRow key={i} />
          ))}
        </div>
      </div>
    </main>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 border-t border-neutral-800/50 px-3 py-3 first:border-t-0 sm:px-4">
      <Skeleton className="h-3 w-4 shrink-0" />
      <Skeleton className="h-5 w-5 shrink-0 rounded-full" />
      <Skeleton className="h-4 w-44 shrink-0" />
      <div className="ml-auto flex items-center gap-3">
        <Skeleton className="h-5 w-12" />
        <Skeleton className="hidden h-4 w-10 sm:block" />
        <Skeleton className="hidden h-4 w-10 sm:block" />
        <Skeleton className="hidden h-4 w-10 sm:block" />
      </div>
    </div>
  );
}
