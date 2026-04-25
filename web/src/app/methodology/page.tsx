import Link from "next/link";

import { gradeColor } from "@/lib/grades";
import {
  getCurrentTopAtPosition,
  getGradeTierExamples,
  type CurrentTopEntry,
  type GradeTierId,
  type TierBucket,
  type TierExample,
} from "@/lib/methodology";

export const metadata = {
  title: "How grades work — NFL Player Grades",
  description:
    "Every NFL player on a 0-100 scale, computed from play-by-play data. Here's what goes into the number, what each tier means, and what we don't measure yet.",
};

/**
 * Consumer-facing methodology page.
 *
 * Audience: an NFL fan who clicked the "methodology" link from a player
 * grade. They want to know what's measured, what the scale means, and
 * what the limitations are. They don't care about version numbers,
 * scope language, or design rationale — that lives at /about/decisions.
 *
 * Server component: the grade scale and per-position cards pull live
 * data so they refresh automatically as new seasons come in.
 */
export default async function MethodologyPage() {
  const [tiers, qbTop, rbTop, wrTop, teTop] = await Promise.all([
    getGradeTierExamples(),
    getCurrentTopAtPosition("QB"),
    getCurrentTopAtPosition("RB"),
    getCurrentTopAtPosition("WR"),
    getCurrentTopAtPosition("TE"),
  ]);

  const positions: PositionCardData[] = [
    {
      position: "QB",
      headline: "Quarterback",
      description:
        "Three things — how many points each dropback added, how accurate they were beyond what's expected, and how often the play succeeded.",
      top: qbTop,
    },
    {
      position: "RB",
      headline: "Running back",
      description:
        "Six factors — yards over expected on each carry, points added per attempt, success rate, receiving value, catch rate, and ball security.",
      top: rbTop,
    },
    {
      position: "WR",
      headline: "Wide receiver",
      description:
        "Six factors — points per target, yards-after-catch beyond expected, separation from defenders, share of team targets earned, success rate when targeted, and ball security.",
      top: wrTop,
    },
    {
      position: "TE",
      headline: "Tight end",
      description:
        "Same six as receivers, with one twist — tight ends who are mostly blockers don't get penalized for low target volume. We classify each TE as receiving, balanced, or blocking based on usage.",
      top: teTop,
    },
  ];

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Hero />
      <GradeScale tiers={tiers} />
      <PositionGrid positions={positions} />
      <HowItsBuilt />
      <Limitations />
      <DataSource />
      <Footer />
    </main>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero() {
  return (
    <header className="mb-14">
      <h1 className="text-4xl font-semibold tracking-tight text-neutral-100 sm:text-5xl">
        How grades work
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-neutral-300">
        Every NFL player on a 0-100 scale, computed from play-by-play
        data. Here&apos;s what goes into the number.
      </p>
    </header>
  );
}

// ---------------------------------------------------------------------------
// The grade scale — vertical band of tiers, each with player examples.
// ---------------------------------------------------------------------------

function GradeScale({ tiers }: { tiers: TierBucket[] }) {
  return (
    <section className="mb-16">
      <SectionHeading eyebrow="The scale" title="What each grade means" />
      <p className="mb-6 max-w-2xl text-sm text-neutral-400">
        Examples are real player-seasons from the database. Click any
        name to see how their grade was built.
      </p>
      <div className="overflow-hidden rounded-xl border border-neutral-800">
        {tiers.map((tier) => (
          <TierRow key={tier.id} tier={tier} />
        ))}
      </div>
    </section>
  );
}

function TierRow({ tier }: { tier: TierBucket }) {
  const accent = TIER_ACCENT[tier.id];
  return (
    <div
      className={`flex flex-col gap-4 border-b border-neutral-900 px-5 py-5 last:border-b-0 sm:flex-row sm:items-center sm:gap-6 ${accent.borderL}`}
    >
      <div className="sm:w-44 sm:shrink-0">
        <div className={`font-mono text-2xl font-semibold ${accent.text}`}>
          {tier.range}
        </div>
        <div className="mt-1 text-sm text-neutral-400">{tier.label}</div>
      </div>
      <div className="flex flex-wrap gap-2">
        {tier.examples.length === 0 ? (
          <span className="text-xs text-neutral-600">
            No qualified seasons in this band yet.
          </span>
        ) : (
          tier.examples.map((ex) => <ExampleChip key={`${ex.player_id}:${ex.season}`} ex={ex} />)
        )}
      </div>
    </div>
  );
}

function ExampleChip({ ex }: { ex: TierExample }) {
  return (
    <Link
      href={{ pathname: `/players/${ex.player_id}` }}
      className="group inline-flex items-center gap-2 rounded-full border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-xs text-neutral-300 hover:border-neutral-600 hover:text-neutral-100"
    >
      <span className="font-medium">{ex.full_name}</span>
      <span className="text-neutral-500">
        {ex.position} · {ex.season}
      </span>
      <span className={`font-mono ${gradeColor(ex.composite_grade)}`}>
        {ex.composite_grade.toFixed(1)}
      </span>
    </Link>
  );
}

/**
 * Per-tier left-border + range-color accents. Kept separate from
 * `gradeColor()` because the grade-scale tiers don't line up exactly
 * with the leaderboard's text-color thresholds (e.g. 50-59 there is
 * yellow on top + orange on bottom).
 */
const TIER_ACCENT: Record<
  GradeTierId,
  { text: string; borderL: string }
> = {
  "tier-90":     { text: "text-emerald-400", borderL: "border-l-4 border-l-emerald-500/60" },
  "tier-80":     { text: "text-green-400",   borderL: "border-l-4 border-l-green-500/60" },
  "tier-70":     { text: "text-lime-400",    borderL: "border-l-4 border-l-lime-500/60" },
  "tier-60":     { text: "text-yellow-400",  borderL: "border-l-4 border-l-yellow-500/60" },
  "tier-50":     { text: "text-orange-400",  borderL: "border-l-4 border-l-orange-500/60" },
  "tier-sub-50": { text: "text-red-400",     borderL: "border-l-4 border-l-red-500/60" },
};

// ---------------------------------------------------------------------------
// Position cards — what gets measured per position.
// ---------------------------------------------------------------------------

type PositionCardData = {
  position: "QB" | "RB" | "WR" | "TE";
  headline: string;
  description: string;
  top: { season: number | null; entries: CurrentTopEntry[] };
};

function PositionGrid({ positions }: { positions: PositionCardData[] }) {
  return (
    <section className="mb-16">
      <SectionHeading
        eyebrow="What gets measured"
        title="Each position has its own recipe"
      />
      <p className="mb-6 max-w-2xl text-sm text-neutral-400">
        We measure the things that matter at each position. Plain
        English here; the exact weights live on the design-decisions
        page.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {positions.map((p) => (
          <PositionCard key={p.position} data={p} />
        ))}
      </div>
    </section>
  );
}

function PositionCard({ data }: { data: PositionCardData }) {
  return (
    <article className="flex flex-col rounded-lg border border-neutral-800 bg-neutral-950/40 p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="font-mono text-sm uppercase tracking-wider text-neutral-500">
          {data.position}
        </div>
        <h3 className="text-lg font-semibold text-neutral-100">
          {data.headline}
        </h3>
      </div>
      <p className="text-sm leading-relaxed text-neutral-300">
        {data.description}
      </p>
      <div className="mt-4 border-t border-neutral-900 pt-4">
        <CurrentTopBlock data={data} />
      </div>
    </article>
  );
}

function CurrentTopBlock({ data }: { data: PositionCardData }) {
  if (data.top.season === null || data.top.entries.length === 0) {
    return (
      <p className="text-xs text-neutral-500">
        No qualified {data.position} grades yet.
      </p>
    );
  }
  return (
    <div className="text-xs text-neutral-400">
      <div className="mb-2 uppercase tracking-wider text-neutral-500">
        Top {data.top.entries.length} this season ({data.top.season})
      </div>
      <ol className="space-y-1">
        {data.top.entries.map((e, i) => (
          <li key={e.player_id} className="flex items-center gap-2">
            <span className="w-4 text-neutral-600">{i + 1}.</span>
            <Link
              href={{ pathname: `/players/${e.player_id}` }}
              className="text-neutral-200 hover:text-neutral-100 hover:underline"
            >
              {e.full_name}
            </Link>
            <span className={`ml-auto font-mono ${gradeColor(e.composite_grade)}`}>
              {e.composite_grade.toFixed(1)}
            </span>
          </li>
        ))}
      </ol>
      <Link
        href={{
          pathname: "/",
          query: { season: data.top.season, position: data.position },
        }}
        className="mt-3 inline-block text-neutral-400 hover:text-neutral-100 hover:underline"
      >
        See full {data.position} leaderboard →
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// How a grade is built — three plain-language paragraphs.
// ---------------------------------------------------------------------------

function HowItsBuilt() {
  return (
    <section className="mb-16">
      <SectionHeading
        eyebrow="The pipeline"
        title="How a grade is built"
      />
      <div className="grid gap-5 sm:grid-cols-3">
        <Step
          n={1}
          title="Pull the raw numbers"
          body="We take every play of the season — dropbacks, carries, targets — and toss out garbage time so blowouts don't pad the stats."
        />
        <Step
          n={2}
          title="Give partial credit on small samples"
          body="A guy with 8 great targets doesn't outrank a guy with 100 good ones. Small-sample numbers get pulled toward the position average until there's enough evidence."
        />
        <Step
          n={3}
          title="Compare to the field"
          body="We compare each player to others at the same position that season. Closer to average means closer to a 50. About two standard deviations above the field lands around a 90."
        />
      </div>
    </section>
  );
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-5">
      <div className="mb-2 font-mono text-xs uppercase tracking-wider text-neutral-500">
        Step {n}
      </div>
      <h3 className="mb-2 text-base font-semibold text-neutral-100">
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-neutral-300">{body}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Honest limitations — what we don't measure yet.
// ---------------------------------------------------------------------------

function Limitations() {
  const items: { title: string; body: string }[] = [
    {
      title: "Opponent quality",
      body: "A great game against the worst defense grades the same as one against the best.",
    },
    {
      title: "QB context for receivers",
      body: "Great receivers stuck on terrible offenses look worse than the tape suggests. We flag this on the player page when it matters.",
    },
    {
      title: "Linemen and off-ball linebackers",
      body: "Public play-by-play data isn't there yet. Offensive line, defensive line, and most LB work doesn't show up cleanly in the numbers.",
    },
    {
      title: "Special teams",
      body: "Kickers, punters, returners, and coverage units are out of scope.",
    },
    {
      title: "Career trajectory smoothing",
      body: "Each season is graded standalone — no carry-over from prior years and no aging curve baked in.",
    },
  ];

  return (
    <section className="mb-16">
      <SectionHeading
        eyebrow="Known gaps"
        title="What we don't measure (yet)"
      />
      <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
        <ul className="space-y-4">
          {items.map((it) => (
            <li key={it.title} className="flex gap-3">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neutral-600" />
              <div>
                <div className="text-sm font-medium text-neutral-100">
                  {it.title}
                </div>
                <p className="text-sm text-neutral-400">{it.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Data source.
// ---------------------------------------------------------------------------

function DataSource() {
  return (
    <section className="mb-16">
      <SectionHeading
        eyebrow="Where the data comes from"
        title="Open, reproducible, and the same data the analysts use"
      />
      <p className="max-w-2xl text-sm leading-relaxed text-neutral-300">
        Every number on this site is computed from{" "}
        <a
          href="https://nflverse.nflverse.com/"
          className="underline decoration-dotted hover:text-neutral-100"
          target="_blank"
          rel="noopener noreferrer"
        >
          nflverse
        </a>{" "}
        — the same public play-by-play and Next Gen Stats feeds used by
        ESPN charts, academic research, and most football analytics
        writing. There are no proprietary grades, no scout opinions, and
        no hidden inputs. If you re-run our pipeline you get the same
        numbers.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Discreet footer link to the design-decisions page.
// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="border-t border-neutral-900 pt-8 text-xs text-neutral-500">
      For the technically curious: see our{" "}
      <Link
        href="/about/decisions"
        className="underline decoration-dotted hover:text-neutral-300"
      >
        design decisions
      </Link>
      .
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Shared section header.
// ---------------------------------------------------------------------------

function SectionHeading({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="mb-4">
      <div className="mb-1 text-xs uppercase tracking-wider text-neutral-500">
        {eyebrow}
      </div>
      <h2 className="text-2xl font-semibold tracking-tight text-neutral-100">
        {title}
      </h2>
    </div>
  );
}
