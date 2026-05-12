import type { SeasonGradeDetail } from "@/types";

function gradeHex(grade: number): string {
  if (grade >= 90) return "#34d399";
  if (grade >= 80) return "#4ade80";
  if (grade >= 70) return "#a3e635";
  if (grade >= 55) return "#facc15";
  if (grade >= 40) return "#fb923c";
  return "#f87171";
}

type Props = {
  grades: SeasonGradeDetail[];
};

export function CareerGradeChart({ grades }: Props) {
  const qualified = grades
    .filter((g) => g.qualified)
    .sort((a, b) => a.season - b.season);

  if (qualified.length < 2) return null;

  const W = 560;
  const H = 110;
  const PAD_X = 32;
  const PAD_TOP = 30;
  const PAD_BOT = 22;
  const chartW = W - PAD_X * 2;
  const chartH = H - PAD_TOP - PAD_BOT;
  const n = qualified.length;

  const xOf = (i: number) =>
    n === 1 ? PAD_X + chartW / 2 : PAD_X + (i / (n - 1)) * chartW;
  const yOf = (grade: number) => PAD_TOP + chartH * (1 - grade / 100);

  const points = qualified
    .map((g, i) => `${xOf(i)},${yOf(g.composite_grade)}`)
    .join(" ");

  const y50 = yOf(50);

  return (
    <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-950/60 p-4">
      <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
        Career grade trend
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        aria-label="Career grade trend sparkline"
      >
        <line
          x1={PAD_X}
          y1={y50}
          x2={W - PAD_X}
          y2={y50}
          stroke="#262626"
          strokeWidth={1}
          strokeDasharray="4 3"
        />
        <polyline
          points={points}
          fill="none"
          stroke="#404040"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        {qualified.map((g, i) => {
          const cx = xOf(i);
          const cy = yOf(g.composite_grade);
          const color = gradeHex(g.composite_grade);
          return (
            <g key={`${g.season}-${g.position}`}>
              <text
                x={cx}
                y={cy - 9}
                textAnchor="middle"
                fontSize={10}
                fill={color}
                fontFamily="ui-monospace, monospace"
                fontWeight="600"
              >
                {g.composite_grade.toFixed(0)}
              </text>
              <circle cx={cx} cy={cy} r={4} fill={color} />
              <text
                x={cx}
                y={H - 4}
                textAnchor="middle"
                fontSize={10}
                fill="#525252"
              >
                {g.season}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
