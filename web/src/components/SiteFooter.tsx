import Link from "next/link";

import { Logo } from "./Logo";

/**
 * Site-wide footer. Three pieces of content:
 *
 *  1. Brand block — logo + name + one-line description so the footer
 *     still tells visitors what the site is even if they landed deep.
 *  2. Link columns — internal docs (Methodology / Research) + external
 *     project link (GitHub). Kept compact; no megafooter.
 *  3. Fine-print row — copyright, the NFL-disclaimer (required since
 *     we render team logos + names), data-source credit, and a build
 *     chip linking to the current commit on GitHub. The build chip is
 *     populated from `process.env.GIT_SHA`, captured in next.config.mjs
 *     at build time from either Vercel's injected SHA or local git.
 */
export function SiteFooter() {
  const sha = process.env.GIT_SHA ?? "";
  const shortSha = sha ? sha.slice(0, 7) : null;
  const year = new Date().getFullYear();

  return (
    <footer className="mt-12 border-t border-neutral-800 bg-neutral-950">
      <div className="mx-auto max-w-[1400px] px-6 py-7">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          {/* Brand block */}
          <div className="max-w-sm">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-sm font-semibold tracking-tight text-neutral-100 hover:text-white"
            >
              <Logo size={22} />
              NFL Player Grades
            </Link>
            <p className="mt-2 text-xs leading-relaxed text-neutral-500">
              Every NFL player on a 0–100 scale. Composite grades built from
              public play-by-play data, advanced metrics, and audited
              weights.
            </p>
          </div>

          {/* Link columns */}
          <div className="grid grid-cols-2 gap-x-10 gap-y-5 text-sm sm:grid-cols-3">
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                Grades
              </h3>
              <ul className="mt-2 space-y-1.5 text-neutral-300">
                <li>
                  <Link href="/" className="hover:text-white">
                    Player Grades
                  </Link>
                </li>
                <li>
                  <Link href="/teams" className="hover:text-white">
                    Team Grades
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                How it works
              </h3>
              <ul className="mt-2 space-y-1.5 text-neutral-300">
                <li>
                  <Link href="/methodology" className="hover:text-white">
                    Methodology
                  </Link>
                </li>
                <li>
                  <Link href="/methodology/audit" className="hover:text-white">
                    Research
                  </Link>
                </li>
              </ul>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                Project
              </h3>
              <ul className="mt-2 space-y-1.5 text-neutral-300">
                <li>
                  <a
                    href="https://github.com/shanethakkar/nfl-player-grades"
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 hover:text-white"
                  >
                    <GitHubIcon />
                    GitHub
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Fine print */}
        <div className="mt-6 flex flex-col gap-3 border-t border-neutral-900 pt-4 text-[11px] text-neutral-500 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-0.5">
            <p>
              © {year} NFL Player Grades. Not affiliated with the National
              Football League or any NFL team. All trademarks are property of
              their respective owners.
            </p>
            <p>
              Data via{" "}
              <a
                href="https://github.com/nflverse"
                target="_blank"
                rel="noreferrer noopener"
                className="underline-offset-2 hover:text-neutral-300 hover:underline"
              >
                nflverse
              </a>
              , Pro-Football-Reference, FTN, and NFL Next Gen Stats.
            </p>
          </div>
          {shortSha && (
            <a
              href={`https://github.com/shanethakkar/nfl-player-grades/commit/${sha}`}
              target="_blank"
              rel="noreferrer noopener"
              className="self-start rounded border border-neutral-800 px-2 py-1 font-mono text-[10px] text-neutral-400 hover:border-neutral-700 hover:text-neutral-200 sm:self-auto"
            >
              build {shortSha}
            </a>
          )}
        </div>
      </div>
    </footer>
  );
}

function GitHubIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
