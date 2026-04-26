import { NextResponse } from "next/server";

import { sql } from "@/lib/db";

/**
 * Quick DB connectivity + row count check. If `qualified_season_grades` is 0
 * but Neon’s console shows thousands, the runtime `DATABASE_URL` (Vercel env
 * or `web/.env.local`) is not the same database you loaded with the pipeline.
 */
export async function GET() {
  const [row] = await sql<
    { total: string; qualified: string }[]
  >`
    SELECT
      COUNT(*)::text AS total,
      COUNT(*) FILTER (WHERE qualified)::text AS qualified
    FROM season_grades
  `;
  return NextResponse.json({
    season_grades_total: Number(row?.total ?? 0),
    qualified_season_grades: Number(row?.qualified ?? 0),
  });
}
