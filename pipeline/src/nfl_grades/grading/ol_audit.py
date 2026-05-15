"""OL (offensive-line unit) audit framework.

Mirrors `exhaustive_audit.py` but for team-season candidates instead of
player-season. Pro Bowl validity is intentionally skipped per the locked
plan for ADR-0025: there is no "All-Pro OL unit" award and the per-team
Pro Bowl OL count proxy is too noisy to use as a gate.

Three criteria:
  1. YoY reliability (paired team-seasons)
  2. Cross-sectional discrimination (std in z-units within a season)
  3. Independence (max abs Pearson r vs other candidates in the set)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nfl_grades.db import get_engine

_OL_SEASONS = [
    (2018, 2019), (2019, 2020), (2020, 2021), (2021, 2022),
    (2022, 2023), (2023, 2024), (2024, 2025),
]


@dataclass(frozen=True)
class OLCandidateScore:
    name: str
    n_team_seasons: int
    yoy_mean_r: float
    xsect_std: float
    max_r_other: float
    max_r_partner: str
    verdict: str


def _fetch_team_ol_stats(engine: Engine) -> pd.DataFrame:
    sql = text("""
        SELECT t.abbr AS team_abbr, ts.team_id, ts.season,
               ts.dropbacks, ts.sacks_allowed, ts.qb_hits_allowed,
               ts.rushes, ts.rush_yards, ts.yards_before_contact,
               ts.rush_epa_total, ts.rushes_success, ts.rushes_stuffed,
               ts.rushes_explosive, ts.false_starts, ts.holdings
        FROM team_ol_stats ts JOIN teams t ON t.team_id = ts.team_id
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def ol_candidates(engine: Engine) -> dict[str, pd.DataFrame]:
    """Return dict of candidate_name -> panel(team_id, season, value).

    All candidates are derived from team_ol_stats. No external joins.
    """
    df = _fetch_team_ol_stats(engine)
    if df.empty:
        return {}

    drops = df["dropbacks"].astype(float).replace(0, np.nan)
    rushes = df["rushes"].astype(float).replace(0, np.nan)
    plays = drops + rushes

    df["sacks_allowed_per_dropback"] = df["sacks_allowed"] / drops
    df["qb_hits_allowed_per_dropback"] = df["qb_hits_allowed"] / drops
    # "Disruption" rate: sacks + hits combined per dropback (broader pressure proxy)
    df["pressure_proxy_per_dropback"] = (
        df["sacks_allowed"].astype(float) + df["qb_hits_allowed"].astype(float)
    ) / drops
    # Sack-to-hit conversion: when QB takes contact, how often does it become a sack?
    contacts = df["sacks_allowed"].astype(float) + df["qb_hits_allowed"].astype(float)
    df["sack_per_contact"] = df["sacks_allowed"].astype(float) / contacts.replace(0, np.nan)

    # Run blocking
    df["yards_before_contact_per_carry"] = df["yards_before_contact"].astype(float) / rushes
    df["rush_yards_per_carry"] = df["rush_yards"].astype(float) / rushes
    df["rush_epa_per_carry"] = df["rush_epa_total"].astype(float) / rushes
    df["rush_success_rate"] = df["rushes_success"].astype(float) / rushes
    df["rush_stuff_rate"] = df["rushes_stuffed"].astype(float) / rushes
    df["rush_explosive_rate"] = df["rushes_explosive"].astype(float) / rushes

    # Penalties (per total play)
    df["false_start_rate"] = df["false_starts"].astype(float) / plays
    df["holding_rate"] = df["holdings"].astype(float) / plays
    df["ol_penalty_rate"] = (
        df["false_starts"].astype(float) + df["holdings"].astype(float)
    ) / plays

    candidates = [
        # Pass blocking
        "sacks_allowed_per_dropback",
        "qb_hits_allowed_per_dropback",
        "pressure_proxy_per_dropback",
        "sack_per_contact",
        # Run blocking
        "yards_before_contact_per_carry",
        "rush_yards_per_carry",
        "rush_epa_per_carry",
        "rush_success_rate",
        "rush_stuff_rate",
        "rush_explosive_rate",
        # Penalties
        "false_start_rate",
        "holding_rate",
        "ol_penalty_rate",
    ]

    out: dict[str, pd.DataFrame] = {}
    for col in candidates:
        panel = df[["team_id", "season", col]].rename(columns={col: "value"}).dropna()
        if not panel.empty:
            out[col] = panel
    return out


