import Link from "next/link";

import { Logo } from "./Logo";
import { MobileNav } from "./MobileNav";
import { PlayerSearch } from "./PlayerSearch";

/**
 * Persistent site header. Small, monospaced, lets the grade tables
 * remain the visual focus.
 *
 * - Desktop (md+): logo + inline nav + search.
 * - Mobile: logo + hamburger drawer (MobileNav) — keeps the header to a
 *   single row so the leaderboard sits closer to the top of the viewport.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-neutral-800 bg-neutral-950">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-3 px-6 py-4">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold tracking-tight text-neutral-100 hover:text-white"
        >
          <Logo size={30} />
          NFL Player Grades
        </Link>
        {/* Desktop nav + search — hidden on mobile in favor of the drawer */}
        <div className="hidden md:flex flex-wrap items-center justify-end gap-x-5 gap-y-2 text-sm text-neutral-300">
          <nav className="flex items-center gap-5">
            <Link href="/" className="hover:text-white">
              Leaderboard
            </Link>
            <Link href="/teams" className="hover:text-white">
              Teams
            </Link>
            <Link href="/methodology" className="hover:text-white">
              Methodology
            </Link>
            <Link href="/methodology/audit" className="hover:text-white">
              Research
            </Link>
          </nav>
          <PlayerSearch />
        </div>
        <MobileNav />
      </div>
    </header>
  );
}
