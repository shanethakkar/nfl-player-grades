import Link from "next/link";

import { RejectionTable } from "@/components/audit/RejectionTable";
import {
  CRITERIA,
  FUNNEL,
  FUNNEL_TOTALS,
  LESSONS,
  REJECTION_HIGHLIGHTS,
  TEAM_AUDIT_FINDINGS,
  TEAM_PHASE_AUDIT,
  TEAM_POSITION_AUDIT,
  VALIDITY_SCOREBOARD,
  WR_AUDIT,
  WR_BEFORE_AFTER,
  type AuditCandidate,
  type TeamPhaseWeightRow,
  type TeamPositionWeightRow,
} from "@/lib/audit-data";

export const metadata = {
  title: "Research — How every weight was decided",
  description:
    "190+ metrics evaluated across 12 positions. 52 in production formulas. The audit framework, the case studies, and the full rejection log.",
};

export default function AuditPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <Hero />
      <FrameworkSection />
      <CaseStudySection />
      <ScoreboardSection />
      <AuditLogSection />
      <LessonsSection />
      <TeamWeightsSection />
      <Footer />
    </main>
  );
}

// ===========================================================================
// HERO
// ===========================================================================

function Hero() {
  return (
    <section className="mb-16 border-b border-neutral-800/60 pb-14">
      <div className="mb-4 inline-flex items-center gap-2 font-mono text-[11px] uppercase leading-none tracking-[0.15em] text-emerald-400/80">
        <span
          aria-hidden
          className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"
        />
        Research
      </div>
      <h1 className="mb-8 text-4xl font-semibold tracking-tight text-neutral-100 sm:text-5xl">
        How every weight was decided.
      </h1>
      <p className="mb-10 max-w-2xl text-lg leading-[1.75] text-neutral-300">
        Each player grade is a weighted composite of 2&ndash;7 statistical
        components. Picking those components &mdash; and choosing what to
        leave out &mdash; was the hard part. This is what we did, what we
        rejected, and what we learned.
      </p>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <BigStat
          number={`${FUNNEL_TOTALS.totalCandidates}+`}
          label="metrics evaluated"
          sublabel={`across ${FUNNEL_TOTALS.positions} positions`}
        />
        <BigStat
          number={String(FUNNEL_TOTALS.inFormula)}
          label="in production formulas"
          sublabel={`${Math.round((FUNNEL_TOTALS.inFormula / FUNNEL_TOTALS.totalCandidates) * 100)}% acceptance rate`}
        />
        <BigStat
          number="4"
          label="screening criteria"
          sublabel="reliability · spread · independence · validity"
        />
      </div>
    </section>
  );
}

function BigStat({
  number,
  label,
  sublabel,
}: {
  number: string;
  label: string;
  sublabel: string;
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/60 p-6">
      <div className="font-mono text-4xl font-semibold tracking-tight text-emerald-400">
        {number}
      </div>
      <div className="mt-2 text-sm font-medium text-neutral-200">{label}</div>
      <div className="mt-1 text-xs text-neutral-500">{sublabel}</div>
    </div>
  );
}

// ===========================================================================
// SECTION 1 — THE FRAMEWORK + WR AUDIT GRID
// ===========================================================================

function FrameworkSection() {
  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="The framework"
        title="Four criteria a metric must survive"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        For every plausible statistical metric in nflverse data, we score it
        against four criteria. A metric only enters a player&rsquo;s grade if
        all four are convincing. The criteria together rule out random noise,
        non-distinguishing stats, redundant signals, and metrics that nobody
        in the football world actually rewards.
      </p>

      <div className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-2">
        {CRITERIA.map((c, i) => (
          <CriterionCard key={c.key} idx={i + 1} criterion={c} />
        ))}
      </div>

      <SubHeading
        eyebrow="A worked example"
        title="What the audit looks like for WR"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Wide receiver got the largest metric set of any position &mdash;
        22 statistics tested. Six survived. Below, all 22 grouped by what
        the audit decided for each.
      </p>

      <WRAuditGrouped />
    </section>
  );
}

// ===========================================================================
// WR AUDIT — grouped by verdict (Shipped / Overlapped / Failed)
// ===========================================================================

