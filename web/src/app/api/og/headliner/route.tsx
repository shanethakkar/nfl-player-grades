import { ImageResponse } from "next/og";

import { sql } from "@/lib/db";
import {
  CARD_BG,
  EMERALD,
  HeaderBar,
  loadHeadshotDataUrl,
  NEUTRAL_100,
  NEUTRAL_300,
  NEUTRAL_400,
  NEUTRAL_500,
  NEUTRAL_800,
  gradeHex,
} from "../_lib";

export const runtime = "nodejs";

/**
 * OG card option A — "The Headliner".
 * Single hero player: pixel-art headshot, big grade, name + team,
 * three stat chips at the bottom. Preview at /api/og/headliner.
 */
export async function GET() {
  const data = await getTopQB();
  const headshot = data ? await loadHeadshotDataUrl(data.player_id) : null;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: CARD_BG,
          color: NEUTRAL_100,
          fontFamily: '"Inter", system-ui, sans-serif',
        }}
      >
        <HeaderBar />

        {data ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              paddingLeft: 80,
              paddingRight: 80,
              gap: 60,
            }}
          >
            {/* Left: grade + name + team */}
            <div
              style={{ display: "flex", flexDirection: "column", flex: 1, gap: 16 }}
            >
              <div
                style={{
                  fontSize: 18,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: EMERALD,
                }}
              >
                {`${data.season} · ${data.position} Leader`}
              </div>

              <div
                style={{
                  fontSize: 180,
                  fontWeight: 800,
                  lineHeight: 1,
                  color: gradeHex(data.grade),
                  fontFamily: '"JetBrains Mono", "Courier New", monospace',
                  letterSpacing: "-0.02em",
                }}
              >
                {data.grade.toFixed(1)}
              </div>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  marginTop: 8,
                }}
              >
                <div style={{ fontSize: 48, fontWeight: 700, color: NEUTRAL_100 }}>
                  {data.full_name}
                </div>
                <div style={{ fontSize: 22, color: NEUTRAL_400, marginTop: 4 }}>
                  {`${data.position} · ${data.team_abbr}`}
                </div>
              </div>
            </div>

            {/* Right: hero headshot in a tall card */}
            {headshot && (
              <div
                style={{
                  display: "flex",
                  width: 340,
                  height: 340,
                  borderRadius: 24,
                  background: "#111",
                  border: `1px solid ${NEUTRAL_800}`,
                  overflow: "hidden",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={headshot}
                  width={340}
                  height={340}
                  style={{ objectFit: "cover" }}
                  alt=""
                />
              </div>
            )}
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              color: NEUTRAL_400,
            }}
          >
            Every NFL player, graded 0-100.
          </div>
        )}

        {/* Footer tagline */}
        <div
          style={{
            paddingLeft: 80,
            paddingRight: 80,
            paddingBottom: 36,
            fontSize: 20,
            color: NEUTRAL_500,
            display: "flex",
          }}
        >
          Every player, 12 positions, open methodology.
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}

async function getTopQB(): Promise<
  | {
      player_id: number;
      full_name: string;
      position: string;
      grade: number;
      team_abbr: string;
      season: number;
    }
  | null
> {
  try {
    const rows = await sql<
      {
        player_id: number;
        full_name: string;
        position: string;
        composite_grade: number;
        team_abbr: string;
        season: number;
      }[]
    >`
      SELECT sg.player_id, p.full_name, sg.position, sg.composite_grade,
             t.abbr AS team_abbr, sg.season
      FROM season_grades sg
      JOIN players p ON p.player_id = sg.player_id
      LEFT JOIN player_seasons ps ON ps.player_id = sg.player_id AND ps.season = sg.season
      LEFT JOIN teams t ON t.team_id = ps.team_id
      WHERE sg.position = 'QB' AND sg.qualified = TRUE
        AND sg.season = (SELECT MAX(season) FROM season_grades WHERE position = 'QB' AND qualified = TRUE)
      ORDER BY sg.composite_grade DESC
      LIMIT 1
    `;
    const r = rows[0];
    if (!r) return null;
    return {
      player_id: Number(r.player_id),
      full_name: r.full_name,
      position: r.position,
      grade: Number(r.composite_grade),
      team_abbr: r.team_abbr ?? "—",
      season: Number(r.season),
    };
  } catch {
    return null;
  }
}
