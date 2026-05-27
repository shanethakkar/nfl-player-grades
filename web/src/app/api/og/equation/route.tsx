import { ImageResponse } from "next/og";

import {
  CARD_BG,
  EMERALD,
  HeaderBar,
  NEUTRAL_100,
  NEUTRAL_300,
  NEUTRAL_400,
  NEUTRAL_500,
  NEUTRAL_800,
  RED,
  YELLOW,
} from "../_lib";

export const runtime = "nodejs";

/**
 * OG card option C — "The Equation".
 * Formula + color spectrum + audit numbers. No headshots; leans hard
 * into the open-methodology brand. Preview at /api/og/equation.
 */
export async function GET() {
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

        {/* Body */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            paddingLeft: 80,
            paddingRight: 80,
            gap: 36,
          }}
        >
          {/* Eyebrow */}
          <div
            style={{
              fontSize: 18,
              letterSpacing: "0.18em",
              color: EMERALD,
              textTransform: "uppercase",
            }}
          >
            Open methodology
          </div>

          {/* The equation — center stage */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 28,
              fontFamily: '"JetBrains Mono", "Courier New", monospace',
            }}
          >
            <div style={{ fontSize: 84, fontWeight: 700, color: NEUTRAL_100 }}>
              grade
            </div>
            <div style={{ fontSize: 84, color: NEUTRAL_500 }}>=</div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
              }}
            >
              <div style={{ fontSize: 64, fontWeight: 700, color: NEUTRAL_100 }}>
                100
              </div>
              <div
                style={{
                  width: 260,
                  height: 4,
                  background: NEUTRAL_400,
                }}
              />
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  fontSize: 48,
                  color: NEUTRAL_300,
                }}
              >
                <span>1 + e</span>
                <sup style={{ fontSize: 28 }}>−1.15·z</sup>
              </div>
            </div>
          </div>

          {/* Color spectrum bar */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div
              style={{
                height: 14,
                borderRadius: 7,
                background: `linear-gradient(to right, ${RED}, ${YELLOW}, ${EMERALD})`,
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
              <span>50</span>
              <span>90</span>
              <span>100</span>
            </div>
          </div>
        </div>

        {/* Footer stat row */}
        <div
          style={{
            display: "flex",
            paddingLeft: 80,
            paddingRight: 80,
            paddingBottom: 48,
            paddingTop: 24,
            gap: 60,
            borderTop: `1px solid ${NEUTRAL_800}`,
            marginLeft: 56,
            marginRight: 56,
          }}
        >
          <StatBlock big="189+" label="metrics evaluated" />
          <StatBlock big="52" label="in production formulas" />
          <StatBlock big="12" label="positions graded" />
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}

function StatBlock({ big, label }: { big: string; label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          fontSize: 44,
          fontWeight: 700,
          color: EMERALD,
          fontFamily: '"JetBrains Mono", "Courier New", monospace',
        }}
      >
        {big}
      </div>
      <div style={{ fontSize: 18, color: NEUTRAL_400, marginTop: 4 }}>
        {label}
      </div>
    </div>
  );
}
