import type { Metadata } from "next";
import { redirect } from "next/navigation";

import {
  DEFAULT_POSITION,
  generateHomeMetadata,
  HomeLeaderboard,
  POSITION_ORDER,
} from "../../_lib/home";
import { getGradedPositions } from "@/lib/queries";

// ISR. Latest-season leaderboards for each graded position.
export const revalidate = 86400;
export const dynamicParams = true;

type PageProps = {
  params: Promise<{ position: string }>;
};

export async function generateStaticParams() {
  try {
    const graded = await getGradedPositions();
    return POSITION_ORDER.filter(
      (p) => p !== DEFAULT_POSITION && graded.includes(p),
    ).map((position) => ({ position }));
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
  // QB is the default and already lives at `/`.
  if (position.toUpperCase() === DEFAULT_POSITION) {
    redirect("/");
  }
  return <HomeLeaderboard positionRaw={position} />;
}
