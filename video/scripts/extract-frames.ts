/**
 * Extract evenly-spaced PNG frames from each clip so Claude (or any
 * reviewer) can inspect the visual content without playing the video.
 *
 * Output: `video/frames/clip-N/frame-NN.png` per clip — ~8 frames
 * each, named with their timestamp in milliseconds so it's clear
 * what point of the clip each one represents.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import ffmpegInstaller from "@ffmpeg-installer/ffmpeg";

const __dirname = dirname(fileURLToPath(import.meta.url));
const RECORDINGS_DIR = resolve(__dirname, "..", "recordings");
const FRAMES_DIR = resolve(__dirname, "..", "frames");

const CLIP_NUMBERS = [1, 2, 3, 4, 5];
// Timestamps to extract per clip. Covers the longest clip (~6s) with
// frames every 0.6s; shorter clips skip timestamps that exceed their
// duration.
const TIMESTAMPS = [
  0.0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.6, 4.2, 4.8, 5.4,
];

function getDurationSeconds(file: string): number {
  // ffprobe ships with @ffmpeg-installer/ffmpeg but not all installer
  // packages — fall back to running ffmpeg with -t parsing if needed.
  // Easier: just parse the file's display duration from ffmpeg's
  // stderr output (it always prints "Duration: HH:MM:SS.ms").
  const out = execFileSync(
    ffmpegInstaller.path,
    ["-i", file, "-hide_banner"],
    { stdio: ["ignore", "pipe", "pipe"] },
  ).toString();
  // Actually ffmpeg errors-out without an output spec but writes to
  // stderr. Catch that and parse.
  const m = out.match(/Duration:\s+(\d+):(\d+):(\d+\.\d+)/);
  if (!m) return 4;
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
}

function extractFramesForClip(clipNum: number) {
  const input = resolve(RECORDINGS_DIR, `clip-${clipNum}.mp4`);
  if (!existsSync(input)) {
    console.warn(`[clip-${clipNum}] mp4 missing — run conversion first`);
    return;
  }
  const outDir = resolve(FRAMES_DIR, `clip-${clipNum}`);
  if (existsSync(outDir)) rmSync(outDir, { recursive: true });
  mkdirSync(outDir, { recursive: true });

  // Try every timestamp. ffmpeg silently produces a 0-byte or
  // duplicate-of-last-frame file when seeking past the end, which is
  // fine for our purposes — we just want as many real frames as
  // possible without parsing duration ahead of time.
  let extracted = 0;
  for (const t of TIMESTAMPS) {
    const msLabel = String(Math.round(t * 1000)).padStart(4, "0");
    const outPath = resolve(outDir, `frame-${msLabel}ms.png`);
    try {
      execFileSync(
        ffmpegInstaller.path,
        [
          "-ss",
          String(t),
          "-i",
          input,
          "-vframes",
          "1",
          "-q:v",
          "2",
          "-y",
          outPath,
        ],
        { stdio: "pipe" },
      );
      extracted++;
    } catch {
      // Seek past end — skip silently.
    }
  }
  console.log(`[clip-${clipNum}] extracted ${extracted} frames`);
}

for (const n of CLIP_NUMBERS) {
  extractFramesForClip(n);
}
console.log(`\nFrames written to ${FRAMES_DIR}`);
