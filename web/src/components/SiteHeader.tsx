import Link from "next/link";

import { PlayerSearch } from "./PlayerSearch";

/**
 * Persistent site header. Small, monospaced, lets the grade tables
 * remain the visual focus. The player-search widget on the right is
 * the only client component in here; the rest is plain Next.js Links.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-neutral-800 bg-neutral-950">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-4">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-neutral-100 hover:text-white"
        >
          NFL Player Grades
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-x-5 gap-y-2 text-sm text-neutral-300">
          <nav className="flex items-center gap-5">
            <Link href="/" className="hover:text-white">
              Leaderboard
            </Link>
            <Link href="/methodology" className="hover:text-white">
              Methodology
            </Link>
          </nav>
          <PlayerSearch />
        </div>
      </div>
    </header>
  );
}
