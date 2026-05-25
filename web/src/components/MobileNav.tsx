"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PlayerSearch } from "./PlayerSearch";

/**
 * Mobile-only hamburger drawer for the site header. Renders the same
 * nav links + player search that the desktop header shows inline, but
 * tucked behind a toggle so the mobile header stays at one row.
 *
 * Hidden at `md` and up — the desktop SiteHeader layout takes over there.
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);

  // Lock body scroll while the drawer is open so the page behind doesn't
  // scroll on touch. Cleanup restores the previous overflow.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 w-9 items-center justify-center rounded-md border border-neutral-800 text-neutral-300 hover:text-white"
      >
        {open ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop — tap to close */}
          <div
            aria-hidden
            className="fixed inset-0 z-40 bg-black/60"
            onClick={() => setOpen(false)}
          />
          {/* Drawer — full-width panel anchored below the header */}
          <div className="fixed inset-x-0 top-[57px] z-50 border-b border-neutral-800 bg-neutral-950 px-6 py-4">
            <div className="mb-4">
              <PlayerSearch />
            </div>
            <nav className="flex flex-col gap-1 text-sm text-neutral-200">
              <Link href="/" className="rounded px-2 py-2 hover:bg-neutral-900" onClick={() => setOpen(false)}>
                Grades
              </Link>
              <Link href="/teams" className="rounded px-2 py-2 hover:bg-neutral-900" onClick={() => setOpen(false)}>
                Teams
              </Link>
              <Link href="/methodology" className="rounded px-2 py-2 hover:bg-neutral-900" onClick={() => setOpen(false)}>
                Methodology
              </Link>
              <Link href="/methodology/audit" className="rounded px-2 py-2 hover:bg-neutral-900" onClick={() => setOpen(false)}>
                Research
              </Link>
            </nav>
          </div>
        </>
      )}
    </div>
  );
}
