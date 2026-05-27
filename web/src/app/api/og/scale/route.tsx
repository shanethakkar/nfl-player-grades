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
  RED,
  YELLOW,
  gradeHex,
} from "../_lib";

export const runtime = "nodejs";

type ScalePin = {
  player_id: number;
  full_name: string;
  position: string;
  grade: number;
  headshot: string | null;
};

/**
 * OG card option D — "The Scale".
 * Horizontal 0-100 color gradient with player headshots pinned at
 * their actual grade positions. Preview at /api/og/scale.
 */
export async function GET() {
  // Pick 4 well-known players spread across the grade range. We seed
  // with player_ids of recognizable names and let the query attach
  // their actual grades — produces a realistic spread.
  const data = await getScalePlayers();
  const pins: ScalePin[] = await Promise.all(
    data.map(async (d) => ({
      ...d,
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
            marginTop: 4,
            display: "flex",
          }}
        >
          <div
            style={{
              fontSize: 18,
              letterSpacing: "0.18em",
              color: EMERALD,
              textTransform: "uppercase",
            }}
          >
            Every player on a scale
          </div>
        </div>

        {/* The scale itself */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            paddingLeft: 80,
            paddingRight: 80,
            paddingTop: 40,
            paddingBottom: 60,
            justifyContent: "center",
            position: "relative",
          }}
        >
          {/* Headshot row — players pinned at their grade x-position */}
          <div
            style={{
              position: "relative",
              height: 200,
              display: "flex",
            }}
          >
            {pins.map((p) => {
              const x = (p.grade / 100) * 100; // % of bar width
              return (
                <div
                  key={p.player_id}
                  style={{
                    position: "absolute",
                    left: `${x}%`,
                    transform: "translateX(-50%)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      width: 124,
                      height: 124,
                      borderRadius: 14,
                      background: "#111",
                      border: `2px solid ${gradeHex(p.grade)}`,
                      overflow: "hidden",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {p.headshot && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={p.headshot}
                        width={120}
                        height={120}
                        style={{ objectFit: "cover" }}
                        alt=""
                      />
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 800,
                      color: gradeHex(p.grade),
                      fontFamily: '"JetBrains Mono", "Courier New", monospace',
                      lineHeight: 1,
                    }}
                  >
                    {p.grade.toFixed(0)}
                  </div>
                  <div style={{ fontSize: 14, color: NEUTRAL_400 }}>
                    {p.full_name}
                  </div>
                </div>
              );
            })}
          </div>

          {/* The color spectrum bar */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
            <div
              style={{
                height: 16,
                borderRadius: 8,
                background: `linear-gradient(to right, ${RED} 0%, ${YELLOW} 50%, ${EMERALD} 100%)`,
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 16,
                color: NEUTRAL_500,
                fontFamily: '"JetBrains Mono", "Courier New", monospace',
              }}
            >
              <span>0</span>
              <span>25</span>
              <span>50</span>
              <span>75</span>
              <span>100</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            paddingLeft: 80,
            paddingRight: 80,
            paddingBottom: 36,
            fontSize: 20,
            color: NEUTRAL_500,
            display: "flex",
            borderTop: `1px solid ${NEUTRAL_800}`,
            paddingTop: 16,
            marginLeft: 56,
            marginRight: 56,
          }}
        >
          12 positions graded. 10 seasons. Open methodology.
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}

async function getScalePlayers(): Promise<
  Array<{ player_id: number; full_name: string; position: string; grade: number }>
> {
  try {
    // Pick the latest season with QB grades. Then sample 4 players
    // spread across the grade range using percentile thresholds, so the
    // card always lands a low / mid-low / mid-high / elite pin.
    const seasonRow = await sql<{ s: number | null }[]>`
      SELECT MAX(season) AS s FROM season_grades WHERE qualified = TRUE
    `;
    const season = seasonRow[0]?.s;
    if (!season) return [];

    const targets = [55, 72, 84, 94];
    const out: Array<{ player_id: number; full_name: string; position: string; grade: number }> = [];
    const seen = new Set<number>();

    for (const tgt of targets) {
      // Prefer offensive skill positions for name recognition; fall back
      // to any qualified player at the right grade tier if needed.
      const rows = await sql<
        { player_id: number; full_name: string; position: string; composite_grade: number }[]
      >`
        SELECT sg.player_id, p.full_name, sg.position, sg.composite_grade
        FROM season_grades sg
        JOIN players p ON p.player_id = sg.player_id
        WHERE sg.season = ${season}
          AND sg.qualified = TRUE
          AND sg.position IN ('QB','RB','WR','TE')
        ORDER BY ABS(sg.composite_grade - ${tgt}) ASC
        LIMIT 4
      `;
      // Take first row that isn't already pinned
      const pick = rows.find((r) => !seen.has(Number(r.player_id)));
      if (pick) {
        seen.add(Number(pick.player_id));
        out.push({
          player_id: Number(pick.player_id),
          full_name: pick.full_name,
          position: pick.position,
          grade: Number(pick.composite_grade),
        });
      }
    }
    return out;
  } catch {
    return [];
  }
}
