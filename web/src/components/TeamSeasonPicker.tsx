"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

/**
 * Season picker for /teams/[abbr]. Mirrors the leaderboard SeasonPicker
 * (mobile select + desktop pill tabs) but the pathname is team-aware so
 * a year change keeps you on the same team page.
 */
type Props = {
  abbr: string;
  seasons: number[];
  activeSeason: number;
};

export function TeamSeasonPicker({ abbr, seasons, activeSeason }: Props) {
  const router = useRouter();
  if (seasons.length === 0) return null;

  function hrefFor(season: number): string {
    return `/teams/${abbr}?season=${season}`;
  }

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(hrefFor(Number(e.target.value)) as any);
  }

  return (
    <>
      <select
        value={activeSeason}
        onChange={onChange}
        className="md:hidden rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-600"
      >
        {seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <div className="hidden md:inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        {seasons.map((season) => {
          const isActive = season === activeSeason;
          return (
            <Link
              key={season}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              href={hrefFor(season) as any}
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
