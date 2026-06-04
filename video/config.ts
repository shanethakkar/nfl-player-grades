/**
 * Shared config for all recording scripts.
 *
 * Recording against the production Vercel deploy means: no dev-server
 * compile pauses in the video, and ISR-cached pages load like real
 * users see them. If you ever want to record against a local build,
 * spin up `npm run build && npm start` in `web/` and set
 * `BASE_URL` to `http://localhost:3000`.
 */

// !! UPDATE if your prod URL is different !!
export const BASE_URL = "https://nfl-grades.shanethakkar.com";

// 16:9 at 1440x810 — fits comfortably on most laptop screens and
// renders out cleanly at 1920x1080 (1.33x scale) for the final video.
export const VIEWPORT_WIDTH = 1440;
export const VIEWPORT_HEIGHT = 810;

// 60fps so the chart line-draw + bar-fill animations look smooth.
// Playwright records to WebM at the configured FPS; we convert to MP4
// in the conversion step.
export const FPS = 60;
