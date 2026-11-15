import type { Metadata } from "next";

import { getAllTeams } from "@/lib/queries";

import { generateTeamMetadata, TeamProfile } from "../_lib/team-profile";

// ISR. `/teams/[abbr]` is the team's latest season. All 32
// abbreviations are prerendered at build time; unknown abbrs 404
// after a single cheap lookup.
export const revalidate = 86400;
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ abbr: string }>;
};

export async function generateStaticParams() {
  try {
    const teams = await getAllTeams();
    return teams.map((team) => ({ abbr: team.abbr }));
  } catch (err) {
    console.error(
      "generateStaticParams for /teams/[abbr] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { abbr } = await params;
  return generateTeamMetadata(abbr);
}

export default async function TeamPage({ params }: PageProps) {
  const { abbr } = await params;
  return <TeamProfile abbrRaw={abbr} />;
}
