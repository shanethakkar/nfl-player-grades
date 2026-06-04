/**
 * Clip 1 — Leaderboard + position switch (target final length: 5s).
 *
 * Approach: record long (~9s total) so the action timeline survives
 * the ~2-3s page-load white screen at the start. Trim aggressively
 * (3s) and cap at 6s in conversion so the kept window is exactly the
 * QB-paint → scroll → WR-switch sequence.
 *
 * Timing (recording, ~9s total):
 *   0 – 3s    page loading (white, trimmed)
 *   3 – 4s    QB leaderboard visible, holding
 *   4 – 5s    smooth scroll +120px
 *   5 – 6s    hold on scrolled QB
 *   6 – 6.5s  hover position picker
 *   6.5 – 7s  click WR
 *   7 – 9s    WR leaderboard visible
 *
 * After trim (-ss 3, -t 6) the clip is:
 *   0 – 1s    QB hold
 *   1 – 2s    scroll
 *   2 – 3s    hold
 *   3 – 3.5s  hover
 *   3.5 – 4s  click
 *   4 – 6s    WR leaderboard
 */

import { chromium } from "playwright";
import { mkdir, rm } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { BASE_URL, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../config.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLIP_DIR = resolve(__dirname, "..", "recordings", "clip-1-raw");

async function main() {
  // Wipe any prior recording so the converter doesn't pick up a
  // stale webm from a previous run.
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

  console.log(`[clip-1] navigating to ${BASE_URL}/?season=2025`);
  await page.goto(`${BASE_URL}/?season=2025`, { waitUntil: "networkidle" });
  await page.waitForSelector("table tbody tr", { timeout: 10_000 });

  // Force smooth scrolling for the scroll beat.
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = "smooth";
  });

  // ── BEAT 1: hold on QB leaderboard (~1s) ────────────────────────
  await page.waitForTimeout(1000);

  // ── BEAT 2: smooth scroll +120px (~1s) ──────────────────────────
  await page.evaluate(() => window.scrollTo({ top: 120, behavior: "smooth" }));
  await page.waitForTimeout(1000);

  // ── BEAT 3: hold on scrolled QB (~1s) ───────────────────────────
  await page.waitForTimeout(1000);

  // ── BEAT 4: hover WR pill (~0.5s) ───────────────────────────────
  const wrPill = page.getByRole("link", { name: "WR", exact: true }).first();
  await wrPill.hover();
  await page.waitForTimeout(500);

  // ── BEAT 5: click WR (~0.5s) ────────────────────────────────────
  await wrPill.click();
  await page.waitForURL(/position=WR/);
  await page.waitForSelector("table tbody tr", { timeout: 10_000 });

  // ── BEAT 6: hold on WR leaderboard (~2s) ────────────────────────
  await page.waitForTimeout(2000);

  await context.close();
  await browser.close();
  console.log(`[clip-1] done — video saved under ${CLIP_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
