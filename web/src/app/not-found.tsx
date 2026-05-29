import Link from "next/link";

import { Logo } from "@/components/Logo";

export const metadata = {
  title: "Not found — NFL Player Grades",
};

/**
 * Custom 404 page. Fired by Next.js whenever a route or a server-side
 * `notFound()` resolves nothing — most commonly a `/players/[slug]`
 * with a slug that doesn't exist, or a hand-typed URL.
 *
 * Visual brief: match the rest of the site's dark, minimal feel. Don't
 * try to be funny; just orient the user and give them a clean way back
 * to the leaderboards.
 */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-6 py-16 text-center">
      <Logo size={48} className="mb-6" />
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-neutral-500">
        404 · Not found
      </p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-neutral-100 sm:text-4xl">
        We couldn&rsquo;t find that page.
      </h1>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-neutral-400">
        The player or team you&rsquo;re looking for might not be graded yet,
        the slug may have changed, or the URL may be off by a character.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-lg bg-neutral-100 px-4 py-2 text-sm font-semibold text-neutral-900 hover:bg-white"
        >
          Back to Player Grades
        </Link>
        <Link
          href="/teams"
          className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:border-neutral-500 hover:text-neutral-100"
        >
          Team Grades
        </Link>
      </div>
    </main>
  );
}
