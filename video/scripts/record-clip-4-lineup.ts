/**
 * Clip 4 â€” Rams team profile with the lineup diagram (target final
 * length: 3s).
 *
 * What it shows:
 *   1. Land on /teams/LA. Team grade card is visible at the top.
 *   2. Smooth-scroll down so the lineup diagram is centered in the
 *      viewport.
 *   3. Hold on the formation.
 *
 * Timing budget (raw, ~5s; trim ~2.5s at start in conversion):
 *   0.0 â€“ 0.5s   page settled, team grade card visible
 *   0.5 â€“ 1.5s   smooth scroll to lineup section
 *   1.5 â€“ 4.5s   hold on the formation (the formation is the visual
 *                  hero â€” let it breathe)
 */

import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { BASE_URL, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../config.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIP_DIR = resolve(__dirname, "..", "recordings", "clip-4-raw");

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

  console.log(`[clip-4] navigating to ${BASE_URL}/teams/LA`);
  await page.goto(`${BASE_URL}/teams/LA`, { waitUntil: "networkidle" });
  // Wait for the team profile h1 + the team grade card to render.
  await page.waitForSelector("h1", { timeout: 10_000 });
  // Brief hold on the top of the profile.
  await page.waitForTimeout(500);

  // â”€â”€ BEAT: smooth scroll to the starting-lineup section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Force smooth scrolling for the recording (default browser
  // behavior would be instant). Find the h2 with text "Starting
  // lineup" â€” that's the section header above the formation diagram.
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = "smooth";
    const headings = Array.from(document.querySelectorAll("h2"));
    const target = headings.find((h) =>
      h.textContent?.toLowerCase().includes("starting lineup"),
    );
    if (target) {
      // Scroll the section's *next sibling* (the formation diagram
      // itself) into view so the field is what's centered, not just
      // the h2.
      const diagram = target.nextElementSibling ?? target;
      diagram.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // Hold on the formation â€” the diagram is the visual hero of the
  // clip and needs time to be read.
  await page.waitForTimeout(3500);

  await context.close();
  await browser.close();
  console.log(`[clip-4] done â€” video saved under ${CLIP_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
