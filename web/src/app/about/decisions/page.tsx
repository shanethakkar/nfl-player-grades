import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import { readAdrs, type AdrDoc } from "@/lib/docs";

export const metadata = {
  title: "Design decisions — NFL Player Grades",
  description:
    "Architecture decision records (ADRs) covering the structural choices made while building NFL Player Grades.",
};

/**
 * Design-decisions page (formerly the bottom half of /methodology).
 *
 * Renders every ADR from `docs/adr/*.md` in numeric order, each in a
 * `<section id="adr-NNNN">` so deep links from the rest of the site
 * (notably the `TeamContextPanel` ADR-0017 link) keep resolving.
 *
 * Server component — `fs` reads happen at render time. See
 * `web/src/lib/docs.ts` for the deploy-time caveat about reading
 * outside the `web/` tree.
 */
export default async function DecisionsPage() {
  const adrs = await readAdrs();

  return (
    <main className="mx-auto max-w-7xl px-6 py-10 lg:flex lg:gap-10">
      <Toc adrs={adrs} />
      <article className="min-w-0 flex-1">
        <div className="mb-2 text-xs uppercase tracking-wider text-neutral-500">
          About
        </div>
        <h1 className="mb-2 text-3xl font-semibold tracking-tight text-neutral-100">
          Design decisions
        </h1>
        <p className="max-w-3xl text-sm text-neutral-400">
          Architecture decision records (ADRs) — the technical choices
          behind the project, why we made each one, and what trade-offs
          we accepted. Append-only and numbered. If you want the
          consumer-facing explanation of how grades work, see{" "}
          <Link
            href="/methodology"
            className="underline decoration-dotted hover:text-neutral-100"
          >
            How grades work
          </Link>
          .
        </p>

        <AdrIndex adrs={adrs} />

        {adrs.map((adr) => (
          <AdrSection key={adr.num} adr={adr} />
        ))}
      </article>
    </main>
  );
}

/**
 * Sticky left-side ADR table of contents. Mobile collapses to a flat
 * list at the top of the page.
 */
function Toc({ adrs }: { adrs: AdrDoc[] }) {
  return (
    <aside className="mb-8 shrink-0 text-sm lg:sticky lg:top-6 lg:mb-0 lg:h-[calc(100vh-4rem)] lg:w-64 lg:overflow-y-auto lg:border-r lg:border-neutral-900 lg:pr-4">
      <div className="mb-2 text-xs uppercase tracking-wider text-neutral-500">
        ADRs
      </div>
      <ul className="space-y-1 text-neutral-400">
        {adrs.map((adr) => (
          <li key={adr.num}>
            <a
              href={`#adr-${adr.num}`}
              className="block truncate hover:text-neutral-100"
              title={`ADR-${adr.num} — ${adr.title}`}
            >
              <span className="font-mono text-neutral-500">{adr.num}</span>{" "}
              {adr.title}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function AdrIndex({ adrs }: { adrs: AdrDoc[] }) {
  return (
    <div className="mt-6 overflow-hidden rounded-lg border border-neutral-800">
      <table className="w-full text-sm">
        <thead className="bg-neutral-950 text-left text-xs uppercase tracking-wider text-neutral-500">
          <tr>
            <th className="px-4 py-2 font-medium">#</th>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-900">
          {adrs.map((adr) => (
            <tr key={adr.num} className="text-neutral-300">
              <td className="px-4 py-2 font-mono text-neutral-500">
                {adr.num}
              </td>
              <td className="px-4 py-2">
                <a
                  href={`#adr-${adr.num}`}
                  className="hover:text-neutral-100 hover:underline"
                >
                  {adr.title}
                </a>
              </td>
              <td className="px-4 py-2 text-neutral-500">{adr.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * One rendered ADR. The section carries a stable `id="adr-NNNN"`
 * (independent of rehype-slug's heading slugs) so deep links like
 * `/about/decisions#adr-0017` resolve even if the title changes.
 */
function AdrSection({ adr }: { adr: AdrDoc }) {
  return (
    <section
      id={`adr-${adr.num}`}
      className="mt-12 scroll-mt-6 border-t border-neutral-900 pt-8"
    >
      <div className="mb-1 text-xs uppercase tracking-wider text-neutral-500">
        ADR-{adr.num}
        {adr.date ? <span className="ml-2 normal-case">· {adr.date}</span> : null}
      </div>
      <h3 className="text-xl font-semibold tracking-tight text-neutral-100">
        {adr.title}
      </h3>
      <div className="mb-4 text-xs text-neutral-500">Status: {adr.status}</div>
      <div className={PROSE_CLASS}>
        <Markdown>{adr.body}</Markdown>
      </div>
    </section>
  );
}

/**
 * Shared prose class. Tuned for the dark site palette.
 */
const PROSE_CLASS =
  "prose prose-invert max-w-none prose-sm md:prose-base " +
  "prose-headings:tracking-tight prose-headings:text-neutral-100 " +
  "prose-h2:mt-10 prose-h2:text-xl prose-h2:font-semibold " +
  "prose-h3:mt-8 prose-h3:text-lg prose-h3:font-semibold " +
  "prose-h4:mt-6 prose-h4:text-base prose-h4:font-semibold " +
  "prose-p:text-neutral-300 prose-li:text-neutral-300 " +
  "prose-strong:text-neutral-100 " +
  "prose-a:text-neutral-100 prose-a:underline prose-a:decoration-dotted " +
  "hover:prose-a:text-white " +
  "prose-code:text-neutral-200 prose-code:before:content-none prose-code:after:content-none " +
  "prose-code:rounded prose-code:bg-neutral-900 prose-code:px-1 prose-code:py-0.5 " +
  "prose-pre:bg-neutral-950 prose-pre:border prose-pre:border-neutral-800 " +
  "prose-table:text-sm prose-th:text-neutral-200 prose-td:border-neutral-800 " +
  "prose-hr:border-neutral-900";

function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[
        rehypeSlug,
        [
          rehypeAutolinkHeadings,
          {
            behavior: "append",
            properties: {
              className:
                "ml-2 text-neutral-700 no-underline hover:text-neutral-400",
              ariaLabel: "Link to this section",
            },
            content: { type: "text", value: "#" },
          },
        ],
      ]}
    >
      {children}
    </ReactMarkdown>
  );
}
