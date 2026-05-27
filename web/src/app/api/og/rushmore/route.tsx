import { ImageResponse } from "next/og";

import { sql } from "@/lib/db";
import {
  CARD_BG,
  EMERALD,
  HeaderBar,
  loadHeadshotDataUrl,
  NEUTRAL_100,
  NEUTRAL_400,
  NEUTRAL_500,
  NEUTRAL_800,
  gradeHex,
} from "../_lib";

export const runtime = "nodejs";

type Hero = {
  player_id: number;
  full_name: string;
  position: string;
  grade: number;
  team_abbr: string;
  headshot: string | null;
};

/**
 * OG card option B — "Mount Rushmore".
 * Four elite players in a row. Gallery feel — every face says
 * "every star, graded." Preview at /api/og/rushmore.
 */
export async function GET() {
  const data = await getTopFourQBs();
  const season = data[0]?.season;

  const heroes: Hero[] = await Promise.all(
    data.map(async (d) => ({
      player_id: d.player_id,
      full_name: d.full_name,
      position: d.position,
      grade: d.grade,
      team_abbr: d.team_abbr,
      headshot: await loadHeadshotDataUrl(d.player_id),
    })),
  );

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

        <div
          style={{
            paddingLeft: 80,
            paddingRight: 80,
            marginTop: 24,
            display: "flex",
            alignItems: "baseline",
            gap: 14,
          }}
        >
          <div
            style={{
              fontSize: 26,
              letterSpacing: "0.18em",
              color: EMERALD,
              textTransform: "uppercase",
            }}
          >
            QB Leaders
          </div>
          {season != null && (
            <div style={{ fontSize: 26, color: NEUTRAL_500 }}>
              {`· ${season}`}
            </div>
          )}
        </div>

        {/* Hero row */}
        <div
          style={{
            flex: 1,
            display: "flex",
            paddingLeft: 60,
            paddingRight: 60,
            paddingTop: 20,
            justifyContent: "space-between",
            alignItems: "center",
            gap: 24,
          }}
        >
          {heroes.map((h) => (
            <HeroBlock key={h.player_id} hero={h} />
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            paddingLeft: 80,
            paddingRight: 80,
            paddingBottom: 44,
            fontSize: 24,
            fontWeight: 500,
            color: NEUTRAL_400,
          }}
        >
          Every NFL player. 0-100. Open methodology.
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}

function HeroBlock({ hero }: { hero: Hero }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 14,
        width: 230,
      }}
    >
      <div
        style={{
          display: "flex",
          width: 200,
          height: 200,
          borderRadius: 20,
          background: "#111",
          border: `1px solid ${NEUTRAL_800}`,
          overflow: "hidden",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {hero.headshot && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={hero.headshot}
            width={200}
            height={200}
            style={{ objectFit: "cover" }}
            alt=""
          />
        )}
      </div>

      <div
        style={{
          fontSize: 56,
          fontWeight: 800,
          color: gradeHex(hero.grade),
          fontFamily: '"JetBrains Mono", "Courier New", monospace',
          letterSpacing: "-0.02em",
          lineHeight: 1,
        }}
      >
        {hero.grade.toFixed(1)}
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ fontSize: 22, fontWeight: 600, color: NEUTRAL_100 }}>
          {hero.full_name}
        </div>
        <div style={{ fontSize: 14, color: NEUTRAL_400, marginTop: 2, letterSpacing: "0.06em" }}>
          {`${hero.position} · ${hero.team_abbr}`}
        </div>
      </div>
    </div>
  );
}

async function getTopFourQBs(): Promise<
  Array<{
    player_id: number;
    full_name: string;
    position: string;
    grade: number;
    team_abbr: string;
    season: number;
  }>
> {
  try {
    const rows = await sql<
      {
        player_id: number;
        full_name: string;
        position: string;
        composite_grade: number;
        team_abbr: string | null;
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
      LIMIT 4
    `;
    return rows.map((r) => ({
      player_id: Number(r.player_id),
      full_name: r.full_name,
      position: r.position,
      grade: Number(r.composite_grade),
      team_abbr: r.team_abbr ?? "—",
      season: Number(r.season),
    }));
  } catch {
    return [];
  }
}
