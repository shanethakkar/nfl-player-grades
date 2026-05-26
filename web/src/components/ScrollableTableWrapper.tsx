"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

/**
 * Wraps a wide table with a premium horizontal-scroll affordance:
 *  - Native scrollbar hidden (Firefox + WebKit) so the table looks clean
 *    when content fits, and avoids OS-level "always-on scrollbar" empty
 *    tracks (Windows in particular).
 *  - Soft right-edge fade gradient when there's content past the viewport,
 *    fading out smoothly when the user reaches the rightmost column. No
 *    left fade — sticky first columns already anchor the view.
 *  - Desktop: click-and-drag to pan (cursor: grab/grabbing). Mousedown on
 *    interactive descendants (links, sort headers, sparkline buttons) is
 *    ignored so existing click behavior keeps working. A small drag
 *    threshold (>4px) distinguishes pan from click; "moved" state is
 *    latched and suppresses the trailing click event so the user doesn't
 *    accidentally navigate when they meant to drag.
 *  - Mobile: native touch swipe handles scrolling; the JS mouse handlers
 *    don't fire, the fade still works.
 *
 * Used by both the player leaderboard (LeaderboardTable) and the team
 * leaderboard (TeamLeaderboardTable). Extract here so the two tables
 * share the affordance instead of drifting apart.
 */
export function ScrollableTableWrapper({ children }: { children: ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const drag = useRef({
    startX: 0,
    startScrollLeft: 0,
    active: false,
    moved: false,
  });

  const updateFades = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
  }, []);

  useEffect(() => {
    updateFades();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", updateFades, { passive: true });
    const ro = new ResizeObserver(updateFades);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateFades);
      ro.disconnect();
    };
  }, [updateFades]);

  useEffect(() => {
    // mousemove/mouseup live on window so the drag survives the cursor
    // leaving the wrapper mid-pan.
    const onMove = (e: MouseEvent) => {
      if (!drag.current.active) return;
      const dx = e.pageX - drag.current.startX;
      if (Math.abs(dx) > 4) drag.current.moved = true;
      if (scrollRef.current) {
        scrollRef.current.scrollLeft = drag.current.startScrollLeft - dx;
      }
      if (drag.current.moved) e.preventDefault();
    };
    const onUp = () => {
      if (!drag.current.active) return;
      drag.current.active = false;
      // Keep `moved` true through the trailing click event so we can
      // suppress it, then reset on the next tick.
      setTimeout(() => {
        drag.current.moved = false;
      }, 0);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const onMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    // Don't hijack drags that started on a clickable child.
    const target = e.target as HTMLElement;
    if (target.closest("a, button, input, [role='button'], select, textarea")) {
      return;
    }
    if (!scrollRef.current) return;
    drag.current = {
      startX: e.pageX,
      startScrollLeft: scrollRef.current.scrollLeft,
      active: true,
      moved: false,
    };
  };

  const onClickCapture = (e: React.MouseEvent) => {
    if (drag.current.moved) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  const canScroll = canScrollLeft || canScrollRight;

  return (
    <div className="relative w-max max-w-full overflow-hidden rounded-l-lg border-y border-l border-neutral-800 sm:rounded-lg sm:border-r">
      <div
        ref={scrollRef}
        onMouseDown={onMouseDown}
        onClickCapture={onClickCapture}
        className={
          "overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden " +
          (canScroll ? "cursor-grab active:cursor-grabbing" : "")
        }
      >
        {children}
      </div>
      {/* Right-edge fade: signals "more columns to the right". Auto-hides
          when there's no more content to scroll to. */}
      <div
        aria-hidden
        className={
          "pointer-events-none absolute inset-y-0 right-0 z-20 w-12 bg-gradient-to-l from-neutral-950 to-transparent transition-opacity duration-150 " +
          (canScrollRight ? "opacity-100" : "opacity-0")
        }
      />
    </div>
  );
}
