import "server-only";

import fs from "node:fs/promises";
import path from "node:path";

/**
 * Read a headshot PNG from /public/headshots/ and return a base64 data URL.
 * ImageResponse needs absolute URLs OR data URLs — data URL is the most
 * reliable across dev / preview / prod environments.
 *
 * Returns null when the file is missing (so OG endpoints can gracefully
 * fall back instead of throwing).
 */
export async function loadHeadshotDataUrl(playerId: number): Promise<string | null> {
  const filePath = path.join(
    process.cwd(),
    "public",
    "headshots",
    `${playerId}.png`,
  );
  try {
    const buffer = await fs.readFile(filePath);
    return `data:image/png;base64,${buffer.toString("base64")}`;
  } catch {
    return null;
  }
}

/** Tailwind-style emerald that matches the site's "elite" grade color. */
export const EMERALD = "#34d399";
export const YELLOW = "#facc15";
export const RED = "#f87171";
export const NEUTRAL_950 = "#0a0a0a";
export const NEUTRAL_900 = "#171717";
export const NEUTRAL_800 = "#262626";
export const NEUTRAL_400 = "#a3a3a3";
export const NEUTRAL_500 = "#737373";
export const NEUTRAL_300 = "#d4d4d4";
export const NEUTRAL_100 = "#f5f5f5";

/** Color for a grade — mirrors the site's gradeHex helper. */
export function gradeHex(grade: number): string {
  if (grade >= 90) return "#34d399";
  if (grade >= 80) return "#4ade80";
  if (grade >= 70) return "#a3e635";
  if (grade >= 55) return "#facc15";
  if (grade >= 40) return "#fb923c";
  return "#f87171";
}

/** The site's football logo, inlined as JSX so ImageResponse can render it. */
export function LogoMark({ size = 56 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="rotate(-22 32 32)">
        <path
          d="M 8 32 Q 32 8 56 32 Q 32 56 8 32 Z"
          fill="#7c2d12"
          stroke="#1a0a07"
          strokeWidth="1.5"
        />
        <line x1="22" y1="32" x2="42" y2="32" stroke="#fef3c7" strokeWidth="1.5" opacity="0.6" />
        <line x1="26" y1="27" x2="26" y2="37" stroke="#34d399" strokeWidth="3" strokeLinecap="round" />
        <line x1="32" y1="27" x2="32" y2="37" stroke="#facc15" strokeWidth="3" strokeLinecap="round" />
        <line x1="38" y1="27" x2="38" y2="37" stroke="#f87171" strokeWidth="3" strokeLinecap="round" />
      </g>
    </svg>
  );
}

/** Site header bar used across all OG cards (top edge). */
export function HeaderBar() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        paddingLeft: 56,
        paddingRight: 56,
        paddingTop: 36,
      }}
    >
      <LogoMark size={48} />
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          letterSpacing: "0.04em",
          color: NEUTRAL_100,
        }}
      >
        NFL Player Grades
      </div>
    </div>
  );
}

export const CARD_BG = NEUTRAL_950;
