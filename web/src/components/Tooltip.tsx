"use client";

import { useRef, useState } from "react";

type Props = {
  content: string;
  children: React.ReactNode;
  direction?: "up" | "down";
};

const LONG_PRESS_MS = 450;

export function Tooltip({ content, children, direction = "up" }: Props) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tracks whether the last interaction was touch so synthesized mouse events
  // fired by mobile browsers after touchend don't re-open the tooltip.
  const touchActiveRef = useRef(false);

  function computePos(): { x: number; y: number } | null {
    if (!ref.current) return null;
    const r = ref.current.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    return {
      x: Math.max(114, Math.min(cx, window.innerWidth - 114)),
      y: direction === "up" ? r.top - 8 : r.bottom + 8,
    };
  }

  function clearTimer() {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  // ── Desktop mouse events ──────────────────────────────────────────────────
  function onMouseEnter() {
    if (touchActiveRef.current) return;
    setPos(computePos());
  }

  function onMouseLeave() {
    if (touchActiveRef.current) return;
    setPos(null);
  }

  // ── Mobile touch events ───────────────────────────────────────────────────
  function onTouchStart() {
    touchActiveRef.current = true;
    clearTimer();
    timerRef.current = setTimeout(() => {
      setPos(computePos());
    }, LONG_PRESS_MS);
  }

  function onTouchEnd() {
    clearTimer();
    setPos(null);
    // Keep touchActiveRef true long enough to suppress the synthesized
    // mouseenter that mobile browsers fire ~300ms after touchend.
    setTimeout(() => { touchActiveRef.current = false; }, 600);
  }

  function onTouchMove() {
    // Finger moved — cancel the long-press and hide.
    clearTimer();
    setPos(null);
  }

  return (
    <span
      ref={ref}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      onTouchCancel={onTouchEnd}
      onTouchMove={onTouchMove}
      className="inline-flex"
    >
      {children}
      {pos && (
        <span
          style={{
            position: "fixed",
            left: pos.x,
            top: pos.y,
            transform: direction === "up" ? "translate(-50%, -100%)" : "translate(-50%, 0)",
            zIndex: 9999,
          }}
          className="pointer-events-none w-52 animate-pop-in whitespace-pre-line rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs font-normal normal-case leading-relaxed tracking-normal text-neutral-300 shadow-lg"
        >
          {content}
          <span
            className={[
              "absolute left-1/2 -translate-x-1/2 border-4 border-transparent",
              direction === "up" ? "top-full border-t-neutral-700" : "bottom-full border-b-neutral-700",
            ].join(" ")}
          />
        </span>
      )}
    </span>
  );
}
