import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { Caption } from "../components/Caption";

/**
 * Shared scaffold for every clip scene. Instead of full-bleed footage
 * with text overlaid on top, the recording sits in a rounded "browser"
 * frame on the dark backdrop, with a two-tier Caption in its own band
 * below. This keeps the caption off the UI (legible + large) and reads
 * as a deliberate product demo rather than a raw screen capture.
 *
 * The frame is 1488x837 (16:9) — ~77% of the 1920-wide canvas — so the
 * recorded 1440x810 source scales cleanly. `startFrom` lets each scene
 * pick the most flattering window of its clip.
 */
export function ClipScene({
  src,
  kicker,
  caption,
  startFromFrames = 0,
}: {
  /** Filename inside `recordings/` (e.g. "clip-1.mp4"). */
  src: string;
  /** Mono accent line signalling the engineering behind the shot. */
  kicker?: string;
  caption: string;
  startFromFrames?: number;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Gentle scale settle for the framed unit. Opacity is intentionally
  // NOT animated here — scene entrances/exits are handled by the
  // crossfade transitions in Composition.tsx, and a second opacity
  // fade on top would dim the clip toward black mid-transition.
  const scale = interpolate(frame, [0, Math.round(fps * 0.5)], [0.98, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0a0a0a",
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        gap: 36,
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          width: 1488,
          height: 837,
          borderRadius: 18,
          overflow: "hidden",
          border: "1px solid #262626",
          boxShadow: "0 30px 80px rgba(0,0,0,0.55)",
          backgroundColor: "#000",
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFromFrames}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
      <Caption kicker={kicker} text={caption} />
    </AbsoluteFill>
  );
}
