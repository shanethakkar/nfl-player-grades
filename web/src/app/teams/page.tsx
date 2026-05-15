import type { Metadata } from "next";
import Link from "next/link";

import { TeamLogo } from "@/components/TeamLogo";
import { getAllTeams } from "@/lib/queries";
import type { Conference, Division, Team } from "@/types";

export const metadata: Metadata = {
  title: "Teams — NFL Player Grades",
};

const CONFERENCES: Conference[] = ["AFC", "NFC"];
const DIVISIONS: Division[] = ["East", "North", "South", "West"];

export default async function TeamsIndexPage() {
  const teams = await getAllTeams();

  // Bucket teams by conference → division for the grouped grid below.
  const byBucket = new Map<string, Team[]>();
  for (const t of teams) {
    const key = `${t.conference}-${t.division}`;
    const list = byBucket.get(key) ?? [];
    list.push(t);
    byBucket.set(key, list);
  }

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Teams</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Pick a team to see its roster, grades, and starting lineup by
          season.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-10 md:grid-cols-2">
        {CONFERENCES.map((conf) => (
          <section key={conf}>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-neutral-500">
              {conf === "AFC" ? "American Conference" : "National Conference"}
            </h2>
            <div className="space-y-6">
              {DIVISIONS.map((div) => {
                const list = byBucket.get(`${conf}-${div}`) ?? [];
                if (list.length === 0) return null;
                return (
                  <div key={div}>
                    <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-neutral-600">
                      {conf} {div}
                    </h3>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {list.map((t) => (
                        <TeamCard key={t.team_id} team={t} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}

function TeamCard({ team }: { team: Team }) {
  return (
    <Link
      href={`/teams/${team.abbr}`}
      className="group flex items-center gap-2.5 rounded-lg border border-neutral-800 bg-neutral-950 px-2.5 py-2.5 transition-colors hover:border-neutral-700 hover:bg-neutral-900"
    >
      <TeamLogo abbr={team.abbr} size={28} className="shrink-0" />
      <div className="min-w-0 leading-tight">
        <div className="text-sm font-medium text-neutral-100 group-hover:text-white">
          {team.name}
        </div>
        <div className="mt-0.5 text-[10px] uppercase tracking-wider text-neutral-500">
          {team.abbr}
        </div>
      </div>
    </Link>
  );
}
