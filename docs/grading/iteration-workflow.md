# Formula Iteration Workflow (canonical, post-2026-05-14)

Three tools introduced 2026-05-14 collapse the pre-existing 7-step shipping process into 3 commands:

- **`nflgrades preview`** — try a weight change in-memory, no writes
- **`pipeline/scripts/sync_weights_to_web.py`** — keep `web/src/lib/grades.ts` in sync with `pipeline/.../weights.py`
- **`nflgrades regrade`** — recompute composite/percentile from existing z-scores, no SQL extract

Always preview first. Always sync to web before regrading. Always regrade Neon, not local.

## Decision: which path?

**Path A — Pure weight change** (90% of revisions):
- Only changing numeric weights in `weights.py`. No new components, no removed components, no SQL changes.
- Use the fast path below.

**Path B — Schema change** (rare):
- Adding a new component, removing one entirely, changing a SQL extract, or adding a new graded position.
- Use the full `grade` (not `regrade`) pipeline. See [checklists/add-position.md](checklists/add-position.md) for new positions, [checklists/removing-a-component.md](checklists/removing-a-component.md) for component removal.

If unsure, ask: "does this require touching `_RAW_VALUE_COLS`, `_SAMPLE_SIZE_COLS`, or the grader's SQL?" If yes → Path B. If no → Path A.

## Path A — pure weight change (the new canonical workflow)

```bash
# 1. PREVIEW (no writes — iterate as many times as needed)
nflgrades preview --season 2024 --position RB \
  --weight rb_rec_epa_per_target=0.05 \
  --weight rb_yac_over_expected_per_rec=0.28 \
  --show-deltas

# 2. EDIT weights.py — change the numbers to match what you previewed
# (edit pipeline/src/nfl_grades/grading/weights.py)

# 3. SYNC web/grades.ts (regenerates COMPONENT_WEIGHTS + TE_BLOCKING_WEIGHTS
#    between AUTOGEN-BEGIN / AUTOGEN-END markers)
python pipeline/scripts/sync_weights_to_web.py

# 4. REGRADE Neon for every affected season
export DATABASE_URL="postgresql+psycopg://...neon...neondb?..."
for y in 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025; do
  nflgrades regrade --season $y --position RB
done

# 5. FACE-CHECK the new top-15 on Neon (optional but recommended)

# 6. UPDATE ADR + memory (the documentation work — still hand-written)
#    - Add v1.X revision history block to docs/adr/00XX-...md
#    - Update relevant docs/grading/research/*.md
#    - Update agent memory if status changed

# 7. COMMIT + push
git add docs/adr/... pipeline/src/nfl_grades/grading/weights.py web/src/lib/grades.ts
git commit -m "..."
git push
```

End-to-end on the RB v1.2 ship (rb_rec_epa_per_target +0.18 → +0.05): steps 1-5 took **~30 seconds** of wall-clock. Steps 6-7 (documentation) take longer, but that's the *thinking* — the *shipping* is fast.

## What each tool does (so you can debug)

### `nflgrades preview --season Y --position P --weight K=V [--show-deltas]`

- Reads `stat_components.z_score` for the qualified cohort on (Y, P).
- Applies a candidate weight dict: defaults from `weights.py`, overridden by `--weight` flags. Multiple `--weight` flags allowed.
- Recomputes composite_z + grade. Same NaN→0 neutralization as production.
- TE handles `blocking_te` role correctly (uses `TE_V1_BLOCKING_WEIGHTS` when applicable).
- **Read-only.** Does not write to DB.
- Output: top-N with current vs preview grade and delta, plus optional biggest-movers section.

Useful for "what if rb_rec_epa was +0.05?" exploration before committing. Verified: preview with no overrides produces exactly the shipped grades (max delta 0.0000).

### `pipeline/scripts/sync_weights_to_web.py [--check]`

