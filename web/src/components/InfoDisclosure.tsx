"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type Props = {
  label?: string;
  children: ReactNode;
};

/**
 * Small (i) button that toggles an inline popover containing arbitrary
 * children. Used to tuck mobile-only context (e.g. the leaderboard
 * description) behind a tap so the page header stays compact.
 *
 * - Closes on outside click and Escape.
 * - Anchored to the button; renders directly underneath with
 *   `absolute` positioning, so callers should put it inside an element
 *   that establishes a positioning context (or accept default body flow).
 */
export function InfoDisclosure({ label = "More info", children }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-neutral-700 text-[11px] font-semibold leading-none text-neutral-400 hover:border-neutral-500 hover:text-neutral-100"
      >
        i
      </button>
      {open && (
        <span className="absolute left-0 top-full z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-neutral-800 bg-neutral-900 p-3 text-xs leading-relaxed text-neutral-300 shadow-lg">
          {children}
        </span>
      )}
    </span>
  );
}
