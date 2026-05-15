import Link from "next/link";

import { RejectionTable } from "@/components/audit/RejectionTable";
import {
  CRITERIA,
  FUNNEL,
  FUNNEL_TOTALS,
  IDL_BEFORE_AFTER,
  LESSONS,
  REJECTION_HIGHLIGHTS,
  VALIDITY_SCOREBOARD,
  VERDICT_META,
  WR_AUDIT,
  type AuditCandidate,
} from "@/lib/audit-data";

export const metadata = {
  title: "Research — How every weight was decided",
  description:
    "190+ candidates evaluated across 12 positions. 52 in production formulas. The audit framework, the case studies, and the full rejection log.",
};

export default function AuditPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Hero />
      <FrameworkSection />
      <CaseStudySection />
      <ScoreboardSection />
      <AuditLogSection />
      <LessonsSection />
      <Footer />
    </main>
  );
}

// ===========================================================================
// HERO
// ===========================================================================

function Hero() {
  return (
    <section className="mb-20 border-b border-neutral-800 pb-16">
      <div className="mb-3 text-xs uppercase tracking-[0.2em] text-emerald-400/80">
        Research
      </div>
      <h1 className="mb-6 text-4xl font-semibold tracking-tight text-neutral-100 sm:text-5xl">
        How every weight was decided.
      </h1>
      <p className="mb-12 max-w-2xl text-lg leading-relaxed text-neutral-300">
        Each player grade is a weighted composite of 2&ndash;7 statistical
        components. Picking those components &mdash; and choosing what to
        leave out &mdash; was the hard part. This is what we did, what we
        rejected, and what we learned.
      </p>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <BigStat
          number={`${FUNNEL_TOTALS.totalCandidates}+`}
          label="candidates evaluated"
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
        title="Four criteria a candidate must survive"
      />
      <p className="mb-8 max-w-3xl text-neutral-300">
        For every plausible statistical metric in nflverse data, we score it
        against four criteria. A metric only enters a player&rsquo;s grade if
        all four are convincing. The criteria together rule out random noise,
        non-distinguishing stats, redundant signals, and metrics that nobody
        in the football world actually rewards.
      </p>

      <div className="mb-12 grid grid-cols-1 gap-4 md:grid-cols-2">
        {CRITERIA.map((c, i) => (
          <CriterionCard key={c.key} idx={i + 1} criterion={c} />
        ))}
      </div>

      <SubHeading
        eyebrow="A worked example"
        title="What the audit looks like for WR"
      />
      <p className="mb-6 max-w-3xl text-neutral-300">
        Wide receiver got the largest candidate set of any position &mdash;
        22 statistics tested. Six survived. The grid below shows every
        candidate&rsquo;s scores on the four criteria. Hover any row for
        the verdict reasoning.
      </p>

      <AuditGrid candidates={WR_AUDIT} position="WR" />

      <p className="mt-6 max-w-3xl text-sm text-neutral-400">
        The shipped components <span className="font-mono text-emerald-400">·</span>{" "}
        sit at the top because they passed every criterion. Below them,
        the rejected candidates are colour-coded by reason: subsumed by an
        existing formula component, redundant with a chosen one, or below
        the noise threshold for year-over-year reliability.
      </p>
    </section>
  );
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
// AUDIT GRID — heatmap-style table
// ===========================================================================

function AuditGrid({
  candidates,
  position,
}: {
  candidates: AuditCandidate[];
  position: string;
}) {
  // Order shipped components first (by weight desc), then everything else
  // by verdict tone (good > neutral > warn > bad).
  const ordered = [...candidates].sort((a, b) => {
    if (a.verdict === "shipped" && b.verdict !== "shipped") return -1;
    if (a.verdict !== "shipped" && b.verdict === "shipped") return 1;
    if (a.verdict === "shipped" && b.verdict === "shipped") {
      return Math.abs(b.weight ?? 0) - Math.abs(a.weight ?? 0);
    }
    return 0;
  });

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-800">
      <table className="w-full min-w-[860px] text-sm">
        <thead className="bg-neutral-900/60 text-xs uppercase tracking-wider text-neutral-500">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Candidate</th>
            <th className="px-3 py-3 text-right font-medium">YoY r</th>
            <th className="px-3 py-3 text-right font-medium">x-sec std</th>
            <th className="px-3 py-3 text-right font-medium">max |r|</th>
            <th className="px-3 py-3 text-right font-medium">Validity r</th>
            <th className="px-4 py-3 text-left font-medium">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((c) => (
            <AuditGridRow key={c.name} candidate={c} />
          ))}
        </tbody>
      </table>
      <div className="border-t border-neutral-800 bg-neutral-900/40 px-4 py-3 text-xs text-neutral-500">
        {position} cohort · {candidates.length} candidates · scores from
        the 2026-05-14 audit. Cell colour reflects signal strength on each
        criterion (green = passes, amber = marginal, red = fails).
      </div>
    </div>
  );
}

