"use client";

import { useRouter } from "next/navigation";

export function BackLink() {
  const router = useRouter();
  return (
    <button
      onClick={() => router.back()}
      className="text-sm text-neutral-400 hover:text-neutral-100"
    >
      ← back to leaderboard
    </button>
  );
}
