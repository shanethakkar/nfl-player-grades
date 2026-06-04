import { AbsoluteFill, Audio, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";

import { Clip1Scene } from "./scenes/Clip1Scene";
import { Clip2Scene } from "./scenes/Clip2Scene";
import { Clip3Scene } from "./scenes/Clip3Scene";
import { Clip4Scene } from "./scenes/Clip4Scene";
import { Clip5Scene } from "./scenes/Clip5Scene";
import { HookScene } from "./scenes/HookScene";
import { OutroScene } from "./scenes/OutroScene";
import { StatsScene } from "./scenes/StatsScene";

export const PROMO_FPS = 60;

/**
 * Scene timing in seconds. Each scene holds noticeably longer than the
 * first cut of the promo — the goal is a calm, watchable pace where
 * each beat settles before moving on, rather than a fast highlight
 * reel. Scenes are stitched with gentle crossfades (see TRANSITION).
 *
 *   7    hook — logo + "An NFL player grading engine" → "Free. Open.
 *        Validated."
 *   6.5  clip 1 — leaderboard + position switch, held through the full
 *        WR settle (the earlier cut truncated this, which read as a
 *        jarring mid-switch jump)
 *   5    clip 2 — player profile + career chart, held on the drawn chart
 *   5.5  clip 3 — component breakdown: advanced machinery → percentile
 *        bars, each state held long enough to read
 *   4.5  clip 4 — Rams lineup diagram
 *   4.5  clip 5 — methodology TOC
 *   4.5  stats counter — numbers rest before the cut (trimmed 0.5s so
 *        the outro lands half a second earlier)
 *   4.5  outro — logo + URL + tagline
 *
 * Crossfades overlap adjacent scenes, so the rendered total is
 * (sum of scene seconds) − (number of transitions × TRANSITION).
 */
const TIMELINE = [
  { name: "hook", seconds: 7, Scene: HookScene },
  { name: "clip1", seconds: 6.5, Scene: Clip1Scene },
  { name: "clip2", seconds: 5, Scene: Clip2Scene },
  { name: "clip3", seconds: 5.5, Scene: Clip3Scene },
  { name: "clip4", seconds: 4.5, Scene: Clip4Scene },
  { name: "clip5", seconds: 4.5, Scene: Clip5Scene },
  { name: "stats", seconds: 4.5, Scene: StatsScene },
  { name: "outro", seconds: 4.5, Scene: OutroScene },
] as const;

// Crossfade length between scenes. 0.45s reads as a deliberate,
// premium dissolve without feeling sluggish.
const TRANSITION_SECONDS = 0.45;
const TRANSITION_FRAMES = Math.round(TRANSITION_SECONDS * PROMO_FPS);

const sceneFrames = (seconds: number) => Math.round(seconds * PROMO_FPS);

// TransitionSeries overlaps each transition with its neighbouring
// sequences, so the composition's total length subtracts one
// transition per gap between scenes.
const totalSceneFrames = TIMELINE.reduce(
  (sum, s) => sum + sceneFrames(s.seconds),
  0,
);
export const PROMO_DURATION_FRAMES =
  totalSceneFrames - (TIMELINE.length - 1) * TRANSITION_FRAMES;

export function Promo() {
  // TransitionSeries requires its Transition and Sequence elements to
  // be DIRECT children, so we build a single flat array (a leading
  // crossfade before every scene except the first) rather than wrapping
  // pairs in a helper component.
  const children = TIMELINE.flatMap((s, i) => {
    const sequence = (
      <TransitionSeries.Sequence
        key={s.name}
        durationInFrames={sceneFrames(s.seconds)}
      >
        <s.Scene />
      </TransitionSeries.Sequence>
    );
    if (i === 0) return [sequence];
    return [
      <TransitionSeries.Transition
        key={`${s.name}-transition`}
        presentation={fade()}
        timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
      />,
      sequence,
    ];
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a" }}>
      {/* Soundtrack plays from frame 0. Open-domain track (credit on
          post). It's a couple seconds shorter than the video, which is
          fine — it simply ends before the outro finishes. */}
      <Audio src={staticFile("soundtrack.mp3")} />
      <TransitionSeries>{children}</TransitionSeries>
    </AbsoluteFill>
  );
}
