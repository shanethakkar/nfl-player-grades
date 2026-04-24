import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";

/**
 * Reads markdown documentation from the repo's docs/ folder at render
 * time. We keep .md as the source of truth (so `docs/methodology.md`
 * and the ADRs render identically on GitHub and on the site) rather
 * than duplicating content into MDX.
 *
 * NOTE: `process.cwd()` is the `web/` directory during `next dev` and
 * `next build`, so `../docs` resolves to the repo's docs folder. If we
 * ever deploy to Vercel, the build must copy `docs/` into the
 * deployable tree (or we can switch to reading at build time via a
 * generated module). For now the local workflow is fine.
 */

const DOCS_ROOT = path.resolve(process.cwd(), "..", "docs");

export type AdrDoc = {
  /** Zero-padded 4-digit number from the filename (e.g. "0017"). */
  num: string;
  /** Full ADR title without the leading `NNNN - ` prefix. */
  title: string;
  /** Parsed from the `- **Status**: ...` line; falls back to "Unknown". */
  status: string;
  /** Parsed from `- **Date**: YYYY-MM-DD`; may be null. */
  date: string | null;
  /**
   * Markdown body with the h1 title line stripped — the page supplies
   * its own section heading so we avoid a duplicate h1 inside each
   * ADR.
   */
  body: string;
};

/**
 * The methodology body with its leading `# Methodology` h1 stripped so
 * the page can supply its own top-level heading.
 */
export async function readMethodology(): Promise<string> {
  const raw = await fs.readFile(path.join(DOCS_ROOT, "methodology.md"), "utf8");
  return stripLeadingH1(raw);
}

/**
 * All ADRs under docs/adr/ in numeric order. Ignores README.md (which
 * is a hand-written index of the folder, not an ADR).
 */
export async function readAdrs(): Promise<AdrDoc[]> {
  const dir = path.join(DOCS_ROOT, "adr");
  const entries = await fs.readdir(dir);
  const adrFiles = entries
    .filter((name) => /^\d{4}-.+\.md$/.test(name))
    .sort();

  const out: AdrDoc[] = [];
  for (const name of adrFiles) {
    const raw = await fs.readFile(path.join(dir, name), "utf8");
    out.push(parseAdr(name, raw));
  }
  return out;
}

function parseAdr(filename: string, raw: string): AdrDoc {
  const numMatch = filename.match(/^(\d{4})-/);
  const num = numMatch ? numMatch[1] : "????";

  const lines = raw.split(/\r?\n/);
  const h1Idx = lines.findIndex((l) => l.startsWith("# "));
  const titleRaw = h1Idx >= 0 ? lines[h1Idx].replace(/^#\s+/, "") : filename;
  // Title lines look like "0017 - v1 face-check: ..." — drop the leading number.
  const title = titleRaw.replace(/^\d{4}\s*[-—–]\s*/, "").trim();

  const status =
    matchMetaLine(lines, "Status") ?? "Unknown";
  const date = matchMetaLine(lines, "Date");

  // Strip the h1 line from the body — the section header renders it.
  const body =
    h1Idx >= 0
      ? [...lines.slice(0, h1Idx), ...lines.slice(h1Idx + 1)].join("\n").trimStart()
      : raw;

  return { num, title, status, date, body };
}

/**
 * Matches `- **Key**: value` lines in the ADR front-matter block and
 * returns the trimmed value, or null if not found.
 */
function matchMetaLine(lines: string[], key: string): string | null {
  const re = new RegExp(`^[-*]\\s+\\*\\*${key}\\*\\*:\\s*(.+?)\\s*$`);
  for (const line of lines) {
    const m = line.match(re);
    if (m) return m[1];
  }
  return null;
}

function stripLeadingH1(raw: string): string {
  const lines = raw.split(/\r?\n/);
  const h1Idx = lines.findIndex((l) => l.startsWith("# "));
  if (h1Idx === -1) return raw;
  return [...lines.slice(0, h1Idx), ...lines.slice(h1Idx + 1)]
    .join("\n")
    .trimStart();
}