- Reads weight dicts from `pipeline/src/nfl_grades/grading/weights.py`.
- Regenerates the `COMPONENT_WEIGHTS` and `TE_BLOCKING_WEIGHTS` blocks in `web/src/lib/grades.ts` between `// AUTOGEN-BEGIN weights` and `// AUTOGEN-END weights` markers. Preserves precision (0.406 stays 0.406, not 0.41).
- Hand-edited content outside the markers (component formats, labels, helpers) is untouched.
- `--check` mode exits 1 if drift exists (use in CI).

If you ever see "missing AUTOGEN markers in grades.ts", check that the comment markers haven't been accidentally deleted. They sit immediately above the `const COMPONENT_WEIGHTS` declaration in `grades.ts`.

### `nflgrades regrade --season Y --position P`

- Reads existing z-scores from `stat_components` for (Y, P).
- Applies current `weights.py` weights → composite_z → grade.
- UPDATEs `season_grades.composite_grade`, `composite_z`, `percentile`.
- Does NOT touch `stat_components` (z-scores unchanged — they only change if you re-run the SQL extract).
- Does NOT re-extract features from `plays` / `ngs_*` / `pfr_*` / `ftn_*`.
- Idempotent. Runs in ~0.3-1s per season.

Speed: ~5× faster than full `grade` on a single season (TE 2024: 1.30s full vs 0.27s regrade). The savings come from skipping the SQL extract; for positions with bigger feature pulls (WR, CB on 2018+) the gap is larger.

## What this workflow does NOT do

- **Does not invalidate the web cache.** `getLeaderboard` and `getPlayerDetail` use `unstable_cache({ revalidate: 3600 })`. After a regrade, users see stale grades for up to an hour unless they hard-refresh. There's a queued task to add cache-bust webhook integration; until then, communicate the 1-hour staleness.
- **Does not handle TE blocking-weight redistribution** unless the weight is in both dicts. If you change a weight that only exists in `TE_V1_WEIGHTS` (like `te_target_earn_rate`), blocking-tier TEs won't see that change — matches production behavior. If you want to change blocking weights too, edit `TE_V1_BLOCKING_WEIGHTS` and re-run sync.
- **Does not auto-update ADRs or research notes.** Those still need hand-written rationale — that's the *why* of the change, which is the part worth documenting. Use the ADR revision history pattern (see ADR-0014 v1.2 for a recent example).
- **Does not handle a new component or removed component.** Those need a real grader code change (Python SQL, raw_value_cols, etc.). Use the full `grade` path.

## When NOT to use this workflow (use Path B instead)

- Adding a new component → schema change, full `grade` path. See [checklists/add-position.md](checklists/add-position.md).
- Removing a component entirely (not just zeroing weight) → schema change, full `grade` path. See [checklists/removing-a-component.md](checklists/removing-a-component.md) for the `_DELETE_STAT_COMPONENTS` gotcha (must be `LIKE 'pos_%'`).
- Changing a SQL extract (e.g., a different filter, a new join) → full `grade` path; regrade can't help because the z-scores would be stale.
- Adding a new graded position → full [checklists/add-position.md](checklists/add-position.md) 13-step.

## Files this workflow touches

- `pipeline/src/nfl_grades/grading/weights.py` — source of truth for weights
- `web/src/lib/grades.ts` — auto-synced (between AUTOGEN markers)
- `season_grades` table on Neon — composite_grade, composite_z, percentile (via regrade)
- `docs/adr/00XX-...md` — hand-edited revision history
- `docs/grading/research/*.md` — hand-edited rationale per position

No other files should change for a pure weight tweak. If you find yourself editing `queries.ts`, `types/index.ts`, `LeaderboardTable.tsx`, methodology page, grader Python, or migrations — you're doing a schema change, not a weight tweak. Switch to Path B.

## Pre-2026-05-14 workflow (deprecated)

Before the preview/regrade/sync tooling shipped, weight changes required editing 5-7 files by hand (weights.py + grades.ts + types/index.ts + queries.ts + LeaderboardTable.tsx + methodology/page.tsx + ADR), then running the full `grade` pipeline for 10 seasons (~5 min), then hand-syncing every TS file. The shipping time was 10-15 minutes per weight change. This is no longer needed for pure weight changes.
