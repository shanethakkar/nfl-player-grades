/**
 * Clip 5 â€” Methodology page with TOC navigation to EDGE (target final
 * length: 3s).
 *
 * What it shows:
 *   1. Land on /methodology â€” top of the page with the right-rail TOC
 *      visible (1440px viewport is well above the lg: breakpoint).
 *   2. Cursor moves to the EDGE link in the TOC.
 *   3. Click â€” page smooth-scrolls down to the EDGE position card.
 *   4. Hold on the EDGE card so the weight chips read.
 *
 * Timing budget (raw, ~6s; trim ~2.5s at start in conversion):
 *   0.0 â€“ 0.6s   page settled, top of methodology + TOC visible
 *   0.6 â€“ 1.0s   cursor moves to EDGE TOC link
 *   1.0 â€“ 1.5s   click â€” smooth scroll begins
 *   1.5 â€“ 3.0s   scroll completes
 *   3.0 â€“ 5.0s   hold on EDGE card (weight chips visible)
 */

import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { BASE_URL, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../config.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIP_DIR = resolve(__dirname, "..", "recordings", "clip-5-raw");

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

  console.log(`[clip-5] navigating to ${BASE_URL}/methodology`);
  await page.goto(`${BASE_URL}/methodology`, { waitUntil: "networkidle" });
  // Wait for the page header + a few position cards to render.
  await page.waitForSelector("h1", { timeout: 10_000 });
  await page.waitForSelector("#pos-EDGE", { timeout: 10_000 });

  // Force smooth scrolling so the anchor click animates instead of
  // jumping (CSS default for anchor links is instant).
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = "smooth";
  });
  // Brief hold on the top of the page (TOC + Hero visible).
  await page.waitForTimeout(600);

  // â”€â”€ BEAT: hover + click EDGE in the TOC â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // The desktop TOC sits in a sticky right-rail aside, with each
  // entry as an anchor link. The EDGE link is inside the nested
  // Positions list. Locate the anchor by href.
  const edgeLink = page.locator('aside a[href="#pos-EDGE"]').first();
  await edgeLink.hover();
  await page.waitForTimeout(350);
  await edgeLink.click();

  // Smooth scroll takes ~700ms â€” hold so it completes, then hold
  // longer on the EDGE card so its weight chips read.
  await page.waitForTimeout(3000);

  await context.close();
  await browser.close();
  console.log(`[clip-5] done â€” video saved under ${CLIP_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
