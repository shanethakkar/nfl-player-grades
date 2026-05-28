import { Skeleton } from "@/components/Skeleton";

/**
 * Loading skeleton for the player profile (/players/[slug]).
 * Approximates the post-fetch layout: back link, header with headshot +
 * name + meta, grade hero, career chart, then component breakdown.
 */
export default function PlayerProfileLoading() {
  return (
    <main className="mx-auto max-w-[1100px] px-6 py-10">
      <Skeleton className="h-4 w-32" />

      <div className="mt-6 mb-8 flex items-end gap-4">
        <Skeleton className="h-24 w-24 rounded-lg" />
        <div className="flex-1">
          <Skeleton className="h-8 w-60" />
          <Skeleton className="mt-2 h-4 w-44" />
        </div>
        <Skeleton className="hidden h-9 w-72 md:block" />
      </div>

      <div className="mb-10 rounded-lg border border-neutral-800 p-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-12 w-32" />
            <Skeleton className="mt-2 h-3 w-20" />
          </div>
          <Skeleton className="h-10 w-24" />
        </div>
        <Skeleton className="mt-6 h-32 w-full" />
      </div>

      <Skeleton className="mb-3 h-4 w-40" />
      <div className="mb-10 rounded-lg border border-neutral-800 p-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 border-t border-neutral-800/50 py-3 first:border-t-0">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="ml-auto h-4 w-12" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </div>
    </main>
  );
}
