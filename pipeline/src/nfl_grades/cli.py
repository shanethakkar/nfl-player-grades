"""`nflgrades` command-line entry point.

Thin wrapper around the orchestration scripts so they can be invoked as
`nflgrades ingest --season 2024` etc. Concrete stages are implemented in
their respective packages; this file only wires arguments.
"""

from __future__ import annotations

import click

from .logging import configure_logging


@click.group()
def main() -> None:
    """NFL Player Grades pipeline CLI."""
    configure_logging()


@main.group()
def ingest() -> None:
    """Pull raw data from nflreadpy into the parquet cache + Postgres.

    One subcommand per data source. Each is idempotent and writes a row
    to ``pipeline_runs``. See ADRs 0009 and 0010.
    """


@ingest.command(name="rosters")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True, help="Bypass parquet cache and re-fetch.")
def ingest_rosters(season: int, refresh: bool) -> None:
    """Refresh the players master + season player_seasons skeleton."""
    from .ingest import rosters

    result = rosters.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"players_upserted={result.players_upserted} "
        f"player_seasons_upserted={result.player_seasons_upserted} "
        f"skipped_no_gsis={result.rows_skipped_no_gsis} "
        f"skipped_unknown_pos={result.rows_skipped_unknown_pos} "
        f"skipped_unknown_team={result.rows_skipped_unknown_team}"
    )


@ingest.command(name="pbp")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pbp(season: int, refresh: bool) -> None:
    """Pull play-by-play into the thin plays table (see ADR-0011)."""
    from .ingest import pbp

    result = pbp.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pk={result.rows_skipped_no_pk}"
    )


@ingest.command(name="snap-counts")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_snap_counts(season: int, refresh: bool) -> None:
    """Pull snap counts (fills in player_seasons.games + snaps_*)."""
    from .ingest import snap_counts

    result = snap_counts.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"player_seasons_updated={result.player_seasons_updated} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match}"
    )


@ingest.command(name="depth-charts")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_depth_charts(season: int, refresh: bool) -> None:
    """Build end-of-regular-season depth-chart snapshot (week=99)."""
    from .ingest import depth_charts

    result = depth_charts.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"source_format={result.source_format} "
        f"source={result.source_label} "
        f"rows_inserted={result.rows_inserted} "
        f"skipped_team={result.skipped_unknown_team} "
        f"skipped_player={result.skipped_unknown_player} "
        f"skipped_depth={result.skipped_non_integer_depth} "
        f"skipped_dup={result.skipped_duplicate}"
    )


@ingest.command(name="ngs")
@click.option("--season", type=int, required=True)
@click.option(
    "--stat-type",
    type=click.Choice(["passing", "rushing", "receiving", "all"]),
    default="all",
    help="Which NGS stat type(s) to ingest. Default: all three.",
)
@click.option("--refresh", is_flag=True)
def ingest_ngs(season: int, stat_type: str, refresh: bool) -> None:
    """Pull Next Gen Stats (2016+). See ADR-0012."""
    from .ingest import ngs

    if stat_type == "all":
        results = ngs.run_all(season, refresh=refresh)
    else:
        results = [ngs.run(stat_type, season, refresh=refresh)]  # type: ignore[arg-type]
    for r in results:
        click.echo(
            f"stat_type={r.stat_type} season={r.season} "
            f"rows_ingested={r.rows_ingested} rows_written={r.rows_written} "
            f"skipped_player={r.skipped_unknown_player} "
            f"skipped_team={r.skipped_unknown_team}"
        )


@ingest.command(name="pfr-def-coverage")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pfr_def_coverage(season: int, refresh: bool) -> None:
    """Pull PFR advanced defensive coverage stats for CBs (2018+)."""
    from .ingest import pfr

    result = pfr.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match}"
    )


@ingest.command(name="pfr-def-coverage-s")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pfr_def_coverage_s(season: int, refresh: bool) -> None:
    """Pull PFR advanced defensive stats for safeties (2018+)."""
    from .ingest import pfr_safety

    result = pfr_safety.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match} "
        f"skipped_not_safety={result.rows_skipped_not_safety}"
    )


@ingest.command(name="pfr-def-passrush")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pfr_def_passrush(season: int, refresh: bool) -> None:
    """Pull PFR pass-rush stats for EDGE and iDL players (2018+)."""
    from .ingest import pfr_dl

    result = pfr_dl.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match} "
        f"skipped_not_dl={result.rows_skipped_not_dl}"
    )


@ingest.command(name="pfr-def-lb")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pfr_def_lb(season: int, refresh: bool) -> None:
    """Pull PFR + nflvs stats for LB players (2018+)."""
    from .ingest import pfr_lb

    result = pfr_lb.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match} "
        f"skipped_not_lb={result.rows_skipped_not_lb}"
    )


@ingest.command(name="ftn-receiving")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_ftn_receiving(season: int, refresh: bool) -> None:
    """Pull FTN charting receiver flags joined to PBP (2022+)."""
    from .ingest import ftn_receiving

    result = ftn_receiving.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_written={result.rows_written} "
        f"skipped_no_gsis_match={result.rows_skipped_no_gsis_match}"
    )


