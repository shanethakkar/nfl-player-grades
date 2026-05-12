import type React from "react";
import Link from "next/link";

import { componentDescription, componentLabel, gradeColor } from "@/lib/grades";
import {
  getCurrentTopAtPosition,
  getGradeTierExamples,
  type CurrentTopEntry,
  type GradeTierId,
  type TierBucket,
  type TierExample,
} from "@/lib/methodology";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "How grades work — NFL Player Grades",
  description:
    "Every NFL player on a 0-100 scale, computed from play-by-play data. Here's what goes into the number, what each tier means, and what we don't measure yet.",
};

// ---------------------------------------------------------------------------
// Per-position component lists (mirrors pipeline/grading/weights.py).
// Negative weights penalize the grade (e.g. fumble rate).
// ---------------------------------------------------------------------------

type ComponentEntry = { name: string; weight: number };

const POSITION_COMPONENTS: Record<string, ComponentEntry[]> = {
  QB: [
    { name: "qb_epa_per_dropback", weight: 0.50 },
    { name: "qb_cpoe",             weight: 0.25 },
    { name: "qb_success_rate",     weight: 0.25 },
  ],
  RB: [
    { name: "rb_ryoe_per_attempt",         weight:  0.28 },
    { name: "rb_rush_epa_per_attempt",     weight:  0.18 },
    { name: "rb_rush_success_rate",        weight:  0.14 },
    { name: "rb_rec_epa_per_target",       weight:  0.18 },
    { name: "rb_yac_over_expected_per_rec",weight:  0.12 },
    { name: "rb_catch_pct",                weight:  0.05 },
    { name: "rb_fumble_rate",              weight: -0.05 },
  ],
  WR: [
    { name: "wr_rec_epa_per_target",         weight:  0.35 },
    { name: "wr_yac_over_expected_per_rec",  weight:  0.27 },
    { name: "wr_separation",                 weight:  0.10 },
    { name: "wr_target_earn_rate",           weight:  0.10 },
    { name: "wr_success_rate_per_target",    weight:  0.08 },
    { name: "wr_fumble_rate",                weight: -0.05 },
  ],
  TE: [
    { name: "te_rec_epa_per_target",         weight:  0.35 },
    { name: "te_yac_over_expected_per_rec",  weight:  0.27 },
    { name: "te_separation",                 weight:  0.07 },
    { name: "te_target_earn_rate",           weight:  0.10 },
    { name: "te_success_rate_per_target",    weight:  0.08 },
    { name: "te_fumble_rate",                weight: -0.05 },
  ],
};

// ---------------------------------------------------------------------------
// Z-score → grade lookup (sigmoid: grade = 100 / (1 + e^{-1.15z})).
// ---------------------------------------------------------------------------

const Z_GRADE_EXAMPLES = [-2, -1, 0, 1, 2].map((z) => ({
  z,
  label: z > 0 ? `+${z}` : String(z),
  grade: Math.round(100 / (1 + Math.exp(-1.15 * z))),
}));

/**
 * Consumer-facing methodology page.
 *
 * Audience: an NFL fan who clicked the "methodology" link from a player
 * grade. They want to know what's measured, what the scale means, and
 * what the limitations are. Technical rationale lives at /about/decisions.
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
      components: POSITION_COMPONENTS.QB,
      top: qbTop,
    },
    {
      position: "RB",
      headline: "Running back",
      components: POSITION_COMPONENTS.RB,
      top: rbTop,
    },
    {
      position: "WR",
      headline: "Wide receiver",
      components: POSITION_COMPONENTS.WR,
      top: wrTop,
    },
    {
      position: "TE",
      headline: "Tight end",
      components: POSITION_COMPONENTS.TE,
      teNote: true,
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
        Every NFL player on a 0–100 scale, computed from play-by-play
        data. Here&apos;s what goes into the number.
      </p>
    </header>
  );
}

// ---------------------------------------------------------------------------
// The grade scale — gradient bar + vertical band of tiers with examples.
// ---------------------------------------------------------------------------

function GradeScale({ tiers }: { tiers: TierBucket[] }) {
  return (
    <section className="mb-16">
      <SectionHeading eyebrow="The scale" title="What each grade means" />
      {/* Change 3: continuous color ramp so the reader sees the full spectrum before reading. */}
      <div className="mb-4 h-2 rounded-full bg-gradient-to-r from-red-500 via-yellow-400 to-emerald-400" />
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
          tier.examples.map((ex) => (
            <ExampleChip key={`${ex.player_id}:${ex.season}`} ex={ex} />
          ))
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

const TIER_ACCENT: Record<GradeTierId, { text: string; borderL: string }> = {
  "tier-90":     { text: "text-emerald-400", borderL: "border-l-4 border-l-emerald-500/60" },
  "tier-80":     { text: "text-green-400",   borderL: "border-l-4 border-l-green-500/60" },
  "tier-70":     { text: "text-lime-400",    borderL: "border-l-4 border-l-lime-500/60" },
  "tier-60":     { text: "text-yellow-400",  borderL: "border-l-4 border-l-yellow-500/60" },
  "tier-50":     { text: "text-orange-400",  borderL: "border-l-4 border-l-orange-500/60" },
  "tier-sub-50": { text: "text-red-400",     borderL: "border-l-4 border-l-red-500/60" },
};