def _yoy_pairs(panel: pd.DataFrame, season_pairs: list[tuple[int, int]]) -> float:
    rs: list[float] = []
    for s1, s2 in season_pairs:
        a = panel[panel["season"] == s1].set_index("team_id")["value"]
        b = panel[panel["season"] == s2].set_index("team_id")["value"]
        joined = pd.DataFrame({"a": a, "b": b}).dropna()
        if len(joined) < 5 or joined["a"].std() == 0 or joined["b"].std() == 0:
            continue
        rs.append(float(joined["a"].corr(joined["b"])))
    return float(np.mean(rs)) if rs else float("nan")


def _xsect_std(panel: pd.DataFrame) -> float:
    """Mean within-season std across team-seasons (after z-normalizing per season)."""
    if panel.empty:
        return float("nan")
    stds: list[float] = []
    for _, sub in panel.groupby("season"):
        if len(sub) < 5 or sub["value"].std() == 0:
            continue
        stds.append(float(sub["value"].std()))
    return float(np.mean(stds)) if stds else float("nan")


def _max_r_with_others(
    name: str,
    panel: pd.DataFrame,
    others: dict[str, pd.DataFrame],
) -> tuple[float, str]:
    """Largest abs Pearson r between this candidate and any OTHER candidate."""
    cand = panel.set_index(["team_id", "season"])["value"]
    best_r = 0.0
    best_partner = "—"
    for other_name, other_panel in others.items():
        if other_name == name:
            continue
        other = other_panel.set_index(["team_id", "season"])["value"]
        joined = pd.DataFrame({"a": cand, "b": other}).dropna()
        if len(joined) < 10 or joined["a"].std() == 0 or joined["b"].std() == 0:
            continue
        r = float(joined["a"].corr(joined["b"]))
        if abs(r) > abs(best_r):
            best_r = r
            best_partner = other_name
    return best_r, best_partner


def _verdict(yoy: float, xsect: float, max_r: float) -> str:
    if pd.isna(yoy) or pd.isna(xsect):
        return "INSUFFICIENT DATA"
    if yoy < 0.20:
        return "NOISE - reject or weight <=0.05"
    if abs(max_r) >= 0.85:
        return "STRONG REDUNDANCY - drop in favor of partner"
    if abs(max_r) >= 0.60:
        return "MEANINGFUL OVERLAP - consider replacement"
    if yoy >= 0.40:
        return "STRONG candidate"
    return "Independent signal"


def run_ol_audit(engine: Engine | None = None) -> list[OLCandidateScore]:
    eng = engine or get_engine()
    cands = ol_candidates(eng)
    results: list[OLCandidateScore] = []
    for name, panel in cands.items():
        yoy = _yoy_pairs(panel, _OL_SEASONS)
        xs = _xsect_std(panel)
        mr, partner = _max_r_with_others(name, panel, cands)
        results.append(OLCandidateScore(
            name=name,
            n_team_seasons=len(panel),
            yoy_mean_r=yoy,
            xsect_std=xs,
            max_r_other=mr,
            max_r_partner=partner,
            verdict=_verdict(yoy, xs, mr),
        ))
    return results


def format_ol_results(results: list[OLCandidateScore]) -> str:
    lines = []
    header = f"{'CANDIDATE':<35} {'n':>4} {'YoY r':>7} {'xsect':>8} {'max_r':>7} {'partner':<32} verdict"
    lines.append(header)
    lines.append("-" * len(header))
    for r in results:
        yoy_str = f"{r.yoy_mean_r:+.3f}" if not pd.isna(r.yoy_mean_r) else "  n/a"
        xs_str = f"{r.xsect_std:.4f}" if not pd.isna(r.xsect_std) else "n/a"
        mr_str = f"{r.max_r_other:+.3f}"
        lines.append(
            f"{r.name:<35} {r.n_team_seasons:>4d} {yoy_str:>7} "
            f"{xs_str:>8} {mr_str:>7} {r.max_r_partner[-32:]:<32} {r.verdict}"
        )
    return "\n".join(lines)


__all__ = ["OLCandidateScore", "ol_candidates", "run_ol_audit", "format_ol_results"]
