import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import { Logo } from "../components/Logo";

/**
 * Opening hook (0-6s) — Builder-POV.
 *
 * Reframed for a recruiter audience: lead with what *I built* and its
 * scale. Screen 2 leans into the real differentiator — open,
 * transparent grades with no black box — rather than a competitor.
 *
 * Screen 1 (0-3.2s): logo + kicker "BUILT SOLO · FROM SCRATCH" +
 *   headline "An NFL player grading engine." + a static scope row.
 *   Establishes that this is a real, substantial system, branded from
 *   the first frame.
 * Screen 2 (3.2-6s): headline "Free. Open. Validated." with
 *   "Every metric tested, every weight public." as subtext. The
 *   differentiator and the takeaway.
 *
 * The two screens crossfade. Scope numbers are static here (not
 * animated) so the counter moment stays unique to StatsScene.
 */
const SANS = "'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif";
const MONO = "'Geist Mono', ui-monospace, SF Mono, Menlo, Consolas, monospace";

export function HookScene() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s = (sec: number) => Math.round(fps * sec);

  // Screen 1: in over 0-0.3s, out over 2.85-3.2s.
  const s1Opacity = interpolate(
    frame,
    [0, s(0.3), s(2.85), s(3.2)],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const s1TranslateY = interpolate(
    frame,
    [s(2.85), s(3.2)],
    [0, -24],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Per-element stagger inside screen 1.
  const logoIn = elementIn(frame, s(0.0), s(0.35));
  const kickerIn = elementIn(frame, s(0.12), s(0.42));
  const headlineIn = elementIn(frame, s(0.3), s(0.62));
  const rowIn = elementIn(frame, s(0.55), s(0.9));

  // Screen 2: in over 3.1-3.5s, holds to the end.
  const s2Opacity = interpolate(
    frame,
    [s(3.1), s(3.5)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const headline2In = elementIn(frame, s(3.1), s(3.5));
  const sub2In = elementIn(frame, s(3.45), s(3.85));

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a" }}>
      {/* Screen 1 — what I built + scale */}
      <AbsoluteFill
        style={{
          opacity: s1Opacity,
          transform: `translateY(${s1TranslateY}px)`,
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 28,
          padding: "0 120px",
        }}
      >
        <div
          style={{
            opacity: logoIn.opacity,
            transform: `translateY(${logoIn.translateY}px)`,
            marginBottom: 4,
          }}
        >
          <Logo size={72} />
        </div>
        <div
          style={{
            opacity: kickerIn.opacity,
            transform: `translateY(${kickerIn.translateY}px)`,
            fontFamily: MONO,
            fontSize: 24,
            fontWeight: 600,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "#34d399",
          }}
        >
          Built solo · From scratch
        </div>
        <div
          style={{
            opacity: headlineIn.opacity,
            transform: `translateY(${headlineIn.translateY}px)`,
            fontFamily: SANS,
            fontSize: 86,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            color: "#fafafa",
            textAlign: "center",
            lineHeight: 1.05,
          }}
        >
          An NFL player grading engine.
        </div>
        <div
          style={{
            opacity: rowIn.opacity,
            transform: `translateY(${rowIn.translateY}px)`,
            fontFamily: SANS,
            fontSize: 30,
            fontWeight: 500,
            letterSpacing: "-0.01em",
            color: "#a3a3a3",
          }}
        >
          2,600+ players&nbsp;&nbsp;·&nbsp;&nbsp;12 positions&nbsp;&nbsp;·&nbsp;&nbsp;189 metrics&nbsp;&nbsp;·&nbsp;&nbsp;10 seasons
        </div>
      </AbsoluteFill>

      {/* Screen 2 — why it matters */}
      <AbsoluteFill
        style={{
          opacity: s2Opacity,
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 22,
          padding: "0 120px",
        }}
      >
        <div
          style={{
            opacity: headline2In.opacity,
            transform: `translateY(${headline2In.translateY}px)`,
            fontFamily: SANS,
            fontSize: 92,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            color: "#fafafa",
            textAlign: "center",
            lineHeight: 1.05,
          }}
        >
          Free. Open. Validated.
        </div>
        <div
          style={{
            opacity: sub2In.opacity,
            transform: `translateY(${sub2In.translateY}px)`,
            fontFamily: SANS,
            fontSize: 32,
            fontWeight: 500,
            letterSpacing: "-0.01em",
            color: "#a3a3a3",
          }}
        >
          Every metric tested. Every weight public.
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

/** Small fade + rise used to stagger elements within a screen. */
function elementIn(frame: number, start: number, end: number) {
  const opacity = interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(frame, [start, end], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return { opacity, translateY };
}