function WRAuditGrouped() {
  const shipped = WR_AUDIT.filter((c) => c.verdict === "shipped").sort(
    (a, b) => Math.abs(b.weight ?? 0) - Math.abs(a.weight ?? 0),
  );
  const overlapped = WR_AUDIT.filter(
    (c) => c.verdict === "subsumed" || c.verdict === "redundant",
  ).sort((a, b) => Math.abs(b.maxR ?? 0) - Math.abs(a.maxR ?? 0));
  const failed = WR_AUDIT.filter(
    (c) =>
      c.verdict === "noise" ||
      c.verdict === "small-sample" ||
      c.verdict === "anti-skill",
  ).sort((a, b) => (b.yoyR ?? 0) - (a.yoyR ?? 0));

  return (
    <div className="space-y-6">
      <ShippedBlock items={shipped} />
      <OverlappedBlock items={overlapped} />
      <FailedBlock items={failed} />
    </div>
  );
}

function GroupHeader({
  count,
  label,
  blurb,
  tone,
}: {
  count: number;
  label: string;
  blurb: string;
  tone: "shipped" | "overlapped" | "failed";
}) {
  const colors = {
    shipped: {
      bar: "bg-emerald-500",
      badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    },
    overlapped: {
      bar: "bg-amber-500",
      badge: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    },
    failed: {
      bar: "bg-red-500",
      badge: "border-red-500/40 bg-red-500/10 text-red-300",
    },
  }[tone];
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <div className={"h-3 w-1 rounded-full " + colors.bar} />
      <h4 className="text-base font-semibold uppercase tracking-wider text-neutral-100">
        {label}
      </h4>
      <span
        className={"rounded border px-2 py-0.5 font-mono text-xs " + colors.badge}
      >
        {count}
      </span>
      <span className="text-sm text-neutral-400">— {blurb}</span>
    </div>
  );
}

