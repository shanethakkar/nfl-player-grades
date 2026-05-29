"use client";

import { useEffect } from "react";
import Link from "next/link";

import { Logo } from "@/components/Logo";

/**
 * Global error boundary for the App Router. Renders when a server
 * component throws or a client component crashes during render. Must
 * be a client component (Next.js contract).
 *
 * Matches the 404 page's layout so failures don't feel like a
 * different site. `reset()` re-renders the failing segment without
 * a full page reload, which fixes most transient failures (network
 * blips, DB hiccups).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error in the browser console so the user (or us, if
    // helping a friend debug) can see what blew up. Production
    // observability would replace this with a real logger.
    // eslint-disable-next-line no-console
    console.error("Unhandled app error:", error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-6 py-16 text-center">
      <Logo size={48} className="mb-6" />
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-neutral-500">
        500 · Something broke
      </p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-neutral-100 sm:text-4xl">
        We hit a snag loading this page.
      </h1>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-neutral-400">
        Most of the time this is a transient hiccup — try again. If it
        keeps happening, the data pipeline or the database might be
        having a moment.
      </p>
      {error.digest && (
        <p className="mt-3 font-mono text-[10px] text-neutral-600">
          ref {error.digest}
        </p>
      )}
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-1.5 rounded-lg bg-neutral-100 px-4 py-2 text-sm font-semibold text-neutral-900 hover:bg-white"
        >
          Try again
        </button>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:border-neutral-500 hover:text-neutral-100"
        >
          Back to Player Grades
        </Link>
      </div>
    </main>
  );
}
