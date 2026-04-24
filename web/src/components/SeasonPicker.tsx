import Link from "next/link";

type Props = {
  seasons: number[];
  activeSeason: number;
};

/**
 * Tab-style season picker. Uses plain <Link> so the whole page is still
 * server-rendered — no client-side JS needed for this control.
 */
export function SeasonPicker({ seasons, activeSeason }: Props) {
  if (seasons.length === 0) return null;
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-neutral-800 bg-neutral-950 p-1">
      {seasons.map((season) => {
        const isActive = season === activeSeason;
        return (
          <Link
            key={season}
            href={{ pathname: "/", query: { season } }}
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