function ShippedBlock({ items }: { items: AuditCandidate[] }) {
  return (
    <div>
      <GroupHeader
        count={items.length}
        label="Shipped in the formula"
        blurb="Passed all four criteria"
        tone="shipped"
      />
      <div className="overflow-hidden rounded-lg border border-emerald-500/20 bg-emerald-500/[0.03]">
        <table className="w-full text-sm">
          <thead className="bg-emerald-500/5 text-[11px] uppercase tracking-wider text-emerald-300/70">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Metric</th>
              <th className="px-2 py-2 text-right font-medium">Weight</th>
              <th className="px-2 py-2 text-right font-medium">YoY</th>
              <th className="px-2 py-2 text-right font-medium">x-sec</th>
              <th className="px-2 py-2 text-right font-medium">max |r|</th>
              <th className="px-2 py-2 text-right font-medium">Validity</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr
                key={c.name}
                className="border-t border-emerald-500/10"
                title={c.rationale}
              >
                <td className="px-4 py-2.5">
                  <div className="font-medium text-neutral-100">{c.displayName}</div>
                </td>
                <td className="px-2 py-2.5 text-right">
                  <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 font-mono text-xs text-emerald-300">
                    {(c.weight ?? 0) > 0 ? "+" : ""}
                    {(c.weight ?? 0).toFixed(2)}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-right">
                  <Heatcell value={c.yoyR} kind="yoy" />
                </td>
                <td className="px-2 py-2.5 text-right">
                  <Heatcell value={c.xsectStd} kind="xsect" />
                </td>
                <td className="px-2 py-2.5 text-right">
                  <Heatcell value={c.maxR} kind="independence" />
                </td>
                <td className="px-2 py-2.5 text-right">
                  <Heatcell value={c.validityR} kind="validity" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OverlappedBlock({ items }: { items: AuditCandidate[] }) {
  return (
    <div>
      <GroupHeader
        count={items.length}
        label="Overlapped a chosen metric"
        blurb="Either mathematically inside, or correlated > 0.5"
        tone="overlapped"
      />
      <div className="overflow-hidden rounded-lg border border-amber-500/20 bg-amber-500/[0.03]">
        <table className="w-full text-sm">
          <thead className="bg-amber-500/5 text-[11px] uppercase tracking-wider text-amber-300/70">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Metric</th>
              <th className="px-3 py-2 text-right font-medium">max |r|</th>
              <th className="px-4 py-2 text-left font-medium">Overlaps with</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr
                key={c.name}
                className="border-t border-amber-500/10"
                title={c.rationale}
              >
                <td className="px-4 py-2 text-neutral-200">{c.displayName}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-amber-200">
                  {(c.maxR ?? 0).toFixed(3)}
                </td>
                <td className="px-4 py-2 text-sm text-neutral-400">
                  {prettyComponent(c.maxRPartner)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FailedBlock({ items }: { items: AuditCandidate[] }) {
  return (
    <div>
      <GroupHeader
        count={items.length}
        label="Failed audit"
        blurb="Below noise floor, anti-skill, or too rare to grade"
        tone="failed"
      />
      <div className="overflow-hidden rounded-lg border border-red-500/20 bg-red-500/[0.03]">
        <table className="w-full text-sm">
          <thead className="bg-red-500/5 text-[11px] uppercase tracking-wider text-red-300/70">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Metric</th>
              <th className="px-3 py-2 text-right font-medium">YoY</th>
              <th className="px-4 py-2 text-left font-medium">Why excluded</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr
                key={c.name}
                className="border-t border-red-500/10"
                title={c.rationale}
              >
                <td className="px-4 py-2 text-neutral-200">{c.displayName}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-red-200">
                  {c.yoyR != null
                    ? (c.yoyR > 0 ? "+" : "") + c.yoyR.toFixed(3)
                    : "n/a"}
                </td>
                <td className="px-4 py-2 text-sm text-neutral-400">
                  {c.rationale}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Strip the "wr_" prefix and tidy underscores for display. */
function prettyComponent(name: string | null): string {
  if (!name) return "—";
  return name.replace(/^[a-z]+_/, "").replace(/_/g, " ");
}

function CriterionCard({
  idx,
  criterion,
}: {
  idx: number;
  criterion: (typeof CRITERIA)[number];
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-5">
      <div className="mb-2 flex items-baseline gap-3">
        <span className="font-mono text-xs text-neutral-500">0{idx}</span>
        <h3 className="text-lg font-semibold tracking-tight text-neutral-100">
          {criterion.title}
        </h3>
        <span className="text-xs uppercase tracking-wider text-neutral-500">
          {criterion.short}
        </span>
      </div>
      <p className="mb-3 text-sm leading-relaxed text-neutral-300">
        {criterion.plain}
      </p>
      <p className="text-xs leading-relaxed text-neutral-500">
        <span className="font-medium text-neutral-400">Technical:</span>{" "}
        {criterion.technical}
      </p>
    </div>
  );
}

// ===========================================================================
// HEATCELL — colored numeric cell, used by the Shipped block above
// ===========================================================================

function Heatcell({
  value,
  kind,
}: {
  value: number | null;
  kind: "yoy" | "xsect" | "independence" | "validity";
}) {
  if (value == null) {
    return <span className="font-mono text-xs text-neutral-600">n/a</span>;
  }

  // Per-criterion thresholds for green/amber/red
  let tone: "good" | "warn" | "bad";
  if (kind === "yoy") {
    tone = value >= 0.4 ? "good" : value >= 0.2 ? "warn" : "bad";
  } else if (kind === "xsect") {
    tone = value >= 0.1 ? "good" : value >= 0.04 ? "warn" : "bad";
  } else if (kind === "independence") {
    // Lower abs(r) is better here
    const ar = Math.abs(value);
    tone = ar < 0.5 ? "good" : ar < 0.75 ? "warn" : "bad";
  } else {
    // validity — sign-aware (negative for "lower is better" components is fine)
    const av = Math.abs(value);
    tone = av >= 0.2 ? "good" : av >= 0.1 ? "warn" : "bad";
  }

  const bgClass =
    tone === "good"
      ? "bg-emerald-500/15 text-emerald-200"
      : tone === "warn"
        ? "bg-amber-500/10 text-amber-200"
        : "bg-red-500/10 text-red-200";

  const formatted =
    Math.abs(value) >= 10
      ? value.toFixed(1)
      : value > 0
        ? "+" + value.toFixed(3)
        : value.toFixed(3);

  return (
    <span
      className={"inline-block rounded px-2 py-1 font-mono text-xs " + bgClass}
    >
      {formatted}
    </span>
  );
}

// ===========================================================================
// SECTION 2 — CASE STUDY: iDL before/after
// ===========================================================================

function CaseStudySection() {
  const v1Total = WR_BEFORE_AFTER.v1Weights.reduce(
    (s, w) => s + Math.abs(w.weight),
    0,
  );
  const v13Total = WR_BEFORE_AFTER.v13Weights.reduce(
    (s, w) => s + Math.abs(w.weight),
    0,
  );

  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="When the framework caught a flaw"
        title="WR: the most validity-driven signal was underweighted"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Methodology only earns trust by showing it changes when the data
        says it should. Most audit-driven changes are small &mdash; that&rsquo;s
        what makes them honest. Here&rsquo;s a representative one: WR v1
        weighted Receiving EPA most heavily because EPA is the comprehensive
        value number. The audit caught two more subtle things going on
        underneath that intuition.
      </p>

      <div className="mb-8 rounded-lg border border-amber-500/20 bg-amber-500/5 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-amber-300/80">
          The problem v1 had
        </div>
        <p className="text-neutral-200">{WR_BEFORE_AFTER.problem}</p>
      </div>

      <SubHeading
        eyebrow="The audit data"
        title="Target earn rate was the highest-validity WR metric"
      />
      <div className="mb-8 overflow-x-auto rounded-lg border border-neutral-800">
        <table className="w-full min-w-[600px] text-sm">
          <thead className="bg-neutral-900/60 text-xs uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Metric</th>
              <th className="px-4 py-3 text-right font-medium">
                Pro Bowl validity
              </th>
              <th className="px-4 py-3 text-right font-medium">
                Year-over-year r
              </th>
              <th className="px-4 py-3 text-right font-medium">Weight (v1 → v1.3)</th>
            </tr>
          </thead>
          <tbody>
            {WR_BEFORE_AFTER.finding.map((row) => (
              <tr key={row.metric} className="border-t border-neutral-800/60">
                <td className="px-4 py-3 font-medium text-neutral-200">
                  {row.metric}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-300">
                  +{row.validity.toFixed(3)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-300">
                  +{row.yoy.toFixed(3)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-300">
                  {row.weight}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        {WR_BEFORE_AFTER.conclusion}
      </p>

      <SubHeading eyebrow="The fix" title="Two weight changes, side-by-side" />
      <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        <FormulaCard
          title="WR v1"
          subtitle="Original — EPA-centric, target_earn as usage marker"
          weights={WR_BEFORE_AFTER.v1Weights}
          total={v1Total}
          tone="muted"
        />
        <FormulaCard
          title="WR v1.3"
          subtitle="After audit — target_earn elevated, success_rate trimmed"
          weights={WR_BEFORE_AFTER.v13Weights}
          total={v13Total}
          tone="active"
        />
      </div>

      <div className="mb-6 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-emerald-300/80">
          The result
        </div>
        <p className="text-neutral-200">
          {WR_BEFORE_AFTER.rebalanceImpact}
        </p>
      </div>

      <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-neutral-500">
          The takeaway
        </div>
        <p className="text-neutral-300">{WR_BEFORE_AFTER.takeaway}</p>
      </div>
    </section>
  );
}

function FormulaCard({
  title,
  subtitle,
  weights,
  total,
  tone,
}: {
  title: string;
  subtitle: string;
  weights: { name: string; display: string; weight: number }[];
  total: number;
  tone: "muted" | "active";
}) {
  const isActive = tone === "active";
  return (
    <div
      className={
        "rounded-lg border p-5 " +
        (isActive
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-neutral-800 bg-neutral-950/40")
      }
    >
      <div
        className={
          "mb-1 text-sm font-semibold " +
          (isActive ? "text-emerald-300" : "text-neutral-300")
        }
      >
        {title}
      </div>
      <div className="mb-4 text-xs text-neutral-500">{subtitle}</div>
      <ul className="space-y-2">
        {weights.map((w) => {
          const share = (Math.abs(w.weight) / total) * 100;
          const isPos = w.weight > 0;
          return (
            <li key={w.name} className="text-sm">
              <div className="mb-0.5 flex items-baseline justify-between gap-3">
                <span className="text-neutral-200">{w.display}</span>
                <span
                  className={
                    "font-mono text-xs " +
                    (isPos ? "text-neutral-300" : "text-orange-300")
                  }
                >
                  {isPos ? "+" : ""}
                  {w.weight.toFixed(2)}{" "}
                  <span className="text-neutral-500">
                    · {share.toFixed(0)}%
                  </span>
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-neutral-800/80">
                <div
                  className={
                    "h-full rounded-full " +
                    (isPos
                      ? isActive
                        ? "bg-emerald-400/70"
                        : "bg-neutral-500"
                      : "bg-orange-400/70")
                  }
                  style={{ width: `${share}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ===========================================================================
// SECTION 3 — VALIDITY SCOREBOARD
// ===========================================================================

function ScoreboardSection() {
  // Find max for bar width normalization
  const maxV = Math.max(
    ...VALIDITY_SCOREBOARD.map((r) => (r.validity != null ? r.validity : 0)),
  );

  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="The result, position by position"
        title="How well does each formula predict Pro Bowl voting?"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        After every weight is set, we test the composite grade against
        next-year Pro Bowl selection. It&rsquo;s an imperfect ground truth
        &mdash; voters have their biases &mdash; but it&rsquo;s the best
        public expert signal we have. The chart below makes the structural
        ceiling on each position clear.
      </p>

      <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
        <div className="space-y-3">
          {VALIDITY_SCOREBOARD.map((row) => (
            <ValidityBarRow key={row.position} row={row} maxV={maxV} />
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
        <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-4">
          <div className="mb-1 text-xs uppercase tracking-wider text-neutral-500">
            Why the bottom of the chart
          </div>
          <p className="text-neutral-300">
            LB, K, and P sit lowest because their Pro Bowl voting is heavily
            reputation-driven. Roquan Smith routinely makes the Pro Bowl on
            box-score numbers that don&rsquo;t scream elite. Only 2 K
            and 2 P slots exist per year &mdash; the smallest cohorts and
            noisiest voting on the board.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-4">
          <div className="mb-1 text-xs uppercase tracking-wider text-neutral-500">
            Why OL is N/A
          </div>
          <p className="text-neutral-300">
            There&rsquo;s no &ldquo;All-Pro OL unit&rdquo; award. Individual
            Pro Bowl OL counts per team are too noisy to use as a hard
            validation gate (some Pro Bowls go to bad-unit veterans on
            reputation). We documented this honestly rather than ginning
            up a weak proxy.
          </p>
        </div>
      </div>
    </section>
  );
}

function ValidityBarRow({
  row,
  maxV,
}: {
  row: (typeof VALIDITY_SCOREBOARD)[number];
  maxV: number;
}) {
  const pct = row.validity != null ? (row.validity / maxV) * 100 : 0;
  const color =
    row.validity == null
      ? "bg-neutral-700/50"
      : row.validity >= 0.35
        ? "bg-emerald-400/80"
        : row.validity >= 0.22
          ? "bg-emerald-500/60"
          : row.validity >= 0.17
            ? "bg-amber-400/70"
            : "bg-red-400/60";

  return (
    <div className="flex items-center gap-4">
      <div className="w-12 font-mono text-sm font-semibold text-neutral-200">
        {row.position}
      </div>
      <div className="flex-1">
        <div className="relative h-6 overflow-hidden rounded bg-neutral-900">
          <div
            className={"h-full rounded " + color}
            style={{
              width: row.validity != null ? `${pct}%` : "100%",
              opacity: row.validity == null ? 0.25 : 1,
            }}
          />
          <div className="absolute inset-0 flex items-center px-3 font-mono text-xs text-neutral-100/80">
            {row.validity != null ? `+${row.validity.toFixed(3)}` : "N/A"}
          </div>
        </div>
      </div>
      <div
        className="hidden w-72 text-xs text-neutral-500 md:block"
        title={row.ceilingNote}
      >
        {row.ceilingNote}
      </div>
    </div>
  );
}

// ===========================================================================
// SECTION 4 — AUDIT LOG (funnel + filterable rejection table)
// ===========================================================================

function AuditLogSection() {
  const maxCandidates = Math.max(...FUNNEL.map((r) => r.totalCandidates));

  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="The full audit log"
        title="What we considered, what we shipped, what we rejected"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        The articles in the analytics community usually show you the formula
        and tell you it&rsquo;s good. Here&rsquo;s what we did before
        landing on the formula. The funnel below shows how many metrics
        each position evaluated and how many made it into the live grade.
      </p>

      <div className="mb-12 rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
        <div className="mb-4 grid grid-cols-1 gap-2 text-xs uppercase tracking-wider text-neutral-500 sm:grid-cols-[60px_1fr_60px]">
          <div>Position</div>
          <div>Evaluated &rarr; in formula</div>
          <div className="text-right">In/Out</div>
        </div>
        <div className="space-y-2">
          {FUNNEL.map((row) => (
            <FunnelRow key={row.position} row={row} max={maxCandidates} />
          ))}
        </div>
        <div className="mt-6 border-t border-neutral-800 pt-4 font-mono text-sm text-neutral-300">
          <span className="text-neutral-500">Total &middot;</span>{" "}
          <span className="text-emerald-300">
            {FUNNEL_TOTALS.totalCandidates}
          </span>{" "}
          metrics evaluated &middot; {" "}
          <span className="text-emerald-300">{FUNNEL_TOTALS.inFormula}</span>{" "}
          in production &middot;{" "}
          <span className="text-neutral-500">
            {FUNNEL_TOTALS.totalCandidates - FUNNEL_TOTALS.inFormula} rejected
          </span>
        </div>
      </div>

      <SubHeading
        eyebrow="The rejection log"
        title="Selected rejections, by pattern"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Every rejected metric has a documented reason. These are the most
        instructive ones &mdash; they show the patterns that recurred across
        positions. Filter by pattern or position; click a row for the full
        explanation.
      </p>
      <RejectionTable rows={REJECTION_HIGHLIGHTS} />
    </section>
  );
}

function FunnelRow({
  row,
  max,
}: {
  row: (typeof FUNNEL)[number];
  max: number;
}) {
  const totalPct = (row.totalCandidates / max) * 100;
  const acceptPct = (row.inFormula / row.totalCandidates) * 100;
  return (
    <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[60px_1fr_60px]">
      <div className="font-mono text-sm font-semibold text-neutral-200">
        {row.position}
      </div>
      <div className="relative h-6 overflow-hidden rounded bg-neutral-900">
        <div
          className="h-full bg-neutral-700/40"
          style={{ width: `${totalPct}%` }}
        />
        <div
          className="absolute top-0 h-full bg-emerald-400/70"
          style={{
            width: `${(row.inFormula / max) * 100}%`,
          }}
        />
        <div className="absolute inset-0 flex items-center px-3 font-mono text-xs text-neutral-100">
          <span className="text-neutral-300">{row.totalCandidates}</span>
          <span className="mx-2 text-neutral-600">&rarr;</span>
          <span className="text-emerald-300">{row.inFormula}</span>
        </div>
      </div>
      <div className="text-right font-mono text-xs text-neutral-500">
        {acceptPct.toFixed(0)}%
      </div>
    </div>
  );
}

// ===========================================================================
// SECTION 5 — CROSS-POSITION LESSONS (closer)
// ===========================================================================

function LessonsSection() {
  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="What we learned"
        title="Patterns that compounded across positions"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Twelve audits surfaced four recurring lessons. They generalize beyond
        football grading &mdash; any composite-metric system runs into them.
      </p>

      <div className="space-y-6">
        {LESSONS.map((l, i) => (
          <LessonCard key={l.title} idx={i + 1} lesson={l} />
        ))}
      </div>
    </section>
  );
}

function LessonCard({
  idx,
  lesson,
}: {
  idx: number;
  lesson: (typeof LESSONS)[number];
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
      <div className="mb-3 flex items-baseline gap-3">
        <span className="font-mono text-xs text-emerald-400/70">
          Lesson 0{idx}
        </span>
        <h3 className="text-xl font-semibold tracking-tight text-neutral-100">
          {lesson.title}
        </h3>
      </div>
      <div className="mb-4 text-base italic text-neutral-300">
        &ldquo;{lesson.one_liner}&rdquo;
      </div>
      <p className="mb-4 leading-relaxed text-neutral-300">{lesson.body}</p>
      <div className="flex flex-wrap gap-2">
        {lesson.examples.map((e) => (
          <span
            key={e}
            className="rounded border border-neutral-700/60 bg-neutral-900/60 px-2 py-1 text-xs text-neutral-400"
          >
            {e}
          </span>
        ))}
      </div>
    </div>
  );
}

// ===========================================================================
// SECTION 6 — TEAM WEIGHTS AUDIT (ADR-0026)
//
// Same 4-criterion framework, applied one level up. The "candidates" are
// the per-position team grades (snap-weighted from the player grades
// above), and the target is team success (point diff + closing spread).
// Phase weights and per-position weights are both empirically derived.
// ===========================================================================

function TeamWeightsSection() {
  return (
    <section id="team-weights" className="mb-24">
      <SectionHeading
        eyebrow="Team weights"
        title="The same framework, applied one level up"
      />
      <p className="mb-10 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Player grades aggregate into team grades through a two-stage
        formula: snap-weight within each position, then position-weight
        within each phase. Both stages of weights were derived the same
        way as the per-position formulas — empirically. Ridge regression
        of team success against the per-position team grades produces
        the regression coefficients below; salary-cap allocation is the
        market-derived second anchor. Shipped weights reconcile both
        anchors with sample-size humility.
      </p>

      <div className="mb-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <BigStat
          number={`R²=${TEAM_PHASE_AUDIT.rSquaredPD.toFixed(2)}`}
          label="phase model fit"
          sublabel="point diff ~ off + def + st"
        />
        <BigStat
          number="222"
          label="team-seasons audited"
          sublabel="32 teams × 7 seasons (2018-2024)"
        />
        <BigStat
          number="2"
          label="empirical anchors"
          sublabel="ridge regression + cap allocation"
        />
      </div>

      <SubHeading
        eyebrow="Phase weights"
        title="Offense outweighs defense; ST is the small slice"
      />
      <p className="mb-6 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Regression on three phase grades fits at R² = 0.79 against point
        differential — a strong signal. The original priors balanced
        offense and defense 0.45 / 0.45 on principle; the data says
        modern NFL is offense-tilted, and ST contributes closer to its
        salary-cap allocation (~2%) than to a gut-feel 10%.
      </p>
      <WeightAuditTable rows={TEAM_PHASE_AUDIT.rows} kind="phase" />

      <SubHeading
        eyebrow="Position weights"
        title="Per-position contribution to each phase"
      />
      <p className="mb-6 max-w-2xl text-[17px] leading-[1.75] text-neutral-300">
        Within each phase, position weights determine which positions
        carry the composite. QB dominates offense, EDGE and CB share top
        billing on defense, and ST is essentially a 50/50 K/P split. The
        univariate column (Pearson r against team point diff) helps spot
        multicollinearity — WR collapses to ~0 multivariate but still
        correlates strongly on its own.
      </p>

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PhaseAuditCard
          title="Offense"
          eyebrow={`R² = ${TEAM_POSITION_AUDIT.offense.rSquaredPD.toFixed(2)}`}
          rows={TEAM_POSITION_AUDIT.offense.rows}
        />
        <PhaseAuditCard
          title="Defense"
          eyebrow={`R² = ${TEAM_POSITION_AUDIT.defense.rSquaredPD.toFixed(2)}`}
          rows={TEAM_POSITION_AUDIT.defense.rows}
        />
        <PhaseAuditCard
          title="Special teams"
          eyebrow={`R² = ${TEAM_POSITION_AUDIT.st.rSquaredPD.toFixed(2)}`}
          rows={TEAM_POSITION_AUDIT.st.rows}
        />
      </div>

      <SubHeading eyebrow="Headline findings" title="What moved from the gut-feel prior" />
      <div className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-2">
        {TEAM_AUDIT_FINDINGS.map((f) => (
          <FindingCard key={f.title} finding={f} />
        ))}
      </div>

      <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-neutral-500">
          The honest limitation
        </div>
        <p className="text-neutral-300">
          Team grades measure per-snap player quality, snap-weighted across
          a team&rsquo;s available roster. They do <em>not</em> measure win-loss
          record. Teams that outperform their efficiency stats (clutch
          close-game wins) tend to grade lower than their record suggests;
          teams whose stars missed games to injury tend to grade higher
          (snaps from healthy stars still count fully). We documented
          this in ADR-0026 rather than tuning the formula to chase wins
          — that&rsquo;s a v2 question.
        </p>
      </div>
    </section>
  );
}

function WeightAuditTable({
  rows,
  kind,
}: {
  rows: TeamPhaseWeightRow[] | TeamPositionWeightRow[];
  kind: "phase" | "position";
}) {
  return (
    <div className="mb-10 overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-full min-w-[600px] text-sm">
        <thead className="bg-neutral-900/60 text-xs uppercase tracking-wider text-neutral-500">
          <tr>
            <th className="px-4 py-3 text-left font-medium">
              {kind === "phase" ? "Phase" : "Position"}
            </th>
            <th className="px-4 py-3 text-right font-medium">Prior</th>
            <th className="px-4 py-3 text-right font-medium">Cap %</th>
            <th className="px-4 py-3 text-right font-medium">Reg (PD)</th>
            <th className="px-4 py-3 text-right font-medium">Reg (spread)</th>
            {kind === "position" && (
              <th className="px-4 py-3 text-right font-medium">Univariate r</th>
            )}
            <th className="px-4 py-3 text-right font-medium">v1.0 shipped</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-t border-neutral-800/60">
              <td className="px-4 py-3 font-medium text-neutral-200">{r.label}</td>
              <td className="px-4 py-3 text-right font-mono text-neutral-400">
                {r.prior.toFixed(2)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-neutral-400">
                {r.cap.toFixed(2)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-neutral-300">
                {r.regressionPD.toFixed(2)}
              </td>
              <td className="px-4 py-3 text-right font-mono text-neutral-300">
                {r.regressionSpread.toFixed(2)}
              </td>
              {kind === "position" && "univariate" in r && (
                <td className="px-4 py-3 text-right font-mono text-neutral-300">
                  +{(r as TeamPositionWeightRow).univariate.toFixed(2)}
                </td>
              )}
              <td className="px-4 py-3 text-right font-mono font-semibold text-emerald-300">
                {r.shipped.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhaseAuditCard({
  title,
  eyebrow,
  rows,
}: {
  title: string;
  eyebrow: string;
  rows: TeamPositionWeightRow[];
}) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40 p-5">
      <div className="mb-1 text-xs uppercase tracking-wider text-neutral-500">
        {eyebrow}
      </div>
      <h3 className="mb-4 text-lg font-semibold text-neutral-100">{title}</h3>
      <ul className="space-y-3">
        {rows.map((r) => {
          const shipped = r.shipped;
          const reg = r.regressionPD;
          const delta = shipped - r.prior;
          const deltaTone =
            Math.abs(delta) < 0.01
              ? "text-neutral-500"
              : delta > 0
                ? "text-emerald-300"
                : "text-amber-300";
          return (
            <li key={r.label}>
              <div className="mb-1 flex items-baseline justify-between gap-3">
                <span className="font-medium text-neutral-200">{r.label}</span>
                <span className="font-mono text-xs text-neutral-500">
                  prior {r.prior.toFixed(2)}{" "}
                  <span className={deltaTone}>
                    → {shipped.toFixed(2)}
                  </span>
                </span>
              </div>
              <div className="relative h-2 overflow-hidden rounded-full bg-neutral-900">
                {/* Regression coefficient — what the data says */}
                <div
                  className="absolute inset-y-0 left-0 bg-neutral-700/60"
                  style={{ width: `${Math.min(reg, 1) * 100}%` }}
                  title={`Regression coefficient: ${reg.toFixed(2)}`}
                />
                {/* Shipped weight — what we use */}
                <div
                  className="absolute inset-y-0 left-0 bg-emerald-400/70"
                  style={{ width: `${shipped * 100}%` }}
                  title={`Shipped weight: ${shipped.toFixed(2)}`}
                />
              </div>
              <div className="mt-1 flex justify-between text-[10px] font-mono text-neutral-600">
                <span>cap {r.cap.toFixed(2)}</span>
                <span>reg {reg.toFixed(2)}</span>
                <span>r {r.univariate >= 0 ? "+" : ""}{r.univariate.toFixed(2)}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FindingCard({
  finding,
}: {
  finding: (typeof TEAM_AUDIT_FINDINGS)[number];
}) {
  const accent =
    finding.tone === "up"
      ? "border-emerald-500/20 bg-emerald-500/5"
      : finding.tone === "down"
        ? "border-amber-500/20 bg-amber-500/5"
        : "border-neutral-700/40 bg-neutral-900/30";
  const deltaTone =
    finding.tone === "up"
      ? "text-emerald-300"
      : finding.tone === "down"
        ? "text-amber-300"
        : "text-neutral-400";
  return (
    <div className={`rounded-lg border p-5 ${accent}`}>
      <h3 className="mb-2 text-lg font-semibold tracking-tight text-neutral-100">
        {finding.title}
      </h3>
      <p className="mb-3 text-sm leading-relaxed text-neutral-300">
        {finding.body}
      </p>
      <div className={`font-mono text-xs ${deltaTone}`}>{finding.delta}</div>
    </div>
  );
}


// ===========================================================================
// FOOTER
// ===========================================================================

function Footer() {
  return (
    <section className="mt-16 border-t border-neutral-800/60 pt-14">
      <div className="text-sm text-neutral-400">
        <p className="mb-3">
          Each position&rsquo;s full audit doc lives in the repo under{" "}
          <code className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-xs">
            docs/grading/audits/
          </code>
          . The corresponding ADRs (architectural decision records) at{" "}
          <code className="rounded bg-neutral-900 px-1.5 py-0.5 font-mono text-xs">
            docs/adr/
          </code>{" "}
          have the full rationale, alternatives considered, and known limitations
          for each formula version.
        </p>
        <p>
          Want to see how the formulas play out in practice?{" "}
          <Link href="/" className="text-emerald-400 hover:underline">
            Browse the leaderboards
          </Link>
          {" · "}
          <Link href="/methodology" className="text-emerald-400 hover:underline">
            Read the per-position methodology
          </Link>
          .
        </p>
      </div>
    </section>
  );
}

// ===========================================================================
// SHARED HEADINGS
// ===========================================================================

function SectionHeading({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="mb-10">
      <div className="mb-2.5 text-xs uppercase tracking-[0.22em] text-emerald-400/70">
        {eyebrow}
      </div>
      <h2 className="text-2xl font-semibold tracking-tight text-neutral-100 sm:text-3xl">
        {title}
      </h2>
    </div>
  );
}

function SubHeading({
  eyebrow,
  title,
}: {
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="mb-3 mt-8">
      <div className="mb-0.5 text-[11px] uppercase tracking-wider text-neutral-500">
        {eyebrow}
      </div>
      <h3 className="text-xl font-semibold tracking-tight text-neutral-200">
        {title}
      </h3>
    </div>
  );
}

