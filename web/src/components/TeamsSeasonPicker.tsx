"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

type Props = {
  seasons: number[];
  activeSeason: number;
};

/**
 * Season picker for the /teams leaderboard. Mirrors {@link SeasonPicker}
 * but routes back to /teams instead of /. Mobile: native <select> with
 * a custom chevron. Desktop: tab-style pills.
 */
export function TeamsSeasonPicker({ seasons, activeSeason }: Props) {
  const router = useRouter();
  if (seasons.length === 0) return null;

  function urlFor(season: number): string {
    return `/teams?season=${season}`;
  }

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(urlFor(Number(e.target.value)) as any);
  }

  return (
    <>
      {/* Mobile: compact select with custom chevron */}
      <div className="relative inline-flex items-center md:hidden">
        <select
          value={activeSeason}
          onChange={onChange}
          className="appearance-none rounded-lg border border-neutral-800 bg-neutral-950 py-2 pl-3 pr-7 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-600"
        >
          {seasons.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span
          aria-hidden
          className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-sm text-neutral-400"
        >
          {"▾"}
        </span>
      </div>

      {/* Desktop: pill tabs */}
      <div className="hidden md:inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        {seasons.map((season) => {
          const isActive = season === activeSeason;
          return (
            <Link
              key={season}
              href={urlFor(season)}
              className={
                isActive
                  ? "rounded-md bg-neutral-100 px-3 py-1 text-sm font-semibold text-neutral-900"
                  : "rounded-md px-3 py-1 text-sm text-neutral-400 hover:text-neutral-100"
              }
            >
              {season}
            </Link>
          );
        })}
      </div>
    </>
  );
}
