import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import { Logo } from "../components/Logo";

/**
 * Outro (3s). Logo + product name + URL + tagline. The closing
 * "screenshot" the viewer takes away — and the thing that gets
 * shared if anyone pauses to copy the URL.
 *
 * !! UPDATE the URL if your prod domain changes. !!
 */
const URL = "nfl-grades.shanethakkar.com";
const TAGLINE = "Free. Open. Validated.";

export function OutroScene() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Everything fades + scales up softly together — feels like a card
  // settling in rather than separate elements popping.
  const opacity = interpolate(
    frame,
    [0, Math.round(fps * 0.5)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const scale = interpolate(
    frame,
    [0, Math.round(fps * 0.6)],
    [0.94, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const fontFamily =
    "'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif";
  const mono =
    "'Geist Mono', ui-monospace, SF Mono, Menlo, Consolas, monospace";

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
          opacity,
          transform: `scale(${scale})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
        }}
      >
        <Logo size={88} />
        <div
          style={{
            fontFamily,
            fontSize: 64,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            color: "#fafafa",
          }}
        >
          NFL Player Grades
        </div>
        <div
          style={{
            fontFamily: mono,
            fontSize: 30,
            color: "#737373",
            letterSpacing: "-0.01em",
          }}
        >
          {URL}
        </div>
        <div
          style={{
            marginTop: 18,
            padding: "10px 24px",
            border: "1px solid #404040",
            borderRadius: 999,
            fontFamily,
            fontSize: 22,
            fontWeight: 500,
            color: "#d4d4d4",
            letterSpacing: "0.02em",
          }}
        >
          {TAGLINE}
        </div>
      </div>
    </AbsoluteFill>
  );
}
