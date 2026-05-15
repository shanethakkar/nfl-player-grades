"use client";

import { useRouter } from "next/navigation";

import type { Conference, Division, Team } from "@/types";

/**
 * Dropdown that lets the user jump to another team without going back
 * to the /teams index. Lives next to the year selector on the team
 * page. Native select with optgroups (division-aware) so it stays
 * mobile-friendly and accessible for free.
 *
 * Preserves the current ?season=N query param so switching teams keeps
 * you on the same year (assuming the new team has data for that year —
 * the team page falls back to its latest season if not).
 */
type Props = {
  teams: Team[];
  activeAbbr: string;
  activeSeason: number | null;
};

const CONFERENCES: Conference[] = ["AFC", "NFC"];
const DIVISIONS: Division[] = ["East", "North", "South", "West"];

export function TeamSwitcher({ teams, activeAbbr, activeSeason }: Props) {
  const router = useRouter();

  // Bucket teams by conference + division so the <optgroup> labels make sense.
  const byBucket = new Map<string, Team[]>();
  for (const t of teams) {
    const key = `${t.conference}-${t.division}`;
    const list = byBucket.get(key) ?? [];
    list.push(t);
    byBucket.set(key, list);
  }

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value;
    if (!next || next === activeAbbr) return;
    const url =
      activeSeason !== null
        ? `/teams/${next}?season=${activeSeason}`
        : `/teams/${next}`;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(url as any);
  }

  return (
    <select
      value={activeAbbr}
      onChange={onChange}
      aria-label="Switch team"
      className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-600"
    >
      {CONFERENCES.flatMap((conf) =>
        DIVISIONS.map((div) => {
          const list = byBucket.get(`${conf}-${div}`) ?? [];
          if (list.length === 0) return null;
          return (
            <optgroup key={`${conf}-${div}`} label={`${conf} ${div}`}>
              {list.map((t) => (
                <option key={t.team_id} value={t.abbr}>
                  {t.name}
                </option>
              ))}
            </optgroup>
          );
        }),
      )}
    </select>
  );
}
