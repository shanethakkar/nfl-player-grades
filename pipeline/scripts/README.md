# scripts/

One-off and orchestration entry points. For anything you'd schedule with cron
or Prefect, put it here and import from `nfl_grades`.

These are thin — most logic lives in the package. Scripts handle argument
parsing, logging setup, and calling into the package.

Prefer the `nflgrades` CLI (installed with `pip install -e .`) over adding new
scripts. Only add a script here when the CLI doesn't fit (e.g. a one-time
backfill).
