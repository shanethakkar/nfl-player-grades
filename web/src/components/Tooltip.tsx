"use client";

import { useRef, useState } from "react";

type Props = {
  content: string;
  children: React.ReactNode;
  direction?: "up" | "down";
};

export function Tooltip({ content, children, direction = "up" }: Props) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const ref = useRef<HTMLSpanElement>(null);

  function show() {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    setPos({
      // clamp so 208px-wide tooltip (w-52) never overflows either edge
      x: Math.max(114, Math.min(cx, window.innerWidth - 114)),
      y: direction === "up" ? r.top - 8 : r.bottom + 8,
    });
  }

  return (
    <span ref={ref} onMouseEnter={show} onMouseLeave={() => setPos(null)} className="inline-flex">
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
          className="pointer-events-none w-52 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs font-normal normal-case leading-relaxed tracking-normal text-neutral-300 shadow-lg"
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
