import Link from "next/link";

type Props = {
  positions: readonly string[];
  activePosition: string;
  /**
   * When set, links include `season=` so clicking a position preserves the
   * currently-selected season.
   */
  activeSeason?: number;
};

/**
 * Tab-style position picker, parallel to {@link SeasonPicker}. Server-rendered
 * via plain <Link>. `"QB"` links omit `?position=` so the default URL (`/`)
 * stays clean.
 */
export function PositionPicker({
  positions,
  activePosition,
  activeSeason,
}: Props) {
  if (positions.length === 0) return null;
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
      {positions.map((position) => {
        const isActive = position === activePosition;
        const query: Record<string, string | number> = {};
        if (position !== "QB") query.position = position;
        if (activeSeason !== undefined) query.season = activeSeason;
        return (
          <Link
            key={position}
            href={{ pathname: "/", query }}
            className={
              isActive
                ? "rounded-md bg-neutral-100 px-3 py-1 text-sm font-semibold text-neutral-900"
                : "rounded-md px-3 py-1 text-sm text-neutral-400 hover:text-neutral-100"
            }
          >
            {position}
          </Link>
        );
      })}
    </div>
  );
}
