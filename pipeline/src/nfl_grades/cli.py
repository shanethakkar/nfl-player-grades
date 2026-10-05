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


@ingest.command(name="pfr-rb-rush")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_pfr_rb_rush(season: int, refresh: bool) -> None:
    """Pull PFR rush-advanced stats for RBs (2018+) — yards_after_contact, broken_tackles."""
    from .ingest import pfr_rush

    result = pfr_rush.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_pfr_match={result.rows_skipped_no_pfr_match} "
        f"skipped_not_rb={result.rows_skipped_not_rb}"
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


@ingest.command(name="kicker-stats")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_kicker_stats(season: int, refresh: bool) -> None:
    """Pull kicker FG/XP stats from nflvs_player_stats (2016+)."""
    from .ingest import kicker as kicker_ingest

    result = kicker_ingest.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_match={result.rows_skipped_no_match}"
    )


@ingest.command(name="qb-stats")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_qb_stats(season: int, refresh: bool) -> None:
    """Pull QB box-score volume stats from nflvs_player_stats (2016+)."""
    from .ingest import qb_stats as qb_stats_ingest

    result = qb_stats_ingest.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_match={result.rows_skipped_no_match}"
    )


@ingest.command(name="skill-stats")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_skill_stats(season: int, refresh: bool) -> None:
    """Pull RB/WR/TE box-score volume stats from nflvs_player_stats (2016+)."""
    from .ingest import skill_player_stats as skill_ingest

    result = skill_ingest.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_match={result.rows_skipped_no_match}"
    )


@ingest.command(name="defensive-stats")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_defensive_stats(season: int, refresh: bool) -> None:
    """Pull CB/S/EDGE/iDL/LB box-score volume stats from nflvs_player_stats (2016+)."""
    from .ingest import defensive_player_stats as def_ingest

    result = def_ingest.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_match={result.rows_skipped_no_match}"
    )


@ingest.command(name="pixel-headshots")
@click.option("--position", type=str, default=None,
              help="Filter to a single position (QB/RB/WR/...). Omit to include all.")
@click.option("--season", type=int, default=2025, show_default=True)
@click.option("--qualified-only", is_flag=True, default=False,
              help="Skip players who didn't qualify (recommended).")
@click.option("--player-id", type=int, default=None,
              help="Single player by player_id. Overrides other filters.")
@click.option("--force", is_flag=True, default=False,
              help="Regenerate even if PNG already exists.")
@click.option("--seed", type=int, default=99, show_default=True,
              help="face-to-many seed. Change to re-roll a player whose initial generation had artifacts.")
def ingest_pixel_headshots(
    position: str | None,
    season: int,
    qualified_only: bool,
    player_id: int | None,
    force: bool,
    seed: int,
) -> None:
    """Generate pixel-art headshots via Replicate (face-to-many + bg removal).

    Saves to web/public/headshots/{player_id}.png + manifest.json.
    Throttled to 6 req/min (Replicate free-tier rate limit).
    """
    from .ingest import pixel_headshots

    result = pixel_headshots.run(
        position=position,
        season=season,
        qualified_only=qualified_only,
        player_id=player_id,
        force=force,
        seed=seed,
    )
    click.echo(
        f"targeted={result.targeted} "
        f"generated={result.generated} "
        f"skipped_existing={result.skipped_existing} "
        f"failed={result.failed}"
    )


@ingest.command(name="punter-stats")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_punter_stats(season: int, refresh: bool) -> None:
    """Pull punter stats from pbp punt_attempt rows (2016+)."""
    from .ingest import punter as punter_ingest

    result = punter_ingest.run(season, refresh=refresh)
    click.echo(
        f"season={result.season} "
        f"rows_ingested={result.rows_ingested} "
        f"rows_written={result.rows_written} "
        f"skipped_no_match={result.rows_skipped_no_match}"
    )


@ingest.command(name="team-ol")
@click.option("--season", type=int, required=True)
@click.option("--refresh", is_flag=True)
def ingest_team_ol(season: int, refresh: bool) -> None:
    """Aggregate team-level OL stats from pbp + pfr_advstats_rush (2018+)."""
    from .ingest import team_ol

    result = team_ol.run(season, refresh=refresh)
    click.echo(f"season={result.season} teams_written={result.teams_written}")


