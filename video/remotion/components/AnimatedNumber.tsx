import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Counter that ticks from 0 to `target` with a spring-based easing,
 * then holds. The visual reads as "the system computed this number."
 */
export function AnimatedNumber({
  target,
  durationFrames,
  formatter = (n) => String(Math.round(n)),
}: {
  target: number;
  /** How long to spend ticking up; after that, value stays at target. */
  durationFrames: number;
  /** Custom formatter — e.g. add commas, plus signs, etc. */
  formatter?: (value: number) => string;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring eases the value naturally — fast at first, decelerates to
  // the target instead of stopping abruptly.
  const progress = spring({
    frame,
    fps,
    config: {
      damping: 200,
      stiffness: 90,
      mass: 0.6,
    },
    durationInFrames: durationFrames,
  });
  const value = interpolate(progress, [0, 1], [0, target]);

  return <>{formatter(value)}</>;
}
