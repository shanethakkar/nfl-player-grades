/**
 * Convert each clip's raw WebM (recorded by Playwright) into a
 * Remotion-friendly MP4, trimming the page-load white preamble off
 * the front.
 *
 * Why trim: Playwright starts recording as soon as the browser context
 * is created, so the first ~2 seconds of every clip is a white screen
 * while the page loads. We strip that off here so each MP4 starts on
 * the first painted frame of real content. Remotion gets clean inputs
 * and we don't have to think about `startFrom` offsets inside the
 * composition.
 *
 * Per-clip trim is configured below; each recording script's `await
 * page.goto(...).waitForLoadState("networkidle")` ends a roughly
 * predictable time after the recording begins, so the trim values are
 * empirically stable.
 *
 * Output: `recordings/clip-N.mp4` per clip.
 */

import { execFileSync } from "node:child_process";
import {
  existsSync,
  readdirSync,
  statSync,
  unlinkSync,
} from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import ffmpegInstaller from "@ffmpeg-installer/ffmpeg";

const __dirname = dirname(fileURLToPath(import.meta.url));
const RECORDINGS_DIR = resolve(__dirname, "..", "recordings");

// Per-clip trim configuration:
//   trim: seconds to skip at the start (page-load white screen)
//   keep: max seconds to keep from the trim point (0 = keep all)
//
// Trims are tuned empirically by inspecting frames after each
// recording. Page load on Vercel + Playwright is roughly 2.5-3s of
// white screen, after which the content paints.
const TRIM_CONFIG: Record<number, { trim: number; keep: number }> = {
  // Clip 1's action sequence runs ~9-10s of raw recording (load
  // ~4-5s, then hold/scroll/hold ~3s, then hover/click/WR ~3s).
  // Trimming 6s catches the action mid-flight so the kept 6s window
  // covers from "QB scrolled hold" through "WR leaderboard settled".
  1: { trim: 6.0, keep: 6.0 },
  // Clip 2's chart replay (slowed to 1.6s for visibility) starts
  // ~2.8s into the recording: page load (~2s) + 800ms pre-replay
  // hold. Trim 2s = ~800ms of static lead-in + animation + hold.
  2: { trim: 2.0, keep: 4.0 },
  // Clip 3 (component breakdown): long deliberate holds so neither
  // state feels flashed. Page load was slow this run (~3.5s); the
  // advanced view settles ~5.0s and holds to ~8.0s, then "Hide
  // advanced" → friendly percentile bars from ~8.3s. Trim 5.5s opens
  // on the settled advanced view; the kept 5.5s holds advanced ~2.5s,
  // toggles, then holds the settled bars ~2.7s and ends there. NOTE:
  // trim is tuned to this recording's load time — re-tune if you
  // re-record and the load preamble shifts.
  3: { trim: 5.5, keep: 5.5 },
  4: { trim: 1.5, keep: 4.0 },
  5: { trim: 1.5, keep: 4.0 },
};

// Each clip's raw recording lives in its own subdirectory because
// Playwright names video files by a hash. We find the .webm and use
// the first one we see.
function findRawWebm(clipNumber: number): string | null {
  const dir = resolve(RECORDINGS_DIR, `clip-${clipNumber}-raw`);
  if (!existsSync(dir)) return null;
  const files = readdirSync(dir).filter((f) => f.endsWith(".webm"));
  if (files.length === 0) return null;
  return resolve(dir, files[0]);
}

function convertClip(clipNumber: number) {
  const inputPath = findRawWebm(clipNumber);
  if (!inputPath) {
    console.warn(`[clip-${clipNumber}] no raw .webm found, skipping`);
    return;
  }
  const outputPath = resolve(RECORDINGS_DIR, `clip-${clipNumber}.mp4`);
  // Remove existing MP4 so ffmpeg doesn't prompt for overwrite.
  if (existsSync(outputPath)) unlinkSync(outputPath);

  const { trim, keep } = TRIM_CONFIG[clipNumber] ?? { trim: 0, keep: 0 };
  const sizeMB = (statSync(inputPath).size / 1024 / 1024).toFixed(2);
  console.log(
    `[clip-${clipNumber}] converting ${sizeMB}MB webm → mp4 (trim ${trim}s, keep ${keep}s)`,
  );

  // FFmpeg args:
  //   -ss {trim}     seek N seconds in before encoding
  //   -i {input}     source
  //   -t {keep}      cap output to this many seconds (omit if 0)
  //   -c:v libx264   H.264 (universal, Remotion-safe)
  //   -preset slow   better compression — small clips, time OK
  //   -crf 18        visually lossless quality
  //   -pix_fmt yuv420p  required for QuickTime / browsers
  //   -movflags +faststart  metadata at start for streaming
  //   -an            drop audio (music added in Remotion later)
  const args = [
    "-ss",
    String(trim),
    "-i",
    inputPath,
    ...(keep > 0 ? ["-t", String(keep)] : []),
    "-c:v",
    "libx264",
    "-preset",
    "slow",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    "-an",
    outputPath,
  ];
  execFileSync(ffmpegInstaller.path, args, { stdio: "inherit" });
  console.log(`[clip-${clipNumber}] → ${outputPath}`);
}

const requested = process.argv[2];
if (requested) {
  convertClip(Number(requested));
} else {
  for (const n of [1, 2, 3, 4, 5]) {
    convertClip(n);
  }
}
