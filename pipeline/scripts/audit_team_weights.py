"""Audit position weights for team grading (ADR-0026).

Two empirical anchors:

  1. **Ridge regression** of team success on per-position team-aggregated grades.
     Coefficients = empirical position weights. Run per phase
     (offense / defense / ST) so multicollinearity within phase is contained.

  2. **Cap allocation** as a market-derived prior. Hardcoded league-average
     percentages from public sources (Spotrac, Over The Cap) since the
     numbers don't shift much year over year.

Output: a comparison table per phase showing
  - Prior weight (from ADR-0026)
  - Cap-allocation weight (market signal)
  - Regression weight against point differential
  - Regression weight against avg closing spread

Plus diagnostic R² and YoY stability checks.

Usage:
    python pipeline/scripts/audit_team_weights.py [--out OUTFILE]

Run from project root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

# Make the nfl_grades package importable when run from project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_grades.db import get_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Phase / position mapping
# ---------------------------------------------------------------------------

OFFENSE_POSITIONS = ["QB", "RB", "WR", "TE", "OL"]
DEFENSE_POSITIONS = ["EDGE", "iDL", "LB", "CB", "S"]
ST_POSITIONS = ["K", "P"]

PHASES = {
    "offense": OFFENSE_POSITIONS,
    "defense": DEFENSE_POSITIONS,
    "st": ST_POSITIONS,
}

SNAP_COL_BY_PHASE = {
    "offense": "snaps_offense",
    "defense": "snaps_defense",
    "st": "snaps_special",
}


# ---------------------------------------------------------------------------
# Cap allocation reference (Spotrac / OTC league averages, smoothed across
# 2022-2024 cap years). Documented in the audit doc; numbers update slowly.
# Within-phase shares sum to 1.0.
# ---------------------------------------------------------------------------

CAP_ALLOCATION = {
    "offense": {
        "QB": 0.28,
        "OL": 0.43,
        "WR": 0.18,
        "TE": 0.06,
        "RB": 0.05,
    },
    "defense": {
        "EDGE": 0.27,
        "CB": 0.24,
        "iDL": 0.19,
        "LB": 0.16,
        "S": 0.14,
    },
    "st": {
        "K": 0.52,
        "P": 0.48,
    },
}


# ---------------------------------------------------------------------------
# Prior weights (current ADR-0026 v1 design)
# ---------------------------------------------------------------------------

# v1.0 phase-level: reconciled position weights from the per-phase audit
# above. Used to compute offense/defense/st phase grades per team-season,
# which then feed the phase-level regression at the bottom.
V10_WEIGHTS = {
    "offense": {"QB": 0.45, "OL": 0.25, "WR": 0.13, "RB": 0.09, "TE": 0.08},
    "defense": {"EDGE": 0.24, "CB": 0.24, "LB": 0.22, "S": 0.20, "iDL": 0.10},
    "st": {"K": 0.52, "P": 0.48},
}

# Cap-allocation phase split: offense and defense are roughly equal in
# total cap spend; ST is the small slice. Source: Spotrac, smoothed.
CAP_PHASE_WEIGHTS = {"offense": 0.49, "defense": 0.49, "st": 0.02}

PRIOR_PHASE_WEIGHTS = {"offense": 0.45, "defense": 0.45, "st": 0.10}


PRIOR_WEIGHTS = {
    "offense": {"QB": 0.40, "OL": 0.25, "WR": 0.15, "RB": 0.10, "TE": 0.10},
    "defense": {"EDGE": 0.25, "CB": 0.25, "LB": 0.20, "iDL": 0.15, "S": 0.15},
    "st": {"K": 0.55, "P": 0.45},
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_team_position_grades(seasons: tuple[int, int]) -> pd.DataFrame:
    """Return one row per (team_abbr, season, position) with the snap-weighted
    average composite grade across all players at that position on that team.

    Methodology mirrors the team-grade Stage 1 (ADR-0026): players who
    logged snaps at the position contribute to the average, weighted by
    snaps. OL is handled separately (it's already team-level)."""
    engine = get_engine()

    # Player positions (everything except OL): join season_grades to
    # player_seasons to get snap counts + team_abbr.
    sql_player = """
        SELECT
            t.abbr AS team_abbr,
            sg.season,
            sg.position,
            sg.player_id,
            sg.composite_grade,
            ps.snaps_offense,
            ps.snaps_defense,
            ps.snaps_special
        FROM season_grades sg
        JOIN player_seasons ps
          ON ps.player_id = sg.player_id AND ps.season = sg.season
        JOIN teams t ON t.team_id = ps.team_id
        WHERE sg.season BETWEEN :s_lo AND :s_hi
          AND sg.position IN ('QB','RB','WR','TE','EDGE','iDL','LB','CB','S','K','P')
    """
    with engine.connect() as conn:
        player_df = pd.read_sql(
            text(sql_player),
            conn,
            params={"s_lo": seasons[0], "s_hi": seasons[1]},
        )

    # Pick the right snap column per position and treat 0 / NaN as no
    # contribution at this position.
    def snap_for_row(row: pd.Series) -> float:
        if row["position"] in OFFENSE_POSITIONS:
            return row["snaps_offense"] or 0
        if row["position"] in DEFENSE_POSITIONS:
            return row["snaps_defense"] or 0
        if row["position"] in ST_POSITIONS:
            return row["snaps_special"] or 0
        return 0

    player_df["snaps"] = player_df.apply(snap_for_row, axis=1)
    player_df = player_df[player_df["snaps"] > 0]

    # Snap-weighted average per (team, season, position).
    grp = player_df.groupby(["team_abbr", "season", "position"])
    out = grp.apply(
        lambda g: pd.Series(
            {
                "position_grade": float(
                    np.average(g["composite_grade"], weights=g["snaps"])
                ),
                "total_snaps": int(g["snaps"].sum()),
                "n_players": int(len(g)),
            }
        )
    ).reset_index()

    # OL: pull from team_ol_grades and append as if it were just another row.
    sql_ol = """
        SELECT
            t.abbr AS team_abbr,
            tog.season,
            'OL' AS position,
            tog.composite_grade AS position_grade,
            0 AS total_snaps,
            5 AS n_players
        FROM team_ol_grades tog
        JOIN teams t ON t.team_id = tog.team_id
        WHERE tog.season BETWEEN :s_lo AND :s_hi
    """
    with engine.connect() as conn:
        ol_df = pd.read_sql(
            text(sql_ol),
            conn,
            params={"s_lo": seasons[0], "s_hi": seasons[1]},
        )
    return pd.concat([out, ol_df], ignore_index=True)


def load_team_outcomes(seasons: tuple[int, int]) -> pd.DataFrame:
    """For each (team_abbr, season), compute:
      - point_diff: sum(points_scored - points_allowed) across regular-season games
      - avg_closing_spread: average closing spread *favoring* the team
        (positive = team was favored; negative = team was underdog)

    Uses nflreadpy.load_schedules — has home/away scores and the closing
    spread_line (= home team's spread by convention).
    """
    import nflreadpy as nfl  # local import; nflreadpy is in the ingest extras

    seasons_list = list(range(seasons[0], seasons[1] + 1))
    sched = nfl.load_schedules(seasons_list).to_pandas()
    sched = sched[sched["game_type"] == "REG"].copy()

    # Build two rows per game — one from each team's perspective.
    home = pd.DataFrame(
        {
            "team_abbr": sched["home_team"],
            "season": sched["season"],
            "points_for": sched["home_score"],
            "points_against": sched["away_score"],
            # spread_line is home team's spread: negative if home favored,
            # positive if home underdog. Convert to "team favored by N":
            # team_spread = -spread_line for home perspective.
            "team_spread": -sched["spread_line"],
        }
    )
    away = pd.DataFrame(
        {
            "team_abbr": sched["away_team"],
            "season": sched["season"],
            "points_for": sched["away_score"],
            "points_against": sched["home_score"],
            "team_spread": sched["spread_line"],
        }
    )
    long = pd.concat([home, away], ignore_index=True).dropna(
        subset=["points_for", "points_against"]
    )
    long["point_diff_game"] = long["points_for"] - long["points_against"]

    out = (
        long.groupby(["team_abbr", "season"])
        .agg(
            point_diff=("point_diff_game", "sum"),
            avg_closing_spread=("team_spread", "mean"),
            n_games=("point_diff_game", "size"),
        )
        .reset_index()
    )
    return out


def build_feature_matrix(
    team_pos: pd.DataFrame, outcomes: pd.DataFrame
) -> pd.DataFrame:
    """Pivot team-position grades into wide format and join outcomes."""
    wide = team_pos.pivot_table(
        index=["team_abbr", "season"],
        columns="position",
        values="position_grade",
        aggfunc="first",
    ).reset_index()
    merged = wide.merge(outcomes, on=["team_abbr", "season"], how="inner")
    return merged


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------


def fit_phase_regression(
    df: pd.DataFrame, positions: list[str], target: str, alpha: float = 1.0
) -> dict:
    """Ridge regression of `target` on the position columns. Drops rows
    with any missing position grade (rare — most happen at K/P)."""
    cols = [p for p in positions if p in df.columns]
    sub = df.dropna(subset=cols + [target]).copy()
    X = sub[cols].values
    y = sub[target].values

    # Standardize features so ridge penalty is comparable across them.
    sx = StandardScaler()
    Xs = sx.fit_transform(X)

    model = Ridge(alpha=alpha)
    model.fit(Xs, y)

    # Coefficients are in standardized units. Take their absolute values,
    # normalize to sum to 1 within phase — gives empirical weights.
    abs_coefs = np.abs(model.coef_)
    norm_weights = abs_coefs / abs_coefs.sum() if abs_coefs.sum() > 0 else abs_coefs

    # R² on the same data (in-sample; small N so we don't bother with CV here).
    r2 = float(model.score(Xs, y))

    return {
        "positions": cols,
        "raw_coefs": dict(zip(cols, model.coef_.tolist())),
        "normalized_weights": dict(zip(cols, norm_weights.tolist())),
        "r2": r2,
        "n": int(len(sub)),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def fmt_weight_table(phase: str, regress_pd: dict, regress_spread: dict) -> str:
    """One-phase comparison table: prior vs cap vs regression(point diff) vs regression(spread)."""
    positions = PHASES[phase]
    prior = PRIOR_WEIGHTS[phase]
    cap = CAP_ALLOCATION[phase]
    rpd = regress_pd["normalized_weights"]
    rsp = regress_spread["normalized_weights"]

    lines = []
    lines.append(f"\n### {phase.upper()}")
    lines.append(
        f"  (regression n={regress_pd['n']}, "
        f"R²(point_diff)={regress_pd['r2']:.3f}, "
        f"R²(spread)={regress_spread['r2']:.3f})\n"
    )
    lines.append(
        f"{'pos':<6} {'prior':>8} {'cap':>8} {'reg(PD)':>10} {'reg(spread)':>13}"
    )
    lines.append("-" * 50)
    for p in positions:
        line = f"{p:<6} {prior.get(p, 0):>8.3f} {cap.get(p, 0):>8.3f} {rpd.get(p, 0):>10.3f} {rsp.get(p, 0):>13.3f}"
        lines.append(line)
    return "\n".join(lines)


def diagnostic_pearson(df: pd.DataFrame, positions: list[str], target: str) -> dict:
    """Univariate Pearson r between each position's grade and the target.
    Surfaces the raw bivariate signal independent of the multivariate model."""
    out = {}
    for p in positions:
        if p not in df.columns:
            continue
        sub = df.dropna(subset=[p, target])
        if len(sub) < 3:
            out[p] = float("nan")
            continue
        out[p] = float(np.corrcoef(sub[p], sub[target])[0, 1])
    return out


# ---------------------------------------------------------------------------
# Phase-level audit (the v1.1 step)
#
# Uses the v1.0 reconciled position weights to compute offense/defense/st
# phase grades per team-season. Then regresses team success on those three
# phase grades. The resulting coefficients are the empirical phase weights
# — the analogue of the per-phase position-weight audit, but one level up.
# ---------------------------------------------------------------------------


def compute_phase_grades(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Add `offense_grade`, `defense_grade`, `st_grade` columns to df,
    computed from the v1.0 position weights. Rows with any missing
    position in a phase produce NaN for that phase grade (so they're
    dropped by the regression's dropna)."""
    out = df.copy()
    for phase, pos_weights in weights.items():
        positions = list(pos_weights.keys())
        # NaN-aware weighted sum: if any required position is missing, NaN.
        out[f"{phase}_grade"] = (
            sum(out[p] * w for p, w in pos_weights.items())
        )
    return out


def fit_phase_level_regression(
    df: pd.DataFrame, target: str, alpha: float = 1.0
) -> dict:
    """Regress `target` on the three phase grades (offense / defense / st).
    Coefficients normalized to sum to 1 = empirical phase weights."""
    cols = ["offense_grade", "defense_grade", "st_grade"]
    sub = df.dropna(subset=cols + [target]).copy()
    X = sub[cols].values
    y = sub[target].values

    sx = StandardScaler()
    Xs = sx.fit_transform(X)
    model = Ridge(alpha=alpha)
    model.fit(Xs, y)

    abs_coefs = np.abs(model.coef_)
    norm_weights = abs_coefs / abs_coefs.sum() if abs_coefs.sum() > 0 else abs_coefs

    # Map back to phase names.
    phase_keys = [c.replace("_grade", "") for c in cols]
    return {
        "raw_coefs": dict(zip(phase_keys, model.coef_.tolist())),
        "normalized_weights": dict(zip(phase_keys, norm_weights.tolist())),
        "r2": float(model.score(Xs, y)),
        "n": int(len(sub)),
    }


def fmt_phase_table(regress_pd: dict, regress_spread: dict) -> str:
    """Phase-level comparison: prior vs cap vs regression(PD) vs regression(spread)."""
    phases = ["offense", "defense", "st"]
    lines = []
    lines.append("\n### Phase weights")
    lines.append(
        f"  (regression n={regress_pd['n']}, "
        f"R²(point_diff)={regress_pd['r2']:.3f}, "
        f"R²(spread)={regress_spread['r2']:.3f})\n"
    )
    lines.append(
        f"{'phase':<10} {'prior':>8} {'cap':>8} {'reg(PD)':>10} {'reg(spread)':>13}"
    )
    lines.append("-" * 54)
    for ph in phases:
        line = (
            f"{ph:<10} "
            f"{PRIOR_PHASE_WEIGHTS[ph]:>8.3f} "
            f"{CAP_PHASE_WEIGHTS[ph]:>8.3f} "
            f"{regress_pd['normalized_weights'].get(ph, 0):>10.3f} "
            f"{regress_spread['normalized_weights'].get(ph, 0):>13.3f}"
        )
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-lo", type=int, default=2018)
    parser.add_argument("--season-hi", type=int, default=2024)
    parser.add_argument("--alpha", type=float, default=1.0, help="Ridge L2 strength")
    parser.add_argument("--out", type=str, default=None, help="Write report to file")
    args = parser.parse_args()

    print(f"Loading team-position grades for {args.season_lo}-{args.season_hi}...")
    team_pos = load_team_position_grades((args.season_lo, args.season_hi))
    print(f"  {len(team_pos)} (team, season, position) rows")

    print("Loading team outcomes (point diff + closing spread)...")
    outcomes = load_team_outcomes((args.season_lo, args.season_hi))
    print(f"  {len(outcomes)} (team, season) rows")

    df = build_feature_matrix(team_pos, outcomes)
    print(f"Feature matrix: {len(df)} (team, season) rows × {df.shape[1]} cols")

    lines = []
    lines.append("# Team weight audit — empirical (regression) + market (cap)")
    lines.append("")
    lines.append(f"Source seasons: {args.season_lo}-{args.season_hi}")
    lines.append(f"Ridge alpha: {args.alpha}")
    lines.append(f"Feature-matrix rows: {len(df)}")
    lines.append("")
    lines.append("## Per-phase weight comparison")

    for phase, positions in PHASES.items():
        regress_pd = fit_phase_regression(
            df, positions, target="point_diff", alpha=args.alpha
        )
        regress_spread = fit_phase_regression(
            df, positions, target="avg_closing_spread", alpha=args.alpha
        )
        lines.append(fmt_weight_table(phase, regress_pd, regress_spread))

    # Phase-level audit: use v1.0 reconciled position weights to compute
    # per-team offense/defense/st phase grades, then regress team success
    # on those. The resulting normalized coefficients are the empirical
    # phase weights.
    lines.append("\n\n## Phase-weight comparison (v1.1 audit)")
    lines.append("")
    lines.append(
        "Computed by aggregating per-position grades into offense/defense/st"
    )
    lines.append(
        "phase grades using the v1.0 reconciled weights, then regressing"
    )
    lines.append("team success on the three phase grades.")
    df_with_phases = compute_phase_grades(df, V10_WEIGHTS)
    phase_reg_pd = fit_phase_level_regression(
        df_with_phases, target="point_diff", alpha=args.alpha
    )
    phase_reg_spread = fit_phase_level_regression(
        df_with_phases, target="avg_closing_spread", alpha=args.alpha
    )
    lines.append(fmt_phase_table(phase_reg_pd, phase_reg_spread))

    # Univariate diagnostics — useful when regression coefficients look weird.
    lines.append("\n\n## Univariate Pearson r (per-position vs targets)")
    lines.append("\n(How much each position's grade alone correlates with team success.")
    lines.append(" Reading both this AND the multivariate weights above protects against")
    lines.append(" multicollinearity surprises.)\n")
    for phase, positions in PHASES.items():
        pd_corr = diagnostic_pearson(df, positions, "point_diff")
        sp_corr = diagnostic_pearson(df, positions, "avg_closing_spread")
        lines.append(f"\n### {phase.upper()}")
        lines.append(f"{'pos':<6} {'r(PD)':>8} {'r(spread)':>10}")
        lines.append("-" * 30)
        for p in positions:
            lines.append(
                f"{p:<6} {pd_corr.get(p, float('nan')):>8.3f} {sp_corr.get(p, float('nan')):>10.3f}"
            )

    report = "\n".join(lines)
    print()
    print(report)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.out}")


if __name__ == "__main__":
    main()