function AuditGridRow({ candidate: c }: { candidate: AuditCandidate }) {
  const meta = VERDICT_META[c.verdict];
  const verdictTone =
    meta.tone === "good"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
      : meta.tone === "warn"
        ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
        : meta.tone === "neutral"
          ? "bg-neutral-700/20 text-neutral-300 border-neutral-700/40"
          : "bg-red-500/10 text-red-300 border-red-500/30";

  const isShipped = c.verdict === "shipped";

  return (
    <tr
      className={
        "group border-t border-neutral-800/60 hover:bg-neutral-900/40 " +
        (isShipped ? "bg-emerald-950/10" : "")
      }
      title={c.rationale}
    >
      <td className="px-4 py-3 align-top">
        <div className="font-medium text-neutral-100">{c.displayName}</div>
        <div className="font-mono text-[10px] text-neutral-500">{c.name}</div>
        {isShipped && c.weight != null && (
          <div className="mt-1 inline-block rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
            weight {c.weight > 0 ? "+" : ""}
            {c.weight.toFixed(2)}
          </div>
        )}
      </td>
      <td className="px-3 py-3 text-right align-top">
        <Heatcell value={c.yoyR} kind="yoy" />
      </td>
      <td className="px-3 py-3 text-right align-top">
        <Heatcell value={c.xsectStd} kind="xsect" />
      </td>
      <td className="px-3 py-3 text-right align-top">
        <Heatcell value={c.maxR} kind="independence" />
        {c.maxRPartner && (
          <div className="mt-0.5 truncate text-[10px] text-neutral-500" style={{ maxWidth: "120px" }}>
            vs {c.maxRPartner.replace(/^[a-z]+_/, "")}
          </div>
        )}
      </td>
      <td className="px-3 py-3 text-right align-top">
        <Heatcell value={c.validityR} kind="validity" />
      </td>
      <td className="px-4 py-3 align-top">
        <span
          className={
            "inline-block rounded border px-2 py-1 text-[11px] font-medium " +
            verdictTone
          }
        >
          {meta.label}
        </span>
        <div
          className="mt-1.5 text-xs text-neutral-400"
          style={{ maxWidth: "260px" }}
        >
          {c.rationale}
        </div>
      </td>
    </tr>
  );
}

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
  const v1Total = IDL_BEFORE_AFTER.v1Weights.reduce(
    (s, w) => s + Math.abs(w.weight),
    0,
  );
  const v12Total = IDL_BEFORE_AFTER.v12Weights.reduce(
    (s, w) => s + Math.abs(w.weight),
    0,
  );

  return (
    <section className="mb-24">
      <SectionHeading
        eyebrow="When the framework caught a flaw"
        title="iDL: the audit said pressure, not run-stop"
      />
      <p className="mb-8 max-w-3xl text-neutral-300">
        Methodology only earns trust by showing it changes when the data
        says it should. Here&rsquo;s the cleanest example: interior
        defensive line was originally designed around &ldquo;run stopping is
        what iDL does.&rdquo; The audit caught that this didn&rsquo;t match
        either the data or how Pro Bowl voters actually evaluate iDL.
      </p>

      <div className="mb-8 rounded-lg border border-amber-500/20 bg-amber-500/5 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-amber-300/80">
          The problem v1 had
        </div>
        <p className="text-neutral-200">{IDL_BEFORE_AFTER.problem}</p>
      </div>

      <SubHeading eyebrow="The audit data" title="Pressure was both more reliable AND more validated" />
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
              <th className="px-4 py-3 text-right font-medium">Weight (v1 → v1.2)</th>
            </tr>
          </thead>
          <tbody>
            {IDL_BEFORE_AFTER.finding.map((row) => (
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

      <p className="mb-10 max-w-3xl text-neutral-300">
        {IDL_BEFORE_AFTER.conclusion}
      </p>

      <SubHeading eyebrow="The fix" title="Formula rebalance, side-by-side" />
      <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        <FormulaCard
          title="iDL v1"
          subtitle="Original — designed around run-stop"
          weights={IDL_BEFORE_AFTER.v1Weights}
          total={v1Total}
          tone="muted"
        />
        <FormulaCard
          title="iDL v1.2"
          subtitle="After audit — pressure-primary"
          weights={IDL_BEFORE_AFTER.v12Weights}
          total={v12Total}
          tone="active"
        />
      </div>

      <div className="mb-8 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-6">
        <div className="mb-2 text-xs uppercase tracking-wider text-emerald-300/80">
          The result
        </div>
        <p className="text-neutral-200">
          {IDL_BEFORE_AFTER.rebalanceImpact}
        </p>
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
      <p className="mb-8 max-w-3xl text-neutral-300">
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
      <p className="mb-8 max-w-3xl text-neutral-300">
        The articles in the analytics community usually show you the formula
        and tell you it&rsquo;s good. Here&rsquo;s what we did before
        landing on the formula. The funnel below shows how many candidates
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
          candidates evaluated &middot; {" "}
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
      <p className="mb-6 max-w-3xl text-neutral-300">
        Every rejected candidate has a documented reason. These are the most
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
      <p className="mb-10 max-w-3xl text-neutral-300">
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
// FOOTER
// ===========================================================================

function Footer() {
  return (
    <section className="mt-12 border-t border-neutral-800 pt-10">
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
    <div className="mb-6">
      <div className="mb-1 text-xs uppercase tracking-[0.18em] text-emerald-400/70">
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
    <div className="mb-3 mt-10">
      <div className="mb-0.5 text-[11px] uppercase tracking-wider text-neutral-500">
        {eyebrow}
      </div>
      <h3 className="text-xl font-semibold tracking-tight text-neutral-200">
        {title}
      </h3>
    </div>
  );
}

