# Removing a Component from a Grading Formula

When a v1.1 audit identifies a component as noise/redundant and we decide to remove it, follow this checklist. Skipping any step leaves stale data that surfaces on the web app.

## The DB-orphan trap

The player profile page (`/players/[id]`) renders **every `stat_components` row** that exists for the player — it doesn't filter to the components currently in the formula. So if we remove `wr_fumble_rate` from the weights dict and re-grade, the old `wr_fumble_rate` rows STAY in the DB unless the grader's `DELETE` statement removes them.

There are two delete patterns in the codebase:

```sql
-- BAD (used to be in qb.py, rb.py, te.py, wr.py — patched 2026-05-14)
DELETE FROM stat_components
WHERE season = :season AND component_name = ANY(:components)
-- This only deletes components CURRENTLY in the formula. Removed components
-- become orphans because they're no longer in the :components list.

-- GOOD (used by cb.py, safety.py, edge.py, idl.py, lb.py, and all 2026-05-14 patched files)
DELETE FROM stat_components
WHERE season = :season AND component_name LIKE 'pos_%'
-- This wipes every component for this position prefix regardless of formula.
```

**Always use the `LIKE 'pos_%'` pattern in new graders.** All graders should use this. Verified 2026-05-14.

## Checklist for removing a component

1. **Edit `weights.py`** — remove from `*_COMPONENTS`, `*_V1_WEIGHTS`, `*_V1_SHRINKAGE_K`, `*_V1_RAW_VALUE_COLS`, `*_V1_SAMPLE_SIZE_COLS`, `*_V1_PRE_ADJUSTED`. Decide whether to redistribute the weight to another component or just let the total drop.

2. **Edit `grading/<position>.py`**:
   - Remove the column from the SQL feature query
   - Remove from `float_cols` / `int_cols` in `extract_features`
   - Remove from the imports if it was named
   - **Verify `_DELETE_STAT_COMPONENTS` uses `LIKE` not `= ANY`**.

3. **Re-grade all seasons for that position.** The `LIKE`-based delete will wipe the removed component's rows; the new INSERT writes only the kept components.

4. **Verify in Neon**:
   ```sql
   SELECT component_name, COUNT(*) FROM stat_components
   WHERE component_name LIKE 'pos_%' GROUP BY component_name;
   ```
   The removed component should NOT appear.

5. **Web layer cleanup** — these will TypeScript-error if missed:
   - `types/index.ts`: remove the field from `LeaderboardEntry`
   - `lib/grades.ts`: remove from `COMPONENT_FORMATS` (the AUTOGEN block updates via sync script after weights.py change)
   - `lib/queries.ts`: remove the SELECT alias, the LEFT JOIN, and the coerce
   - `components/LeaderboardTable.tsx`: remove the column from the position's `*_COLUMNS` array
   - `app/methodology/page.tsx`: remove from the position's `POSITION_COMPONENTS` list
   - `app/page.tsx`: update the position blurb in `COMPOSITE_BLURB` if it mentioned the component

6. **Run the sync script** to push the weights.py change into the AUTOGEN block of grades.ts:
   ```
   python pipeline/scripts/sync_weights_to_web.py
   ```

7. **Bust the cache.** `getPlayerDetail` and `getLeaderboard` are wrapped in `unstable_cache` with `revalidate: 3600`. After re-grading, users will still see stale data for up to an hour. Either:
   - Tell the user to hard-refresh (Ctrl+Shift+R) — instant fix.
   - Or wait 1 hour for revalidation.
   - Or temporarily shorten the revalidate window before a planned formula change.

8. **Update the ADR's Revision History section** explaining what changed and why (use the WR v1.1 and RB v1.1 entries as templates).

9. **Update research notes**: mark the position's research file in `docs/grading/research/` as SHIPPED, update [../README.md](../README.md) hook if structure changed.

## Symptom checklist

If a user reports "I still see [removed component] on the profile":

- Check Neon: `SELECT DISTINCT component_name FROM stat_components WHERE component_name LIKE 'pos_%'`.
  - If the orphan is there → `_DELETE_STAT_COMPONENTS` uses the wrong pattern. Fix and re-grade.
  - If the orphan is NOT there → it's the `unstable_cache` issue. User should hard-refresh.

## Why the `ANY` pattern existed in the first place

QB/RB/TE/WR were the first four position graders written, before the lesson was internalized. The `ANY(:components)` form is more "explicit" in that it only deletes the rows the grader is about to write — feels defensive. But it has the side effect that removing a component from the formula doesn't remove it from the DB. The defensive-position graders (CB, S, EDGE, iDL, LB) were written later with the `LIKE` pattern and avoid the bug entirely.
