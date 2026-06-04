/**
 * Clip 2 â€” Player profile with the career chart animating in (target
 * final length: 4s).
 *
 * Why this clip is tricky: Playwright records from context creation,
 * but the page is white during initial load (~2s on Vercel). The
 * chart's CSS line-draw + dots fade-in animations fire as soon as
 * the SVG mounts â€” which happens DURING the white screen. By the
 * time the page is visible, the animation has already finished, so
 * a naive recording captures a static chart.
 *
 * Fix: after the page is fully loaded + visible, clone-and-replace
 * the SVG element. Cloning resets the CSS animation state on the
 * new node, so the line draws again and the dots fade in â€” but now
 * the page is fully painted, so it's visible in the recording.
 *
 * Timing (recording is ~7s; trim ~3s in conversion):
 *   0 â€“ 3s    page loading (white screen, trimmed)
 *   3 â€“ 3.5s  hero + chart visible (static)
 *   3.5s      clone-and-replace SVG â†’ animation restarts
 *   3.5 â€“ 5s  line draws, dots fade in (chart-line is 700ms, dots
 *               fade-in completes ~1s after start)
 *   5 â€“ 7s    hold on the finished chart
 */

import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { BASE_URL, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../config.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIP_DIR = resolve(__dirname, "..", "recordings", "clip-2-raw");

async function main() {
  await rm(CLIP_DIR, { recursive: true, force: true });
  await mkdir(CLIP_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--force-color-profile=srgb",
    ],
  });

  const context = await browser.newContext({
    viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    deviceScaleFactor: 2,
    recordVideo: {
      dir: CLIP_DIR,
      size: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    },
  });

  const page = await context.newPage();

  console.log(`[clip-2] navigating to ${BASE_URL}/players/matthew-stafford`);
  await page.goto(`${BASE_URL}/players/matthew-stafford`, {
    waitUntil: "networkidle",
  });
  // Wait for the hero + chart to be in the DOM. The chart's
  // animations will have already run by this point.
  await page.waitForSelector("h1", { timeout: 10_000 });
  await page.waitForSelector("svg[aria-label*='Career grade']", {
    timeout: 10_000,
  });
  // Hold a moment on the loaded (already-painted) chart so the
  // recording has a clean static state to lead into the replay.
  await page.waitForTimeout(800);

  // ---- Restart the chart animation ----
  // First inject CSS that slows the line-draw + dot fade-in. The
  // production 700ms is right for a real visit but too quick when
  // isolated in a clip — the eye barely registers it. Stretching to
  // 1600ms makes the draw clearly visible and dramatic.
  // Then clone-and-replace the SVG so the CSS animations restart on
  // the new node.
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.textContent = `
      .chart-line  { animation: draw-line 1600ms cubic-bezier(0.2, 0.8, 0.2, 1) both !important; }
      .chart-point { animation: fade-in-delayed 1600ms ease-out both !important; }
    `;
    document.head.appendChild(style);
    const svg = document.querySelector(
      'svg[aria-label*="Career grade"]',
    );
    if (svg && svg.parentNode) {
      const clone = svg.cloneNode(true);
      svg.parentNode.replaceChild(clone, svg);
    }
  });

  // Hold long enough for: the slowed draw (~1.6s) + 3s static hold.
  // Total recording ~7s after page load.
  await page.waitForTimeout(4500);

  await context.close();
  await browser.close();
  console.log(`[clip-2] done â€” video saved under ${CLIP_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
