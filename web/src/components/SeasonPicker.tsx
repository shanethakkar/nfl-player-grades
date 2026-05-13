"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

type Props = {
  seasons: number[];
  activeSeason: number;
  /**
   * When set, links include `position=` so switching seasons preserves the
   * currently-selected position. `"QB"` is omitted (it's the default).
   */
  activePosition?: string;
};

export function SeasonPicker({ seasons, activeSeason, activePosition }: Props) {
  const router = useRouter();

  if (seasons.length === 0) return null;

  function buildQuery(season: number): Record<string, string | number> {
    const q: Record<string, string | number> = { season };
    if (activePosition && activePosition !== "QB") q.position = activePosition;
    return q;
  }

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const q = buildQuery(Number(e.target.value));
    const qs = new URLSearchParams(
      Object.entries(q).map(([k, v]) => [k, String(v)]),
    ).toString();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(`/?${qs}` as any);
  }

  return (
    <>
      {/* Mobile: compact select — avoids page-level overflow from 10 pills */}
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

      {/* Desktop: tab-style pills */}
      <div className="hidden md:inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        {seasons.map((season) => {
          const isActive = season === activeSeason;
          return (
            <Link
              key={season}
              href={{ pathname: "/", query: buildQuery(season) }}
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
