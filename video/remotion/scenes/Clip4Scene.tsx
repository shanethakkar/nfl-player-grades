import { ClipScene } from "./ClipScene";

/**
 * Clip 4 (3s) — Rams team profile with the lineup diagram.
 * Recording is 4s; use first 3s.
 */
export function Clip4Scene() {
  return (
    <ClipScene
      src="clip-4.mp4"
      kicker="Team-level rollups"
      caption="Team grades roll up from the player data."
    />
  );
}
