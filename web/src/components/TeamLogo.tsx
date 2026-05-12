import Image from "next/image";

// nflverse uses "LA" for the Rams; ESPN's CDN expects "lar".
const ABBR_OVERRIDE: Record<string, string> = {
  LA: "lar",
};

type Props = {
  abbr: string;
  size?: number;
  className?: string;
};

export function TeamLogo({ abbr, size = 24, className = "" }: Props) {
  const espnAbbr = ABBR_OVERRIDE[abbr] ?? abbr.toLowerCase();
  return (
    <Image
      src={`https://a.espncdn.com/i/teamlogos/nfl/500/${espnAbbr}.png`}
      alt={`${abbr} logo`}
      width={size}
      height={size}
      className={className}
      unoptimized
    />
  );
}