@ingest.command(name="team-records")
@click.option("--season", type=int, required=True)
def ingest_team_records(season: int) -> None:
    """Pull regular-season records (W-L, point diff) from nflverse schedules.

    Used by the team leaderboard on /teams as context columns. Not part
    of grading.
    """
    from .ingest import team_season_records

    result = team_season_records.run(season)
    click.echo(f"season={result.season} teams_written={result.teams_written}")


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
        ctx.invoke(ingest_kicker_stats, season=season, refresh=refresh)
        ctx.invoke(ingest_punter_stats, season=season, refresh=refresh)
        ctx.invoke(ingest_qb_stats, season=season, refresh=refresh)
        ctx.invoke(ingest_skill_stats, season=season, refresh=refresh)
        ctx.invoke(ingest_defensive_stats, season=season, refresh=refresh)
    if season >= 2018:
        ctx.invoke(ingest_pfr_def_coverage, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_coverage_s, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_passrush, season=season, refresh=refresh)
        ctx.invoke(ingest_pfr_def_lb, season=season, refresh=refresh)
        ctx.invoke(ingest_team_ol, season=season, refresh=refresh)
    if season >= 2022:
        ctx.invoke(ingest_ftn_receiving, season=season, refresh=refresh)


@main.command()
@click.option("--season", type=int, required=True)
@click.option(
    "--position",
    type=str,
    default=None,
    help="Limit to a single position (QB, RB, WR, TE, CB, S, EDGE, iDL, LB, K, P, OL). Omit to grade all.",
)
def grade(season: int, position: str | None) -> None:
    """Compute season grades (QB/RB/WR/TE/CB/S/EDGE/iDL/LB v1)."""
    from .grading import run as grading_run

    summary = grading_run.run(season=season, position=position)
    for pos, result in summary.by_position.items():
        if isinstance(result, grading_run.NotGraded):
            click.echo(f"position={pos} season={result.season} not graded: {result.reason}")
            continue
        # Per-position RunResult dataclasses carry position-specific
        # counters (n_qbs_total, n_rbs_total, …). Probe generically.
        _TOTAL_ATTRS = (
            "n_qbs_total", "n_rbs_total", "n_wrs_total", "n_tes_total",
            "n_cbs_total", "n_safeties_total", "n_edges_total", "n_idls_total",
            "n_lbs_total", "n_kickers_total", "n_punters_total", "n_teams_total",
        )
        _QUAL_ATTRS = (
            "n_qbs_qualified", "n_rbs_qualified", "n_wrs_qualified",
            "n_tes_qualified", "n_cbs_qualified", "n_safeties_qualified",
            "n_edges_qualified", "n_idls_qualified", "n_lbs_qualified",
            "n_kickers_qualified", "n_punters_qualified", "n_teams_qualified",
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


@main.command(name="grade-teams")
@click.option("--season", type=int, required=True)
def grade_teams(season: int) -> None:
    """Compute team-level overall + Off/Def/ST grades (ADR-0026).

    Aggregates already-computed player + OL grades into per-team
    Offense / Defense / ST / Overall scores. Idempotent — re-running
    overwrites the season's team_grades rows.
    """
    from .grading import team

    result = team.run(season=season)
    click.echo(
        f"season={result.season} teams={result.n_teams} components={result.n_components}"
    )


@main.command()
@click.option("--season", type=int, required=True)
@click.option("--position", type=str, required=True)
@click.option(
    "--weight",
    "weight_overrides",
    multiple=True,
    help='Override a single weight, e.g. --weight te_drop_rate=-0.10. Repeatable.',
)
@click.option("--top", type=int, default=20, help="Number of rows in the head/tail summary.")
@click.option(
    "--show-deltas",
    is_flag=True,
    help="Also print the players whose grade moved most (in either direction).",
)
def preview(
    season: int,
    position: str,
    weight_overrides: tuple[str, ...],
    top: int,
    show_deltas: bool,
) -> None:
    """Preview a weight change without writing to the database.

    Reads existing stat_components.z_score, applies the candidate weights,
    and prints the resulting leaderboard side-by-side with the currently
    shipped grades. Useful for "what if I bumped wr_drop_rate to -0.07"
    style experiments before running the real grader.

    Examples:

      nflgrades preview --season 2024 --position TE --weight te_drop_rate=-0.10
      nflgrades preview --season 2024 --position RB --weight rb_rec_epa_per_target=0.05 --weight rb_yac_over_expected_per_rec=0.28
    """
    from .grading.preview import parse_weight_overrides, preview_position
    from .grading.scoring import InsufficientCohortError

    overrides = parse_weight_overrides(weight_overrides)
    if not overrides:
        click.echo("(no --weight overrides supplied — preview will match current grades)")
    else:
        click.echo("Overrides:")
        for k, v in sorted(overrides.items()):
            click.echo(f"  {k} = {v:+.3f}")

    try:
        df = preview_position(season=season, position=position, overrides=overrides)
    except InsufficientCohortError as exc:
        raise click.ClickException(f"{position} {season} can't be graded: {exc}") from exc

    pd_repr = df.head(top)[
        ["preview_rank", "full_name", "role", "current_grade", "preview_grade", "delta"]
    ].copy()
    pd_repr["current_grade"] = pd_repr["current_grade"].map(lambda v: f"{v:6.2f}")
    pd_repr["preview_grade"] = pd_repr["preview_grade"].map(lambda v: f"{v:6.2f}")
    pd_repr["delta"] = pd_repr["delta"].map(lambda v: f"{v:+5.2f}")
    click.echo(f"\nTop {top} ({position} {season}):")
    click.echo(pd_repr.to_string(index=False))

    if show_deltas:
        biggest = df.assign(abs_delta=df["delta"].abs()).sort_values(
            "abs_delta", ascending=False
        )
        head = biggest.head(top)[
            ["full_name", "role", "current_rank", "preview_rank", "current_grade",
             "preview_grade", "delta"]
        ].copy()
        head["current_grade"] = head["current_grade"].map(lambda v: f"{v:6.2f}")
        head["preview_grade"] = head["preview_grade"].map(lambda v: f"{v:6.2f}")
        head["delta"] = head["delta"].map(lambda v: f"{v:+5.2f}")
        click.echo(f"\nBiggest movers (top {top}):")
        click.echo(head.to_string(index=False))


@main.command()
@click.option("--season", type=int, required=True)
@click.option("--position", type=str, required=True)
def regrade(season: int, position: str) -> None:
    """Recompute composite_grade / composite_z / percentile from existing
    stat_components z-scores, using current weights.py. Use this after a
    pure weight change — no SQL re-extract, no z-score recompute.

    For schema changes (adding/removing components, changing SQL), use the
    full ``grade`` command instead.

    Idempotent.
    """
    from .grading.preview import regrade_from_components
    from .grading.scoring import InsufficientCohortError

    try:
        n = regrade_from_components(season=season, position=position)
    except InsufficientCohortError as exc:
        raise click.ClickException(f"{position} {season} can't be graded: {exc}") from exc
    click.echo(f"position={position} season={season} season_grades_updated={n}")


@main.command()
@click.option("--diagnose", is_flag=True, help="Print Pro Bowl name-match diagnostics.")
@click.option(
    "--next-season",
    is_flag=True,
    help="Label each season with the following season's Pro Bowl instead of its own.",
)
def validity(diagnose: bool, next_season: bool) -> None:
    """Pro Bowl face-validity report for all positions (ADR-0029).

    Pearson r between composite grade and same-season Pro Bowl selection
    (0/1) for qualified player-seasons, joined on name and position group.
    Seasons without a Pro Bowl roster are excluded. A sanity check only:
    Formula changes are judged by the evaluation harness, not by this.

    Pro Bowl data: pipeline/data/pro_bowl_selections.csv.
    """
    from .grading.validity import diagnose_match_rate, run_all

    if diagnose:
        diag = diagnose_match_rate()
        click.echo("Pro Bowl name-match diagnostics (name + position group):")
        click.echo(f"  n_pro_bowl_unique_players = {diag['n_pro_bowl_unique_players']}")
        click.echo(f"  n_matched_in_grades       = {diag['n_matched_in_grades']}")
        click.echo(f"  match_rate                = {diag['match_rate']:.1%}")
        click.echo(f"  n_unmatched               = {diag['n_unmatched']}")
        click.echo(f"  unmatched sample          = {diag['unmatched_sample']}")
        click.echo()

    results = run_all(next_season=next_season)
    click.echo(f"Pro Bowl label: {'next' if next_season else 'same'} season")
    click.echo(
        f"{'POS':<6} {'n_qual':>7} {'n_PB':>5} {'PB_rate':>8} "
        f"{'pearson_r':>10}   seasons"
    )
    click.echo("-" * 60)
    for r in results:
        r_str = f"{r.pearson_r:>+10.3f}" if r.pearson_r == r.pearson_r else f"{'n/a':>10}"
        click.echo(
            f"{r.position:<6} {r.n_player_seasons:>7d} "
            f"{r.n_pro_bowls:>5d} "
            f"{r.pro_bowl_rate:>7.1%} "
            f"{r_str}   {r.seasons_covered}"
        )


@main.command()
@click.option("--position", type=str, required=True, help="Position to evaluate (QB so far).")
@click.option(
    "--weight",
    "weight_overrides",
    multiple=True,
    help="Proposed weight, e.g. --weight qb_success_rate=0.05. Repeatable. "
    "Also sets a Candidate's weight.",
)
@click.option(
    "--candidate",
    "candidate_names",
    multiple=True,
    help="Add a Candidate Component to the panel (give it a weight with --weight). Repeatable.",
)
@click.option("--boot", "n_boot", type=int, default=2000, show_default=True,
              help="Bootstrap draws for the paired deltas.")
@click.option("--seed", type=int, default=0, show_default=True)
def evaluate(
    position: str,
    weight_overrides: tuple[str, ...],
    candidate_names: tuple[str, ...],
    n_boot: int,
    seed: int,
) -> None:
    """Score the current or a proposed Formula without reputation (ADR-0029).

    Reports Reliability (odd vs even weeks, Spearman-Brown), Portability
    (YoY for team changers) and next-season prediction, with CIs, for the
    2016-2022 fit window and the 2023-2025 hold-out. With --weight or
    --candidate, also scores the proposed Formula, prints paired deltas
    and applies the ship rule to the hold-out. Read-only.

    Examples:

      nflgrades evaluate --position QB

      nflgrades evaluate --position QB --weight qb_success_rate=0.05

      nflgrades evaluate --position QB --candidate qb_sack_rate --weight qb_sack_rate=-0.10
    """
    from .db import get_engine
    from .grading import evaluation, panels
    from .grading.preview import parse_weight_overrides

    source = panels.POSITIONS.get(position)
    if source is None:
        raise click.ClickException(
            f"no evaluation panel for {position}; supported: {', '.join(panels.POSITIONS)}"
        )
    candidates = []
    for name in dict.fromkeys(candidate_names):
        cand = panels.CANDIDATES.get(name)
        if cand is None or cand.position != position:
            known = [c for c, v in panels.CANDIDATES.items() if v.position == position]
            raise click.ClickException(f"unknown {position} Candidate {name!r}; known: {known}")
        candidates.append(cand)

    try:
        overrides = parse_weight_overrides(weight_overrides)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    known_components = set(source.weights) | {c.name for c in candidates}
    unknown = sorted(set(overrides) - known_components)
    if unknown:
        raise click.ClickException(
            f"--weight names unknown Components {unknown}; add Candidates with --candidate"
        )
    unweighted = [c.name for c in candidates if c.name not in overrides]
    if unweighted:
        raise click.ClickException(f"give each Candidate a weight: --weight {unweighted[0]}=W")

    proposed = None
    if overrides:
        proposed = evaluation.Formula(
            weights={**source.weights, **overrides},
            shrinkage_k={**source.shrinkage_k, **{c.name: c.shrinkage_k for c in candidates}},
        )
        click.echo("Proposed (vs current):")
        for name, w in sorted(overrides.items()):
            click.echo(f"  {name}: {source.weights.get(name, 0.0):+.3f} -> {w:+.3f}")
        for c in candidates:
            click.echo(f"  Candidate {c.name}: {c.description}")

    click.echo(f"Reading {position} panels (full season, odd weeks, even weeks)...")
    with get_engine().connect() as conn:
        data = panels.load(conn, source, candidates=candidates)

    reports = evaluation.evaluate(
        data.panel,
        data.roster,
        source.formula,
        proposed=proposed,
        primary=source.primary,
        pro_bowl=data.pro_bowl,
        n_boot=n_boot,
        seed=seed,
    )
    click.echo(evaluation.format_report(reports))
    click.echo(
        f"\nCIs: Fisher-z per metric; deltas from {n_boot} player-clustered bootstrap draws. "
        f"Primary Component: {source.primary}. Pro Bowl r is face validity only."
    )
    if proposed is not None:
        holdout = next(r for r in reports if r.name == "holdout")
        verdict = evaluation.ship_rule(holdout)
        click.echo(f"\nShip rule (hold-out): {'PASS' if verdict.passes else 'FAIL'}")
        for reason in verdict.reasons:
            click.echo(f"  - {reason}")
        if verdict.passes:
            click.echo("  - still needs skill-tree / face-validity review before shipping")


@main.command(name="audit-candidates")
@click.option(
    "--position",
    type=str,
    required=True,
    help="Position to audit. Currently only QB is implemented as a worked example; "
         "other positions get candidate fetchers added when their audit lands.",
)
def audit_candidates(position: str) -> None:
    """Legacy candidate table: YoY, spread, overlap and Pro Bowl r per stat.

    The four-criterion verdict hints predate ADR-0029 and no longer decide
    anything; use it for the redundancy column (max_r). Formula changes go
    through ``nflgrades evaluate``. The Pro Bowl column is same-season and
    position-matched.

    The candidate set per position is defined in
    ``grading/exhaustive_audit.py::<pos>_candidates()``. Expand that
    function during each position's audit phase.
    """
    from .grading.exhaustive_audit import (
        format_results_table,
        run_cb_audit,
        run_edge_audit,
        run_idl_audit,
        run_k_audit,
        run_lb_audit,
        run_p_audit,
        run_qb_audit,
        run_rb_audit,
        run_s_audit,
        run_te_audit,
        run_wr_audit,
    )

    pos = position.upper()
    runners = {
        "QB": run_qb_audit,
        "RB": run_rb_audit,
        "WR": run_wr_audit,
        "TE": run_te_audit,
        "CB": run_cb_audit,
        "S": run_s_audit,
        "EDGE": run_edge_audit,
        "IDL": run_idl_audit,
        "LB": run_lb_audit,
        "K": run_k_audit,
        "P": run_p_audit,
    }
    if pos not in runners:
        click.echo(
            f"Position {pos!r} not yet implemented. Available: {sorted(runners)}. "
            "Add a <pos>_candidates() function in grading/exhaustive_audit.py "
            "to enable other positions."
        )
        raise SystemExit(1)
    results = runners[pos]()
    click.echo(format_results_table(results))


@main.command()
@click.option("--season", type=int, required=True)
def weekly(season: int) -> None:
    """Refresh a season end-to-end: fresh data, every ingest stage, then
    every grade in one transaction (ADR-0031).

    Fails without writing anything if a source isn't through the last
    completed regular-season week on the schedule. Run weekly in season
    (GitHub Actions) or by hand to re-run after a fix.
    """
    from . import weekly as weekly_mod

    result = weekly_mod.run(season)
    if result.through_week is None:
        click.echo(f"season={season}: no regular-season week completed yet; nothing to do")
        return
    click.echo(
        f"season={season} through_week={result.through_week} stages={len(result.stages)}"
    )


@main.command(name="backfill-team-context")
@click.option("--season", type=int, required=True)
def backfill_team_context(season: int) -> None:
    """Populate season_grades.team_abbr and team_season_epa for a season.

    Run after grading. Idempotent — safe to re-run.
    """
    from .grading.team_context import run as backfill_run

    n_abbr, n_epa = backfill_run(season)
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
