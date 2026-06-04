/**
 * Remotion CLI config. Most defaults are fine — we just bump quality
 * settings for the final render (CRF 18 = visually lossless H.264).
 */
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// CRF 18 — visually lossless H.264. Output stays under ~30MB at 30s.
Config.setCodec("h264");
Config.setCrf(18);
Config.setPixelFormat("yuv420p");

// Serve the clip MP4s out of `recordings/` so `staticFile("clip-N.mp4")`
// resolves correctly without copying or symlinking them into a separate
// public/ folder.
Config.setPublicDir("./recordings");
