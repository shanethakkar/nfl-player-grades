/**
 * NPG football logo. Tilted ~22° "game-card" angle, neutral-gray body,
 * three colored laces (emerald / yellow / red) mapped to the grade
 * palette. Same artwork lives at `src/app/icon.svg` for the favicon —
 * keep the two in sync if you ever tweak the path.
 */
type Props = {
  size?: number;
  className?: string;
};

export function Logo({ size = 28, className = "" }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="NFL Player Grades"
      className={className}
    >
      <g transform="rotate(-22 32 32)">
        {/* Football body — classic amber/brown leather */}
        <path
          d="M 8 32 Q 32 8 56 32 Q 32 56 8 32 Z"
          fill="#7c2d12"
          stroke="#1a0a07"
          strokeWidth="1.5"
        />
        {/* Center seam */}
        <line
          x1="22"
          y1="32"
          x2="42"
          y2="32"
          stroke="#fef3c7"
          strokeWidth="1.5"
          opacity="0.6"
        />
        {/* Three colored laces — emerald (top tier), yellow (mid), red (poor) */}
        <line
          x1="26"
          y1="27"
          x2="26"
          y2="37"
          stroke="#34d399"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <line
          x1="32"
          y1="27"
          x2="32"
          y2="37"
          stroke="#facc15"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <line
          x1="38"
          y1="27"
          x2="38"
          y2="37"
          stroke="#f87171"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}
