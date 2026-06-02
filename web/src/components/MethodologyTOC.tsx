"use client";

import { useEffect, useState } from "react";

/**
 * Table of contents for the methodology page.
 *
 * Two exports, one shared active-section hook:
 *  - `MethodologyTOCMobile`: a collapsible "On this page" disclosure
 *    that sticks below the SiteHeader on small viewports. Closes on
 *    tap to navigate.
 *  - `MethodologyTOCDesktop`: a sticky right-rail with nested position
 *    links, grouped by phase. Active section highlights on scroll.
 *
 * Both are rendered by the page (the mobile one above the content;
 * the desktop one inside the grid sidebar). The shared
 * `useActiveSection` hook means there's exactly one
 * IntersectionObserver per mounted view.
 */

type TOCItem = {
  id: string;
  label: string;
  children?: { id: string; label: string }[];
};

const ITEMS: TOCItem[] = [
  { id: "scale", label: "The scale" },
  {
    id: "positions",
    label: "Positions",
    children: [
      { id: "pos-QB", label: "QB" },
      { id: "pos-RB", label: "RB" },
      { id: "pos-WR", label: "WR" },
      { id: "pos-TE", label: "TE" },
      { id: "pos-OL", label: "OL" },
      { id: "pos-CB", label: "CB" },
      { id: "pos-S", label: "S" },
      { id: "pos-EDGE", label: "EDGE" },
      { id: "pos-iDL", label: "iDL" },
      { id: "pos-LB", label: "LB" },
      { id: "pos-K", label: "K" },
      { id: "pos-P", label: "P" },
    ],
  },
  { id: "how-built", label: "How a grade is built" },
  { id: "team-grades", label: "Team grades" },
  { id: "limitations", label: "What we don't measure" },
  { id: "data", label: "Data source" },
];

/** Flat list of every tracked anchor — used by the IntersectionObserver. */
const ALL_IDS = ITEMS.flatMap((i) => [i.id, ...(i.children?.map((c) => c.id) ?? [])]);
/** Lookup for the label of the currently-active section. */
const LABELS = new Map<string, string>(
  ITEMS.flatMap((i) => [
    [i.id, i.label] as const,
    ...(i.children?.map((c) => [c.id, c.label] as const) ?? []),
  ]),
);

function useActiveSection() {
  const [active, setActive] = useState<string>(ITEMS[0].id);
  useEffect(() => {
    const els = ALL_IDS.map((id) => document.getElementById(id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (els.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        // Pick the topmost intersecting entry. If nothing is
        // intersecting (between sections), leave `active` alone —
        // avoids flicker as the reader scrolls past a boundary.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort(
            (a, b) =>
              a.boundingClientRect.top - b.boundingClientRect.top,
          );
        if (visible[0]) {
          setActive(visible[0].target.id);
        }
      },
      {
        // -64px top: clears the SiteHeader. -65% bottom: only flip
        // "active" when the section is in the top third of the
        // viewport, so headings stay current as the reader actually
        // reads them.
        rootMargin: "-64px 0px -65% 0px",
        threshold: 0,
      },
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return active;
}

// ---------------------------------------------------------------------------
// Mobile / tablet: collapsible "On this page" disclosure.
// ---------------------------------------------------------------------------

export function MethodologyTOCMobile() {
  const active = useActiveSection();
  const [open, setOpen] = useState(false);
  return (
    <nav
      aria-label="On this page"
      className="sticky top-[57px] z-30 -mx-4 mb-6 border-b border-neutral-800 bg-neutral-950/80 backdrop-blur-md sm:-mx-6"
    >
      <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm sm:px-6">
          <span className="flex items-center gap-2 truncate">
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-neutral-500">
              On this page
            </span>
            <span className="truncate text-neutral-300">
              {LABELS.get(active) ?? ""}
            </span>
          </span>
          <span
            aria-hidden
            className="shrink-0 text-xs text-neutral-500 transition-transform"
            style={{ transform: open ? "rotate(180deg)" : "rotate(0)" }}
          >
            ▼
          </span>
        </summary>
        <ul className="border-t border-neutral-800 px-4 py-2 text-sm sm:px-6">
          {ITEMS.map((item) => (
            <TOCEntry
              key={item.id}
              item={item}
              active={active}
              onClick={() => setOpen(false)}
            />
          ))}
        </ul>
      </details>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Desktop (lg+): sticky right-rail sidebar.
// ---------------------------------------------------------------------------

export function MethodologyTOCDesktop() {
  const active = useActiveSection();
  return (
    <nav aria-label="On this page" className="sticky top-24">
      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-neutral-500">
        On this page
      </div>
      <ul className="mt-3 space-y-0.5 border-l border-neutral-800 pl-3 text-sm">
        {ITEMS.map((item) => (
          <TOCEntry key={item.id} item={item} active={active} />
        ))}
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Shared row renderer.
// ---------------------------------------------------------------------------

function TOCEntry({
  item,
  active,
  onClick,
}: {
  item: TOCItem;
  active: string;
  onClick?: () => void;
}) {
  const isActive = item.id === active;
  const hasActiveChild = item.children?.some((c) => c.id === active) ?? false;
  return (
    <li>
      <a
        href={`#${item.id}`}
        onClick={onClick}
        className={
          "block py-1.5 transition-colors " +
          (isActive
            ? "font-medium text-neutral-100"
            : hasActiveChild
              ? "text-neutral-200"
              : "text-neutral-500 hover:text-neutral-200")
        }
      >
        {item.label}
      </a>
      {item.children && (
        // Position sub-items grouped by phase with subtle dividers.
        // Phase eyebrow labels appear next to the first item in each
        // group so readers can see "this is the defense block."
        <ul className="ml-2 space-y-px border-l border-neutral-800/60 pl-3 font-mono text-[11px]">
          {item.children.map((child) => {
            const childActive = child.id === active;
            const phaseBreakBefore =
              child.id === "pos-CB" || child.id === "pos-K";
            const phaseLabel =
              child.id === "pos-QB"
                ? "offense"
                : child.id === "pos-CB"
                  ? "defense"
                  : child.id === "pos-K"
                    ? "special"
                    : null;
            return (
              <li key={child.id} className={phaseBreakBefore ? "mt-2" : ""}>
                <a
                  href={`#${child.id}`}
                  onClick={onClick}
                  className={
                    "block py-0.5 transition-colors " +
                    (childActive
                      ? "font-semibold text-neutral-100"
                      : "text-neutral-500 hover:text-neutral-200")
                  }
                  aria-current={childActive ? "true" : undefined}
                >
                  {child.label}
                  {phaseLabel && (
                    <span className="ml-2 text-[9px] uppercase tracking-wider text-neutral-700">
                      {phaseLabel}
                    </span>
                  )}
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}
