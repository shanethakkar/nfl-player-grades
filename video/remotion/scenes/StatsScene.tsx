import {
  AbsoluteFill,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { AnimatedNumber } from "../components/AnimatedNumber";

/**
 * Stats moment (5s). The "wow, that's a lot of work" beat.
 *
 * Layout: 2x2 grid of big numbers + small labels, staggered in. Each
 * cell uses its own `delayFrames` instead of an outer `<Sequence>`
 * because Sequence wraps children in AbsoluteFill, which collapses
 * onto the grid container and breaks CSS grid placement (all cells
 * stack at the first grid slot). Per-cell gating keeps the grid
 * flow intact AND staggers reveal.
 */
export function StatsScene() {
  const { fps } = useVideoConfig();
  const cellStagger = Math.round(fps * 0.5);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "60px 120px",
          maxWidth: 1300,
          width: "100%",
          padding: "0 80px",
        }}
      >
        <StatCell
          delayFrames={0 * cellStagger}
          value={2600}
          suffix="+"
          label="NFL players graded"
          color="#34d399"
        />
        <StatCell
          delayFrames={1 * cellStagger}
          value={189}
          label="metrics evaluated"
          color="#a3e635"
        />
        <StatCell
          delayFrames={2 * cellStagger}
          value={52}
          label="in production formulas"
          color="#facc15"
        />
        <StatCell
          delayFrames={3 * cellStagger}
          value={10}
          label="seasons of history"
          color="#fb923c"
        />
      </div>
    </AbsoluteFill>
  );
}

function StatCell({
  delayFrames,
  value,
  suffix = "",
  label,
  color,
}: {
  delayFrames: number;
  value: number;
  suffix?: string;
  label: string;
  color: string;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Local frame counter — counts up from 0 when this cell's delay
  // has elapsed. Used for the cell's fade/translate AND for the
  // counter's spring (so each cell ticks up at its own time).
  const localFrame = Math.max(0, frame - delayFrames);

  const opacity = interpolate(
    localFrame,
    [0, Math.round(fps * 0.2)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const translateY = interpolate(
    localFrame,
    [0, Math.round(fps * 0.3)],
    [16, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const fontFamily =
    "'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif";
  const mono =
    "'Geist Mono', ui-monospace, SF Mono, Menlo, Consolas, monospace";

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      <div
        style={{
          fontFamily: mono,
          fontSize: 140,
          fontWeight: 700,
          letterSpacing: "-0.04em",
          color,
          lineHeight: 1,
        }}
      >
        <CellNumber
          delayFrames={delayFrames}
          value={value}
          suffix={suffix}
        />
      </div>
      <div
        style={{
          marginTop: 14,
          fontFamily,
          fontSize: 26,
          fontWeight: 500,
          color: "#a3a3a3",
          letterSpacing: "-0.01em",
        }}
      >
        {label}
      </div>
    </div>
  );
}

/**
 * Wraps AnimatedNumber in a `<Sequence layout="none">` so the
 * counter's internal `useCurrentFrame()` resets to 0 at the cell's
 * delay point — the spring animation then plays correctly.
 *
 * `layout="none"` is critical: the default Sequence layout wraps in
 * AbsoluteFill which would collapse the inline number rendering.
 * With layout="none" the Sequence is a pure time-shifter with no
 * DOM wrapper.
 *
 * Pre-delay we render `0` directly so the cell isn't empty before
 * the counter starts.
 */
function CellNumber({
  delayFrames,
  value,
  suffix,
}: {
  delayFrames: number;
  value: number;
  suffix: string;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < delayFrames) {
    return <>0{suffix}</>;
  }
  return (
    <Sequence from={delayFrames} layout="none">
      <AnimatedNumber
        target={value}
        durationFrames={Math.round(fps * 1.2)}
        formatter={(n) =>
          `${new Intl.NumberFormat("en-US").format(Math.round(n))}${suffix}`
        }
      />
    </Sequence>
  );
}
