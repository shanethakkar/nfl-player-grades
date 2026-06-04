import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Two-tier caption shown *below* the framed clip (not overlaid on it).
 *
 * Tier 1 — a small mono "kicker" in the brand accent that signals the
 *   engineering behind the shot (scale, scope, or a capability).
 * Tier 2 — a larger sans line describing what's on screen.
 *
 * Lives in normal flow inside ClipScene's flex column, so it never
 * fights the UI for legibility and can be sized large for phone
 * viewing. Fades + rises in, then fades out as the scene ends.
 */
const SANS = "'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif";
const MONO = "'Geist Mono', ui-monospace, SF Mono, Menlo, Consolas, monospace";

export function Caption({ kicker, text }: { kicker?: string; text: string }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fadeInFrames = Math.round(fps * 0.25);
  const fadeOutFrames = Math.round(fps * 0.2);
  const fadeOutStart = durationInFrames - fadeOutFrames;

  const opacity = interpolate(
    frame,
    [0, fadeInFrames, fadeOutStart, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const translateY = interpolate(
    frame,
    [0, fadeInFrames],
    [12, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translateY}px)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        textAlign: "center",
        maxWidth: 1488,
      }}
    >
      {kicker ? (
        <div
          style={{
            fontFamily: MONO,
            fontSize: 22,
            fontWeight: 600,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "#34d399",
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div
        style={{
          fontFamily: SANS,
          fontSize: 50,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          color: "#fafafa",
          lineHeight: 1.1,
        }}
      >
        {text}
      </div>
    </div>
  );
}
