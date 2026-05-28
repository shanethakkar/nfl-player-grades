import { Skeleton } from "@/components/Skeleton";

/**
 * Loading skeleton for the player-grades landing page.
 *
 * Shape mirrors the post-fetch layout (centered column hugging the
 * table, title left, picker placeholders, table rows) so the swap to
 * real content doesn't shift anything around.
 */
export default function HomeLoading() {
  return (
    <main className="mx-auto max-w-[1400px] px-6 py-4 sm:py-10">
      <div className="mx-auto w-full max-w-[900px]">
        <div className="flex flex-wrap items-center justify-between gap-3 md:block">
          <Skeleton className="h-8 w-32 md:h-10 md:w-44" />
          <div className="flex items-center gap-2 md:mt-4 md:gap-3">
            <Skeleton className="h-9 w-20 md:w-72" />
            <Skeleton className="h-9 w-24 md:w-72" />
          </div>
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
      <Skeleton className="h-4 w-40 shrink-0 sm:w-56" />
      <Skeleton className="hidden h-4 w-12 shrink-0 sm:block" />
      <div className="ml-auto flex items-center gap-3">
        <Skeleton className="h-5 w-12" />
        <Skeleton className="hidden h-4 w-10 sm:block" />
        <Skeleton className="hidden h-4 w-10 sm:block" />
      </div>
    </div>
  );
}
