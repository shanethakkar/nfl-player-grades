/**
 * Clip 3 — Per-component breakdown on a player profile (target final
 * length: 4s). The grade-explainability beat: every stat, its
 * percentile bar, its weight — and the raw machinery underneath.
 *
 * Reworked from the old "chart hover + team-chip nav" clip, which
 * tried to say two things at once and opened on the same profile view
 * as clip 2. This one has a single idea: "see every stat behind the
 * grade."
 *
 * Choreography (recording is ~7s; trim the white load preamble in
 * conversion):
 *   load        page paints (white preamble trimmed off in convert)
 *   scroll      bring the first season's breakdown table into frame
 *   hold        friendly view: stat / value / percentile bar / weight
 *   advanced    click "Show advanced" → raw / shrunk / z / weight cols
 *   friendly    click "Hide advanced" → friendly view remounts, so the
 *                 percentile bars grow back in on camera (slowed for
 *                 visibility, same trick as clip 2's chart replay)
 *
 * Toggling the React view (rather than clone-replacing the DOM like
 * clip 2) keeps React in control, so the remount-driven bar refill is
 * robust.
 */

import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { BASE_URL, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../config.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIP_DIR = resolve(__dirname, "..", "recordings", "clip-3-raw");

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

  console.log(`[clip-3] navigating to ${BASE_URL}/players/matthew-stafford`);
  await page.goto(`${BASE_URL}/players/matthew-stafford`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("h1", { timeout: 10_000 });
  // The component breakdown table is the heart of this clip.
  await page.waitForSelector("table", { timeout: 10_000 });

  // Slow the percentile-bar grow so the refill (triggered later by the
  // advanced→friendly remount) is clearly visible on camera. Prod is
  // 500ms — too quick to register when isolated in a clip.
  await page.addStyleTag({
    content: `.bar-grow { animation-duration: 1400ms !important; }`,
  });

  // Brief settle on the painted page.
  await page.waitForTimeout(400);

  // ── Scroll the breakdown into frame ───────────────────────────────
  // The "Show advanced" toggle sits just above the first season card.
  // Scroll it to ~80px from the top so the toggle stays visible (clicks
  // then don't trigger Playwright's auto-scroll jump) AND the first
  // card header + table rows fill the rest of the viewport below it.
  const toggle = page.getByRole("button", { name: /advanced/i });
  const box = await toggle.boundingBox();
  if (box) {
    await page.evaluate(
      (dy) => window.scrollBy({ top: dy, behavior: "smooth" }),
      box.y - 80,
    );
  }
  await page.waitForTimeout(1000);

  // Two long, well-separated beats (rather than three short ones) so
  // the kept window is robust to page-load timing variance, and so
  // each beat clearly reads at the downscaled video size.

  // ── BEAT 1: open on the raw machinery ─────────────────────────────
  // Raw / shrunk / z / weight for every component — the "proof" that
  // the grade is built from real, inspectable numbers. Held long
  // enough to read, not flashed.
  await toggle.click();
  await page.waitForTimeout(2800);

  // ── BEAT 2: back to friendly → percentile bars grow in on camera ──
  // The readable view; remounting it replays the (slowed) bar fill,
  // ending the clip on a long, settled hold of its most dynamic,
  // colourful moment.
  await page.getByRole("button", { name: /advanced/i }).click();
  await page.waitForTimeout(3200);

  await context.close();
  await browser.close();
  console.log(`[clip-3] done — video saved under ${CLIP_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
