import { ClipScene } from "./ClipScene";

/**
 * Clip 1 (5s) — Player grades leaderboard, QB → WR switch.
 * Recording is 6s; the QB transition starts visible from frame 0.
 */
export function Clip1Scene() {
  return (
    <ClipScene
      src="clip-1.mp4"
      kicker="12 positions · 2,600+ players"
      caption="Every player. Every position."
    />
  );
}
