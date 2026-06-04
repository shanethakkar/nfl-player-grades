/**
 * NPG football logo — same artwork as the site's `<Logo>` component.
 * Reused directly so the video's branding ties back to the product.
 */
export function Logo({ size = 64 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="NFL Player Grades"
    >
      <g transform="rotate(-22 32 32)">
        <path
          d="M 8 32 Q 32 8 56 32 Q 32 56 8 32 Z"
          fill="#7c2d12"
          stroke="#1a0a07"
          strokeWidth="1.5"
        />
        <line
          x1="22"
          y1="32"
          x2="42"
          y2="32"
          stroke="#fef3c7"
          strokeWidth="1.5"
          opacity="0.6"
        />
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
