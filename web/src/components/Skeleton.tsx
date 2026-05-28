/**
 * Shimmering placeholder block, sized by the caller via `className`.
 *
 * Use as the building block for `loading.tsx` skeletons — wrap rows of
 * fixed dimensions to approximate the eventual content. The shimmer
 * comes from the `.skeleton` class in globals.css (a moving gradient
 * background), which reads as "loading" rather than the static
 * `animate-pulse` Tailwind ships.
 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded ${className}`} />;
}
