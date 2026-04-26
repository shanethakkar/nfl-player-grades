import { NextResponse } from "next/server";

import { searchPlayers } from "@/lib/queries";

/**
 * GET /api/players/search?q=mahomes&limit=8
 *
 * Powers the header autocomplete. Restricts results to graded players
 * (see `searchPlayers`) and returns at most `limit` hits, capped at
 * 25 so a misbehaving client can't pull a giant payload.
 *
 * Returns `{ results: [] }` for queries shorter than 2 characters
 * rather than 400 — debounced typing in the input otherwise spams 400s
 * for the first keystroke.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const q = url.searchParams.get("q") ?? "";
  const limitParam = url.searchParams.get("limit");
  let limit = limitParam === null ? 8 : Number(limitParam);
  if (!Number.isFinite(limit) || limit <= 0) limit = 8;
  if (limit > 25) limit = 25;

  const results = await searchPlayers(q, limit);
  return NextResponse.json({ q, results });
}
