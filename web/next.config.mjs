import { execSync } from "node:child_process";

// Capture the build's git SHA so the footer can show a "build XXXXXXX"
// link to the exact commit running in prod. Vercel injects
// VERCEL_GIT_COMMIT_SHA on every deploy; locally we fall back to
// reading `git rev-parse HEAD`. If neither works (e.g. running outside
// a repo), the footer just omits the build chip.
let gitSha = process.env.VERCEL_GIT_COMMIT_SHA || "";
if (!gitSha) {
  try {
    gitSha = execSync("git rev-parse HEAD").toString().trim();
  } catch {
    // Not in a git repo or git not installed; leave empty.
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typedRoutes: true,
  env: {
    GIT_SHA: gitSha,
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "a.espncdn.com",
        pathname: "/i/teamlogos/**",
      },
    ],
  },
  // Old `?season=` links (in-app shares, crawler indexes) move to
  // path-based URLs so the team pages can stay static/ISR.
  async redirects() {
    return [
      {
        source: "/teams",
        has: [{ type: "query", key: "season", value: "(?<season>\\d{4})" }],
        destination: "/teams/season/:season",
        permanent: true,
      },
      {
        source: "/teams/:abbr",
        has: [{ type: "query", key: "season", value: "(?<season>\\d{4})" }],
        destination: "/teams/:abbr/:season",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
