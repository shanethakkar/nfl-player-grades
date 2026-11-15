import type { Metadata } from "next";

import {
  generateHomeMetadata,
  HomeLeaderboard,
  POSITION_ORDER,
} from "../../_lib/home";
import { getGradedPositions } from "@/lib/queries";

// ISR. Latest-season leaderboards for each graded position, including
// QB at `/position/QB` so `/?position=QB` can land here instead of
// bouncing to `/`.
export const revalidate = 86400;
export const dynamic = "force-static";
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ position: string }>;
};

export async function generateStaticParams() {
  try {
    const graded = await getGradedPositions();
    return POSITION_ORDER.filter((p) => graded.includes(p)).map(
      (position) => ({ position }),
    );
  } catch (err) {
    console.error(
      "generateStaticParams for /position/[position] failed; falling back to on-demand ISR",
      err,
    );
    return [];
  }
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { position } = await params;
  return generateHomeMetadata(undefined, position);
}

export default async function PositionPage({ params }: PageProps) {
  const { position } = await params;
  return <HomeLeaderboard positionRaw={position} />;
}
