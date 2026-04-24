import Link from "next/link";

type Props = {
  seasons: number[];
  activeSeason: number;
  /**
   * When set, links include `position=` so clicking a season preserves the
   * currently-selected position. `"QB"` is omitted to keep the URL clean
   * (QB is the default when no `?position=` is present).
   */
  activePosition?: string;
};

/**
 * Tab-style season picker. Uses plain <Link> so the whole page is still
 * server-rendered — no client-side JS needed for this control.
 */
export function SeasonPicker({
  seasons,
  activeSeason,
  activePosition,
}: Props) {
  if (seasons.length === 0) return null;
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
      {seasons.map((season) => {
        const isActive = season === activeSeason;
        const query: Record<string, string | number> = { season };
        if (activePosition && activePosition !== "QB") {
          query.position = activePosition;
        }
        return (
          <Link
            key={season}
            href={{ pathname: "/", query }}
            className={
              isActive
                ? "rounded-md bg-neutral-100 px-3 py-1 text-sm font-semibold text-neutral-900"
                : "rounded-md px-3 py-1 text-sm text-neutral-400 hover:text-neutral-100"
            }
          >
            {season}
          </Link>
        );
      })}
    </div>
  );
}
