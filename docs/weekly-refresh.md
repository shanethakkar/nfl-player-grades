# Weekly refresh (Provisional grades)

`nflgrades weekly --season N` refreshes one season end-to-end: it downloads
every nflverse source once, caps them at the last completed regular-season
week, refuses to write anything if a source lags that week, runs every
ingest stage, then writes all grades in one transaction. Design: ADR-0031.

In season it runs on GitHub Actions (`.github/workflows/weekly.yml`, "Weekly
grades") every Wednesday at 12:00 UTC, September through January, against
Neon.

## One-time setup

1. **Apply migrations 0026–0027 to Neon** before deploying the web app
   (the site reads `through_week`):

   ```powershell
   $env:DATABASE_URL = "<Neon URL>"
   nflgrades migrate
   ```

2. **Add the `DATABASE_URL` secret.** Use Neon's *direct* endpoint, not the
   pooler: in the Neon console, Connect → turn "Connection pooling" off, or
   take the pooled URL and delete `-pooler` from the host
   (`ep-...-pooler.c-6...` → `ep-....c-6...`). Keep `?sslmode=require`.

   ```bash
   gh secret set DATABASE_URL --repo shanethakkar/nfl-player-grades
   # paste the URL at the prompt
   ```

   The secret is the only copy of the Neon URL outside your local env files.

3. **Push**, then run it once by hand: GitHub → Actions → "Weekly grades" →
   Run workflow (leave season blank). Or:

   ```bash
   gh workflow run weekly.yml --repo shanethakkar/nfl-player-grades
   gh run watch --repo shanethakkar/nfl-player-grades
   ```

## When a run fails

GitHub emails you; the previous week's grades are still live.

- **`sources not through week N ... ngs_passing at week N-1`**: an nflverse
  source hasn't published the last week yet. Re-run the workflow later in
  the day.
- **`... season summaries already include games after week N`**: NGS has
  started the next week, and its season-summary row can't be capped. Re-run
  once that week is complete (the Wednesday schedule avoids this), or see
  the override below.
- **Anything else**: the grade transaction rolled back, so grades are
  unchanged. Ingest tables may already hold the new week; the next
  successful run overwrites them. The failing stage is in `pipeline_runs`
  (`status = 'error'`, traceback in `notes`). The `weekly` row is the one
  to trust: `grading:*` rows from the same run can read `ok` even though
  the transaction they wrote into was rolled back.

Before week 1 is complete the command does nothing and succeeds. After the
final regular-season week, the next run writes the season as complete
(`through_week` NULL) and the Provisional labels disappear.

## Running it by hand

```powershell
$env:DATABASE_URL = "<Neon URL>"
nflgrades weekly --season 2026
```

Tuesday and Wednesday work as is. From Thursday night's game until Monday
night's is final, NGS season summaries already include the next week's
games and can't be capped, so the run refuses. Every other source is
capped at the last completed week.

To run anyway in that window, pass `--allow-ngs-ahead` (in Actions: tick
"allow_ngs_ahead" on Run workflow). Everything is still graded through the
last completed week, except RB RYOE and WR/TE separation, which include the
games already played in the next week. The run notes this in
`pipeline_runs`, and the next clean run (the Wednesday schedule) restates
it. Every other check still applies.
