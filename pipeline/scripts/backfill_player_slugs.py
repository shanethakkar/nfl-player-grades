"""One-time backfill of the `players.slug` column.

Rule (matches migration 0024 doc comment):
  1. Default: lowercase(full_name), non-alphanumeric runs -> hyphen.
  2. On collision among graded players: the player with the most graded
     seasons keeps the bare slug. Tie-breaker: lowest player_id.
  3. Secondary colliders get a position suffix (e.g. `lamar-jackson-cb`).
  4. If position ALSO collides (e.g. two Jaylon Joneses both at CB):
     fall back to first-graded-season suffix (`jaylon-jones-2022`).
  5. Non-graded colliders: append player_id (they aren't surfaced
     anywhere on the site, so the slug just needs to be unique).

After running, every player row should have a non-null slug and the
set of slugs should be unique. Migration 0025 then enforces those
constraints.

Idempotent: re-running rewrites all slugs from scratch. Safe to run
multiple times during development.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_grades.db import get_engine  # noqa: E402


SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def base_slug(full_name: str) -> str:
    s = (full_name or "").lower().strip()
    s = SLUG_NON_ALNUM.sub("-", s)
    return s.strip("-")


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        # Pull every player + a summary of their grading record. Players
        # without grades come through with n_seasons = 0 and NULL position/
        # first_season; collision-resolution rules treat them as the
        # weakest claimants to a slug.
        rows = conn.execute(text("""
            SELECT
                p.player_id,
                p.full_name,
                COALESCE(s.n_seasons, 0)        AS n_seasons,
                s.primary_position,
                s.first_season
            FROM players p
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(DISTINCT sg.season)               AS n_seasons,
                    -- "primary" position = position with the most
                    -- graded seasons; ties broken alphabetically.
                    (SELECT sg2.position
                     FROM season_grades sg2
                     WHERE sg2.player_id = p.player_id
                     GROUP BY sg2.position
                     ORDER BY COUNT(*) DESC, sg2.position
                     LIMIT 1)                               AS primary_position,
                    MIN(sg.season)                          AS first_season
                FROM season_grades sg
                WHERE sg.player_id = p.player_id
            ) s ON TRUE
        """)).mappings().all()

    # Group by base slug to find collisions.
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[base_slug(r["full_name"])].append(dict(r))

    # Assign final slugs.
    assignments: dict[int, str] = {}

    for base, members in groups.items():
        if not base:
            # Edge case: player with empty/null name. Fall back to id.
            for m in members:
                assignments[m["player_id"]] = f"player-{m['player_id']}"
            continue

        if len(members) == 1:
            assignments[members[0]["player_id"]] = base
            continue

        # Sort: graded players first (by n_seasons desc), then by player_id asc.
        members.sort(key=lambda m: (-m["n_seasons"], m["player_id"]))

        # The "primary" player keeps the bare slug.
        primary = members[0]
        primary_pos = primary["primary_position"]
        assignments[primary["player_id"]] = base
        used: set[str] = {base}

        # Resolve each secondary, in sort order, with the fallback chain:
        #   1. position suffix (`-cb`) if the secondary's position
        #      DIFFERS from the primary's (so the suffix actually
        #      disambiguates by role)
        #   2. first-graded-season suffix (`-2022`) when the secondary
        #      shares a position with the primary OR has no position
        #   3. player_id suffix (`-1423`) as the last-resort tiebreaker
        for m in members[1:]:
            pos = m["primary_position"]
            tried: list[str] = []
            if pos and pos != primary_pos:
                tried.append(f"{base}-{_pos_token(pos)}")
            if m["first_season"] is not None:
                tried.append(f"{base}-{m['first_season']}")
            tried.append(f"{base}-{m['player_id']}")

            final = next((t for t in tried if t not in used), tried[-1])
            assignments[m["player_id"]] = final
            used.add(final)

    # Sanity: every assignment is unique.
    seen: dict[str, int] = {}
    for pid, slug in assignments.items():
        if slug in seen:
            raise RuntimeError(
                f"slug collision after resolution: '{slug}' assigned to "
                f"both player_id {seen[slug]} and {pid}"
            )
        seen[slug] = pid

    # Write everything.
    with engine.begin() as conn:
        for pid, slug in assignments.items():
            conn.execute(
                text("UPDATE players SET slug = :s WHERE player_id = :pid"),
                {"s": slug, "pid": pid},
            )

    print(f"Backfilled {len(assignments)} slugs.")
    # Show a few interesting cases for confidence.
    samples = [
        "Drake Maye", "Lamar Jackson", "Chris Jones",
        "Brandon Marshall", "Michael Thomas", "Jaylon Jones",
        "Jordan Phillips",
    ]
    with engine.begin() as conn:
        for name in samples:
            r = conn.execute(text("""
                SELECT player_id, full_name, slug FROM players
                WHERE full_name = :n ORDER BY player_id
            """), {"n": name}).mappings().all()
            for row in r:
                print(f"  {row['player_id']:<6} {row['full_name']:<25} -> /players/{row['slug']}")


def _pos_token(position: str) -> str:
    """Position string -> URL-safe token. 'iDL' -> 'idl', 'S' -> 's'."""
    return SLUG_NON_ALNUM.sub("-", position.lower()).strip("-")


if __name__ == "__main__":
    main()
