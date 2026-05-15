import { gradeHex } from "@/lib/grades";

/**
 * Inline sparkline for leaderboard rows. Renders the last N seasons of a
 * player's composite grade as a tiny SVG. Designed to sit comfortably in a
 * single table cell (~70x20).
 *
 * If a player has < 2 graded seasons, renders a single dot for the current
 * season instead of a line.
 *
 * Data shape: array of { season, grade }, ordered oldest-first. Caller is
 * responsible for picking the slice (e.g. last 5 seasons).
 */
type Point = { season: number; grade: number };

type Props = {
  points: Point[];
  /** Width in px (default 70). */
  width?: number;
  /** Height in px (default 20). */
  height?: number;
  /** Show small dots at each season (default: only at the latest point). */
  showDots?: boolean;
};

export function MiniSparkline({
  points,
  width = 70,
  height = 20,
  showDots = false,
}: Props) {
  if (!points.length) {
    return (
      <span className="inline-block text-xs text-neutral-700" style={{ width }}>
        —
      </span>
    );
  }

  const padX = 2;
  const padY = 3;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  // Y scale: fixed 0-100 range so different players are visually comparable.
  const yOf = (g: number) => padY + innerH * (1 - g / 100);

  // X scale: evenly spaced across the available width.
  const xOf = (i: number) =>
    points.length === 1
      ? padX + innerW / 2
      : padX + (i / (points.length - 1)) * innerW;

  const pathData = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(i)} ${yOf(p.grade)}`)
    .join(" ");

  // Last point — colored by its grade tier so the dot signals current value.
  const last = points[points.length - 1];
  const lastX = xOf(points.length - 1);
  const lastY = yOf(last.grade);
  const lastColor = gradeHex(last.grade);

  // Reference line at grade=50 (league average) — very subtle.
  const midY = yOf(50);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block align-middle"
      aria-label={`Grade trend: ${points.map((p) => `${p.season} ${p.grade.toFixed(0)}`).join(", ")}`}
    >
      {/* league-average reference */}
      <line
        x1={padX}
        y1={midY}
        x2={width - padX}
        y2={midY}
        stroke="#262626"
        strokeWidth={1}
        strokeDasharray="1,2"
      />
      {/* trend line */}
      <path
        d={pathData}
        fill="none"
        stroke="#525252"
        strokeWidth={1.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* optional intermediate dots */}
      {showDots &&
        points.slice(0, -1).map((p, i) => (
          <circle
            key={p.season}
            cx={xOf(i)}
            cy={yOf(p.grade)}
            r={1.4}
            fill="#737373"
          />
        ))}
      {/* latest point — colored to match grade tier */}
      <circle cx={lastX} cy={lastY} r={2.25} fill={lastColor} />
    </svg>
  );
}