@ingest.command(name="all")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_all(season: int, refresh: bool) -> None:
    """Run every ingest source for a season, in dependency order."""
    ctx = click.get_current_context()
    ctx.invoke(ingest_rosters, season=season, refresh=refresh)
    ctx.invoke(ingest_snap_counts, season=season, refresh=refresh)
    ctx.invoke(ingest_depth_charts, season=season, refresh=refresh)
    ctx.invoke(ingest_pbp, season=season, refresh=refresh)
    if season >= 2016:
        ctx.invoke(ingest_ngs, season=season, stat_type="all", refresh=refresh)
    if season >= 2018:
        ctx.invoke(ingest_pfr_def_coverage, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_coverage_s, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_passrush, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_lb, season=season, refresh=refresh)
    if season >= 2022:
        ctx.invoke(ingest_ftn_receiving, season=season, refresh=refresh)


@main.command()
@click.option("--season", type=int, required=True)
@click.option(
    "--position",
    type=str,
    default=None,
    help="Limit to a single position (QB, RB, WR, TE, CB, S, EDGE, iDL, LB). Omit to grade all.",
)
def grade(season: int, position: str | None) -> None:
    """Compute season grades (QB/RB/WR/TE/CB/S/EDGE/iDL/LB v1)."""
    from .grading import run as grading_run

    summary = grading_run.run(season=season, position=position)
    for pos, result in summary.by_position.items():
        # Per-position RunResult dataclasses carry position-specific
        # counters (n_qbs_total, n_rbs_total, …). Probe generically.
        _TOTAL_ATTRS = (
            "n_qbs_total", "n_rbs_total", "n_wrs_total", "n_tes_total",
            "n_cbs_total", "n_safeties_total", "n_edges_total", "n_idls_total",
            "n_lbs_total",
        )
        _QUAL_ATTRS = (
            "n_qbs_qualified", "n_rbs_qualified", "n_wrs_qualified",
            "n_tes_qualified", "n_cbs_qualified", "n_safeties_qualified",
            "n_edges_qualified", "n_idls_qualified", "n_lbs_qualified",
        )
        total_attr = next((a for a in _TOTAL_ATTRS if hasattr(result, a)), None)
        qualified_attr = next((a for a in _QUAL_ATTRS if hasattr(result, a)), None)
        click.echo(
            f"position={pos} season={result.season} "
            f"total={getattr(result, total_attr) if total_attr else '?'} "
            f"qualified={getattr(result, qualified_attr) if qualified_attr else '?'} "
            f"stat_components_written={result.stat_components_written} "
            f"season_grades_written={result.season_grades_written}"
        )


@main.command(name="backfill-team-context")
@click.option("--season", type=int, required=True)
def backfill_team_context(season: int) -> None:
    """Populate season_grades.team_abbr and team_season_epa for a season.

    Run after grading. Idempotent — safe to re-run.
    """
    from .db import get_engine
    from .grading.team_context import backfill_team_abbr, compute_team_epa

    engine = get_engine()
    with engine.begin() as conn:
        n_abbr = backfill_team_abbr(conn, season)
        n_epa = compute_team_epa(conn, season)
    click.echo(f"season={season} team_abbr_updated={n_abbr} team_epa_written={n_epa}")


@main.command()
def career() -> None:
    """Compute career grades from existing season grades."""
    # TODO(step 8): wire up pipeline.career.run()
    click.echo("[stub] career smoothing")


@main.command()
@click.option("--season", type=int, required=True)
def validate(season: int) -> None:
    """Run the validation suite for a season's grades."""
    # TODO: wire up pipeline.validation.run(season=season)
    click.echo(f"[stub] validate season={season}")


@main.command(name="gen-types")
@click.option("--check", is_flag=True, help="Exit non-zero if file is stale (CI mode).")
def gen_types(check: bool) -> None:
    """Generate web/src/types/db.generated.ts from the live DB schema."""
    from . import gen_ts_types

    raise SystemExit(gen_ts_types.write(check=check))


@main.command()
@click.option("--seeds", is_flag=True, help="Also apply db/seeds/*.sql")
@click.option("--dry-run", is_flag=True)
def migrate(seeds: bool, dry_run: bool) -> None:
    """Apply pending SQL migrations from db/migrations/."""
    from . import migrate as migrate_mod

    n = migrate_mod.run(seeds=seeds, dry_run=dry_run)
    click.echo(f"Applied {n} migration(s)." if n else "No pending migrations.")


@main.command()
@click.option("--season", type=int, required=True)
def rebuild(season: int) -> None:
    """Ingest + grade + validate for a single season. Convenience for MVP dev."""
    ctx = click.get_current_context()
    ctx.invoke(ingest_all, season=season, refresh=False)
    ctx.invoke(grade, season=season, position=None)
    ctx.invoke(validate, season=season)


if __name__ == "__main__":
    main()
