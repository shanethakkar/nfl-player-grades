import { ClipScene } from "./ClipScene";

/**
 * Clip 5 (3s) — Methodology page, TOC click scrolls to EDGE card.
 * Recording is 4s; use first 3s.
 */
export function Clip5Scene() {
  return (
    <ClipScene
      src="clip-5.mp4"
      kicker="Open methodology"
      caption="Every weight, documented."
    />
  );
}
