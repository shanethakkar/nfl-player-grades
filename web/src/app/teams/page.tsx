import type { Metadata } from "next";

import { generateTeamsIndexMetadata, TeamsIndex } from "./_lib/teams-index";

// ISR. `/teams` is the latest season and has no searchParams, so the
// page can be prerendered and served from the CDN instead of SSR on
// every `?season=` variation.
export const revalidate = 86400;

export async function generateMetadata(): Promise<Metadata> {
  return generateTeamsIndexMetadata();
}

export default async function TeamsIndexPage() {
  return <TeamsIndex />;
}
