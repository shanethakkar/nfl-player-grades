import { NextResponse } from "next/server";
import { sql } from "@/lib/db";
import type { Team } from "@/types";

export async function GET() {
  const teams = await sql<Team[]>`
    SELECT team_id, abbr, name, conference, division, primary_color, secondary_color
    FROM teams
    ORDER BY conference, division, name
  `;
  return NextResponse.json(teams);
}
