import type { Metadata } from "next";

import { getAllTeamSeasonParams } from "@/lib/queries";

import { generateTeamMetadata, TeamProfile } from "../../_lib/team-profile";

// ISR. Every team × graded season is prerendered so year-picker
// navigation and old `?season=` redirects are static.
export const revalidate = 86400;
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ abbr: string; season: string }>;
};

export async function generateStaticParams() {
  try {
    const pairs = await getAllTeamSeasonParams();
    return pairs.map(({ abbr, season }) => ({
      abbr,
      season: String(season),
    }));
  } catch (err) {
    console.error(
      "generateStaticParams for /teams/[abbr]/[season] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { abbr, season } = await params;
  return generateTeamMetadata(abbr, season);
}

export default async function TeamSeasonPage({ params }: PageProps) {
  const { abbr, season } = await params;
  return <TeamProfile abbrRaw={abbr} seasonRaw={season} />;
}
