import { Skeleton } from "@/components/Skeleton";

/**
 * Loading skeleton for the team profile (/teams/[abbr]). Approximates
 * the post-fetch layout: back link, header with logo + name, grade
 * card, lineup grid, then roster table.
 */
export default function TeamProfileLoading() {
  return (
    <main className="mx-auto max-w-[1400px] px-6 py-10">
      <Skeleton className="h-4 w-32" />

      <div className="mt-6 mb-8 flex items-end justify-between gap-4">
        <div className="flex items-center gap-4">
          <Skeleton className="h-14 w-14 rounded-full" />
          <div>
            <Skeleton className="h-8 w-56" />
            <Skeleton className="mt-2 h-4 w-40" />
          </div>
        </div>
        <Skeleton className="hidden h-9 w-72 md:block" />
      </div>

      <div className="mb-10 rounded-lg border border-neutral-800 p-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-12 w-32" />
          <div className="flex gap-3">
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-10 w-20" />
          </div>
        </div>
        <Skeleton className="mt-6 h-32 w-full" />
      </div>

      <Skeleton className="mb-3 h-4 w-32" />
      <Skeleton className="mb-12 h-64 w-full" />

      <Skeleton className="mb-3 h-4 w-32" />
      <div className="rounded-lg border border-neutral-800">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 border-t border-neutral-800/50 px-4 py-3 first:border-t-0"
          >
            <Skeleton className="h-3 w-6" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="ml-auto h-5 w-12" />
          </div>
        ))}
      </div>
    </main>
  );
}
