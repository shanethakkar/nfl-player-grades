import { Composition } from "remotion";

import { Promo, PROMO_DURATION_FRAMES, PROMO_FPS } from "./Composition";

/**
 * Root registers every composition that Remotion's CLI/Studio can
 * render. There's just one: the 30s promo at 1920x1080 / 60fps.
 *
 * Recordings live at 1440x810 (16:9, what Playwright captured) — at
 * 1920x1080 the clips render upscaled but at 2x deviceScaleFactor
 * (we set this on the Playwright context), so the source pixels are
 * actually 2880x1620 and the result is sharp.
 */
export function Root() {
  return (
    <>
      <Composition
        id="Promo"
        component={Promo}
        durationInFrames={PROMO_DURATION_FRAMES}
        fps={PROMO_FPS}
        width={1920}
        height={1080}
      />
    </>
  );
}
