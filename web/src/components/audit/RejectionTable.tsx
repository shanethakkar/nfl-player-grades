"use client";

import { useMemo, useState } from "react";

type Pattern =
  | "subsumed"
  | "noise"
  | "anti-skill"
  | "context-only"
  | "small-sample";

type Row = {
  position: string;
  candidate: string;
  reason: string;
  pattern: Pattern;
  detail: string;
  yoy: number | null;
  validity: number | null;
};

const PATTERN_LABELS: Record<Pattern, string> = {
  "subsumed": "Subsumed",
  "noise": "Noise",
  "anti-skill": "Anti-skill",
  "context-only": "Context only",
  "small-sample": "Small sample",
};

const PATTERN_TONE: Record<Pattern, string> = {
  "subsumed": "border-amber-500/40 bg-amber-500/10 text-amber-300",
  "noise": "border-red-500/40 bg-red-500/10 text-red-300",
  "anti-skill": "border-red-500/50 bg-red-500/15 text-red-200",
  "context-only": "border-neutral-600/50 bg-neutral-700/20 text-neutral-300",
  "small-sample": "border-orange-500/40 bg-orange-500/10 text-orange-300",
};

export function RejectionTable({ rows }: { rows: Row[] }) {
  const [patternFilter, setPatternFilter] = useState<Pattern | "all">("all");
  const [positionFilter, setPositionFilter] = useState<string | "all">("all");
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  const positions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.position))).sort(),
    [rows],
  );

  const patterns = useMemo(
    () => Array.from(new Set(rows.map((r) => r.pattern))) as Pattern[],
    [rows],
  );

  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (patternFilter === "all" || r.pattern === patternFilter) &&
          (positionFilter === "all" || r.position === positionFilter),
      ),
    [rows, patternFilter, positionFilter],
  );

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/40">
      <div className="flex flex-wrap items-center gap-3 border-b border-neutral-800 p-4">
        <FilterPills
          label="Pattern"
          value={patternFilter}
          options={[
            { v: "all", label: `All (${rows.length})` },
            ...patterns.map((p) => ({
              v: p,
              label: `${PATTERN_LABELS[p]} (${rows.filter((r) => r.pattern === p).length})`,
            })),
          ]}
          onChange={(v) => setPatternFilter(v as Pattern | "all")}
        />
        <FilterPills
          label="Position"
          value={positionFilter}
          options={[
            { v: "all", label: "All" },
            ...positions.map((p) => ({ v: p, label: p })),
          ]}
          onChange={setPositionFilter}
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-neutral-900/40 text-xs uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Position</th>
              <th className="px-4 py-3 text-left font-medium">Candidate</th>
              <th className="px-4 py-3 text-left font-medium">Pattern</th>
              <th className="px-3 py-3 text-right font-medium">YoY</th>
              <th className="px-3 py-3 text-right font-medium">Validity</th>
              <th className="px-4 py-3 text-left font-medium">Reason</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-neutral-500">
                  No rejections match this filter.
                </td>
              </tr>
            )}
            {filtered.map((row, i) => {
              const isOpen = openIdx === i;
              return (
                <RowItem
                  key={`${row.position}-${row.candidate}`}
                  row={row}
                  isOpen={isOpen}
                  onToggle={() => setOpenIdx(isOpen ? null : i)}
                />
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="border-t border-neutral-800 px-4 py-3 text-xs text-neutral-500">
        Showing {filtered.length} of {rows.length} featured rejections.
        Click a row for the full explanation.
      </div>
    </div>
  );
}

function RowItem({
  row,
  isOpen,
  onToggle,
}: {
  row: Row;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-t border-neutral-800/60 hover:bg-neutral-900/40"
        onClick={onToggle}
      >
        <td className="px-4 py-3 font-mono text-xs font-semibold text-neutral-300">
          {row.position}
        </td>
        <td className="px-4 py-3 text-neutral-200">{row.candidate}</td>
        <td className="px-4 py-3">
          <span
            className={
              "rounded border px-2 py-0.5 text-[11px] font-medium " +
              PATTERN_TONE[row.pattern]
            }
          >
            {PATTERN_LABELS[row.pattern]}
          </span>
        </td>
        <td className="px-3 py-3 text-right font-mono text-xs text-neutral-400">
          {row.yoy != null
            ? (row.yoy > 0 ? "+" : "") + row.yoy.toFixed(3)
            : "n/a"}
        </td>
        <td className="px-3 py-3 text-right font-mono text-xs text-neutral-400">
          {row.validity != null
            ? (row.validity > 0 ? "+" : "") + row.validity.toFixed(3)
            : "skipped"}
        </td>
        <td className="px-4 py-3 text-sm text-neutral-300">
          {row.reason}{" "}
          <span aria-hidden className="ml-1 text-neutral-600">
            {isOpen ? "▼" : "▶"}
          </span>
        </td>
      </tr>
      {isOpen && (
        <tr className="border-t border-neutral-800/40 bg-neutral-900/30">
          <td colSpan={6} className="px-6 py-4 text-sm text-neutral-300">
            <div className="max-w-3xl">{row.detail}</div>
          </td>
        </tr>
      )}
    </>
  );
}

function FilterPills({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { v: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs uppercase tracking-wider text-neutral-500">
        {label}
      </span>
      {options.map((o) => {
        const active = o.v === value;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={
              "rounded border px-2.5 py-1 text-xs transition-colors " +
              (active
                ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-300"
                : "border-neutral-700 bg-neutral-900/50 text-neutral-400 hover:bg-neutral-800")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
