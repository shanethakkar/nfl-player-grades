import Link from "next/link";

/**
 * Persistent site header. Small, monospaced, lets the grade tables
 * remain the visual focus.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-neutral-800 bg-neutral-950">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-neutral-100 hover:text-white"
        >
          NFL Player Grades
        </Link>
        <nav className="flex items-center gap-5 text-sm text-neutral-300">
          <Link href="/" className="hover:text-white">
            Leaderboard
          </Link>
          <Link href="/methodology" className="hover:text-white">
            Methodology
          </Link>
        </nav>
      </div>
    </header>
  );
}
