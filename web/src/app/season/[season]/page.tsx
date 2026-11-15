import type { Metadata } from "next";

import { getGradedSeasons } from "@/lib/queries";

import { generateHomeMetadata, HomeLeaderboard } from "../../_lib/home";

// ISR. Historical leaderboard seasons (default position, QB) are
// prerendered so year-picker clicks hit the CDN.
export const revalidate = 86400;
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ season: string }>;
};

export async function generateStaticParams() {
  try {
    const seasons = await getGradedSeasons();
    return seasons.map((season) => ({ season: String(season) }));
  } catch (err) {
    console.error(
      "generateStaticParams for /season/[season] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { season } = await params;
  return generateHomeMetadata(season);
}

export default async function SeasonPage({ params }: PageProps) {
  const { season } = await params;
  return <HomeLeaderboard seasonRaw={season} />;
}
