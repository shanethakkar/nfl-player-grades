import type { Metadata } from "next";

import { getGradedPositions, getGradedSeasons } from "@/lib/queries";

import {
  generateHomeMetadata,
  HomeLeaderboard,
  POSITION_ORDER,
} from "../../../../_lib/home";

// ISR. Every graded season × position is prerendered, including QB
// at `/season/[season]/position/QB`.
export const revalidate = 86400;
export const dynamic = "force-static";
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ season: string; position: string }>;
};

export async function generateStaticParams() {
  try {
    const [seasons, graded] = await Promise.all([
      getGradedSeasons(),
      getGradedPositions(),
    ]);
    const positions = POSITION_ORDER.filter((p) => graded.includes(p));
    return seasons.flatMap((season) =>
      positions.map((position) => ({ season: String(season), position })),
    );
  } catch (err) {
    console.error(
      "generateStaticParams for /season/[season]/position/[position] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { season, position } = await params;
  return generateHomeMetadata(season, position);
}

export default async function SeasonPositionPage({ params }: PageProps) {
  const { season, position } = await params;
  return <HomeLeaderboard seasonRaw={season} positionRaw={position} />;
}
