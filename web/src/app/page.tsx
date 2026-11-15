import type { Metadata } from "next";

import { generateHomeMetadata, HomeLeaderboard } from "./_lib/home";

// ISR. `/` is the latest season + QB and has no searchParams, so the
// page can be prerendered and served from the CDN.
export const revalidate = 86400;

export async function generateMetadata(): Promise<Metadata> {
  return generateHomeMetadata();
}

export default async function HomePage() {
  return <HomeLeaderboard />;
}
