"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

type Props = {
  positions: readonly string[];
  activePosition: string;
  /**
   * When set, links include `season=` so clicking a position preserves the
   * currently-selected season.
   */
  activeSeason?: number;
};

/**
 * Tab-style position picker, parallel to {@link SeasonPicker}.
 *
 * - Mobile: compact `<select>` dropdown so the picker doesn't overflow the
 *   viewport when there are 12 positions.
 * - Desktop: server-rendered pill tabs via plain `<Link>`. `"QB"` links omit
 *   `?position=` so the default URL (`/`) stays clean.
 */
export function PositionPicker({
  positions,
  activePosition,
  activeSeason,
}: Props) {
  const router = useRouter();

  if (positions.length === 0) return null;

  function buildQuery(position: string): Record<string, string | number> {
    const q: Record<string, string | number> = {};
    if (position !== "QB") q.position = position;
    if (activeSeason !== undefined) q.season = activeSeason;
    return q;
  }

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const q = buildQuery(e.target.value);
    const qs = new URLSearchParams(
      Object.entries(q).map(([k, v]) => [k, String(v)]),
    ).toString();
    const url = qs ? `/?${qs}` : "/";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(url as any);
  }

  return (
    <>
      {/* Mobile: compact select — avoids page-level overflow from 12 pills.
          `appearance-none` strips the OS dropdown arrow (which sits at
          the far right edge regardless of how short the value is); we
          render a custom chevron right after the text so the button
          reads as one tight unit. */}
      <div className="relative inline-flex items-center md:hidden">
        <select
          value={activePosition}
          onChange={onChange}
          className="appearance-none rounded-lg border border-neutral-800 bg-neutral-950 py-2 pl-3 pr-7 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-600"
        >
          {positions.map((p) => (
            <option key={p} value={p}>
              {p}
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

      {/* Desktop: tab-style pills */}
      <div className="hidden md:inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
        {positions.map((position) => {
          const isActive = position === activePosition;
          const query: Record<string, string | number> = {};
          if (position !== "QB") query.position = position;
          if (activeSeason !== undefined) query.season = activeSeason;
          return (
            <Link
              key={position}
              href={{ pathname: "/", query }}
              className={
                isActive
                  ? "rounded-md bg-neutral-100 px-3 py-1 text-sm font-semibold text-neutral-900"
                  : "rounded-md px-3 py-1 text-sm text-neutral-400 hover:text-neutral-100"
              }
            >
              {position}
            </Link>
          );
        })}
      </div>
    </>
  );
}
