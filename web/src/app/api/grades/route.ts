import { NextResponse } from "next/server";

import {
  getGradedSeasons,
  getLeaderboard,
} from "@/lib/queries";

/**
 * GET /api/grades?season=2024&position=QB
 *
 * Returns the leaderboard for the requested (season, position). Both
 * params are optional:
 *   - season defaults to the most recent graded season.
 *   - position defaults to 'QB' (only position graded in v1).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const position = (url.searchParams.get("position") ?? "QB").toUpperCase();
  const seasonParam = url.searchParams.get("season");

  const seasons = await getGradedSeasons();
  if (seasons.length === 0) {
    return NextResponse.json({ season: null, position, entries: [] });
  }

  const requestedSeason = seasonParam === null ? seasons[0] : Number(seasonParam);
  if (!Number.isFinite(requestedSeason)) {
    return NextResponse.json(
      { error: "Invalid ?season — must be an integer year." },
      { status: 400 },
    );
  }
  if (!seasons.includes(requestedSeason)) {
    return NextResponse.json(
      {
        error: `No grades for season ${requestedSeason}.`,
        available_seasons: seasons,
      },
      { status: 404 },
    );
  }

  const entries = await getLeaderboard(requestedSeason, position);
  return NextResponse.json({
    season: requestedSeason,
    position,
    entries,
  });
}
