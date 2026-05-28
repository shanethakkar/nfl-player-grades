"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Logo } from "./Logo";
import { MobileNav } from "./MobileNav";
import { PlayerSearch } from "./PlayerSearch";

/**
 * Persistent site header. Small, monospaced, lets the grade tables
 * remain the visual focus.
 *
 * - `sticky top-0` so the nav follows the scroll; always-on
 *   backdrop-blur means content faintly shows through, and once the
 *   page has scrolled past the top the bg darkens + a hairline bottom
 *   border appears for separation against the leaderboard.
 * - Desktop (md+): logo + inline nav + search.
 * - Mobile: logo + hamburger drawer (MobileNav) — keeps the header to a
 *   single row so the leaderboard sits closer to the top of the viewport.
 */
export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={
        "sticky top-0 z-40 backdrop-blur-md transition-[background-color,border-color,box-shadow] duration-200 " +
        (scrolled
          ? "border-b border-neutral-800 bg-neutral-950/80 shadow-[0_1px_0_rgba(0,0,0,0.4)]"
          : "border-b border-transparent bg-neutral-950/95")
      }
    >
      <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-3 px-6 py-4">
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
              Player Grades
            </Link>
            <Link href="/teams" className="hover:text-white">
              Team Grades
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
