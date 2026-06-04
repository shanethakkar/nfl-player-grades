import { ClipScene } from "./ClipScene";

/**
 * Clip 2 (4s) — Player profile loads, career chart draws in.
 * Recording is 4s; the chart line begins drawing right at frame 0.
 */
export function Clip2Scene() {
  return (
    <ClipScene
      src="clip-2.mp4"
      kicker="10 seasons of history"
      caption="A grade for every season they've played."
    />
  );
}