// ---------------------------------------------------------------------------
// Position cards — weight chips instead of prose descriptions.
// ---------------------------------------------------------------------------

type PositionCardData = {
  position: "QB" | "RB" | "WR" | "TE";
  headline: string;
  components: ComponentEntry[];
  /** When true, renders a note about the blocking-TE path. */
  teNote?: boolean;
  top: { season: number | null; entries: CurrentTopEntry[] };
};

function PositionGrid({ positions }: { positions: PositionCardData[] }) {
  return (
    <section className="mb-16">
      <SectionHeading
        eyebrow="What gets measured"
        title="Each position has its own recipe"
      />
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

      {/* Change 1: weight chips replace the prose description paragraph. */}
      <div className="flex flex-wrap gap-1.5">
        {data.components.map((c) => (
          <WeightChip key={c.name} name={c.name} weight={c.weight} />
        ))}
      </div>
      {data.teNote && (
        <p className="mt-2 text-[11px] text-neutral-500">
          Pure blockers (&lt;15 targets): earn rate excluded from composite,
          weight redistributed to EPA + YAC.
        </p>
      )}

      <div className="mt-4 border-t border-neutral-900 pt-4">
        <CurrentTopBlock data={data} />
      </div>
    </article>
  );
}

function WeightChip({ name, weight }: ComponentEntry) {
  const label = componentLabel(name);
  const desc = componentDescription(name);
  const pct = Math.round(Math.abs(weight) * 100);
  const neg = weight < 0;
  return (
    <span className="group/chip relative">
      <span
        className={`inline-flex cursor-default items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${
          neg
            ? "border-red-900/60 bg-red-950/30 text-red-400"
            : "border-neutral-700 bg-neutral-900 text-neutral-300"
        }`}
      >
        <span>{label}</span>
        <span className={`font-mono font-semibold ${neg ? "text-red-400" : "text-neutral-500"}`}>
          {neg ? "−" : ""}{pct}%
        </span>
      </span>
      {desc && (
        <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-52 -translate-x-1/2 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs leading-relaxed text-neutral-300 opacity-0 shadow-lg transition-opacity duration-150 group-hover/chip:opacity-100">
          {desc}
          <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-neutral-700" />
        </span>
      )}
    </span>
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
// How a grade is built — trimmed step cards + z→grade visual on step 3.
// ---------------------------------------------------------------------------

function HowItsBuilt() {
  return (
    <section className="mb-16">
      <SectionHeading eyebrow="The pipeline" title="How a grade is built" />
      <div className="grid gap-5 sm:grid-cols-3">
        {/* Change 4: bodies trimmed to one tight sentence each. */}
        <Step
          n={1}
          title="Pull the raw numbers"
          body="Every play, every season — dropbacks, carries, targets. Garbage-time plays (win probability below 5% or above 95%) are filtered out."
        />
        <Step
          n={2}
          title="Shrink toward the mean"
          body="Low-sample numbers are pulled toward the position average in proportion to how little data there is — a 10-target season counts for less than a 100-target one."
        />
        <Step
          n={3}
          title="Compare to the field"
          body="Stats are z-scored within (season, position). The composite z is mapped to a grade via sigmoid:"
        >
          <p className="mt-2 rounded bg-neutral-900 px-2.5 py-1.5 font-mono text-[11px] text-neutral-400">
            grade = 100 / (1 + e^(−1.15z))
          </p>
          <div className="mt-3">
            <ZGradeStrip />
          </div>
        </Step>
      </div>
    </section>
  );
}

function Step({
  n,
  title,
  body,
  children,
}: {
  n: number;
  title: string;
  body: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-5">
      <div className="mb-2 font-mono text-xs uppercase tracking-wider text-neutral-500">
        Step {n}
      </div>
      <h3 className="mb-2 text-base font-semibold text-neutral-100">{title}</h3>
      <p className="text-sm leading-relaxed text-neutral-300">{body}</p>
      {children}
    </div>
  );
}

function ZGradeStrip() {
  return (
    <div className="grid grid-cols-5 gap-px overflow-hidden rounded-lg border border-neutral-800 text-center">
      {Z_GRADE_EXAMPLES.map(({ z, label, grade }) => (
        <div key={z} className="bg-neutral-950 px-1 py-2.5">
          <div className={`font-mono text-lg font-bold leading-none ${gradeColor(grade)}`}>
            {grade}
          </div>
          <div className="mt-1 font-mono text-[10px] text-neutral-500">
            z={label}
          </div>
        </div>
      ))}
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
    <footer className="border-t border-neutral-900 pt-8">
      <Link
        href="/about/decisions"
        className="inline-flex items-center gap-2 rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-400 transition-colors hover:border-neutral-500 hover:text-neutral-100"
      >
        Design decisions
        <span aria-hidden>→</span>
      </Link>
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
