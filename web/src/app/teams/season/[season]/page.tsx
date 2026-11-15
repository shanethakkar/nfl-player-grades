import type { Metadata } from "next";

import { getGradedTeamSeasons } from "@/lib/queries";

import { generateTeamsIndexMetadata, TeamsIndex } from "../../_lib/teams-index";

// ISR. Historical team-leaderboard seasons are prerendered so crawlers
// and year-picker clicks hit the CDN instead of a function.
export const revalidate = 86400;
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ season: string }>;
};

export async function generateStaticParams() {
  try {
    const seasons = await getGradedTeamSeasons();
    return seasons.map((season) => ({ season: String(season) }));
  } catch (err) {
    console.error(
      "generateStaticParams for /teams/season/[season] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { season } = await params;
  return generateTeamsIndexMetadata(season);
}

export default async function TeamsSeasonPage({ params }: PageProps) {
  const { season } = await params;
  return <TeamsIndex seasonRaw={season} />;
}
