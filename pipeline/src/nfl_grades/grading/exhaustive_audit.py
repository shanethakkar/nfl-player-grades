"""Exhaustive candidate audit framework.

For each candidate stat (current OR proposed), score it against four criteria:

  1. **Reliability (YoY r)** — does the metric persist as skill across seasons?
  2. **Cross-sectional discrimination (xsect_std)** — does it meaningfully
     separate players in a single season (in z-units)?
  3. **Independence (max_r_with_existing)** — does it add new information
     vs currently-shipped components for this position?
  4. **Predictive validity (validity_r)** — does it correlate with next-year
     Pro Bowl selection?

Verdicts that emerge from these four numbers:

- All four good (YoY > 0.20, xsect > 0.5, max_r < 0.6, validity > 0.15) → ADD
- YoY > 0.20 but high redundancy → REPLACE existing if signal stronger
- YoY < 0.20 + low xsect + low validity → NOISE, reject
- YoY < 0.20 but high xsect AND high validity → CONTEXT-DEPENDENT skill,
  keep at light weight (≤0.05) with documentation

Per-position candidate fetchers live alongside this framework as
``<pos>_candidates()`` functions. The QB version is implemented here as a
worked example; others get filled in as we do each position's audit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nfl_grades.db import get_engine
from nfl_grades.grading.validity import build_panel as build_validity_panel


@dataclass(frozen=True)
class CandidateScore:
    name: str
    n_player_seasons: int
    yoy_mean_r: float
    yoy_pairs: list[tuple[int, int, int, float]]  # (y1, y2, n, r)
    xsect_std: float  # std across qualified players in z-units (≈ 1.0 expected)
    max_r_with_existing: float
    max_r_partner: str
    validity_r: float
    verdict_hint: str  # auto-generated suggestion ("ADD", "REJECT", "WEAK", etc.)


def _yoy_pairs(panel: pd.DataFrame, season_pairs: list[tuple[int, int]]) -> list[tuple[int, int, int, float]]:
    """Compute YoY Pearson r for each (y1, y2) pair. Returns (y1, y2, n, r)."""
    out = []
    for y1, y2 in season_pairs:
        a = panel[panel["season"] == y1][["player_id", "value"]].rename(columns={"value": "v1"})
        b = panel[panel["season"] == y2][["player_id", "value"]].rename(columns={"value": "v2"})
        m = a.merge(b, on="player_id", how="inner")
        if len(m) < 5 or m["v1"].std() == 0 or m["v2"].std() == 0:
            r = float("nan")
        else:
            r = float(m["v1"].corr(m["v2"]))
        out.append((y1, y2, len(m), r))
    return out


def _xsect_std(panel: pd.DataFrame, qualified_only: bool = True) -> float:
    """Cross-sectional std of the candidate, averaged across seasons.

    Within each season, z-standardize the candidate value; the std of those
    z-values is by definition ~1.0 if the metric has any spread. The number
    is meaningful only relative to other candidates — a candidate with a
    degenerate distribution will return std ~0 here even after z-scoring,
    because z-scoring of a constant produces NaN which we drop.
    """
    if panel.empty:
        return float("nan")
    season_stds: list[float] = []
    for season, sub in panel.groupby("season"):
        v = sub["value"].dropna()
        if len(v) < 5 or v.std() == 0:
            continue
        season_stds.append(float(v.std()))
    if not season_stds:
        return float("nan")
    return float(np.mean(season_stds))


def _max_r_with_existing(
    panel: pd.DataFrame,
    position: str,
    engine: Engine,
) -> tuple[float, str]:
    """Compute the largest absolute Pearson r between the candidate and any
    currently-shipped component for this position.

    Returns (max_abs_r, partner_component_name). If no existing components,
    returns (0.0, "—").
    """
    if panel.empty:
        return 0.0, "—"
    sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.z_score
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = :pos
        WHERE sg.qualified = true
          AND sc.component_name LIKE :prefix
          AND sc.z_score IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(
            sql,
            conn,
            params={"pos": position, "prefix": f"{position.lower()}_%"},
        )
    if existing.empty:
        return 0.0, "—"
    wide = existing.pivot_table(
        index=["player_id", "season"],
        columns="component_name",
        values="z_score",
        aggfunc="first",
    )
    # Join candidate values
    cand = panel.set_index(["player_id", "season"])["value"]
    joined = wide.copy()
    joined["__candidate__"] = cand
    joined = joined.dropna(subset=["__candidate__"])
    if len(joined) < 10:
        return 0.0, "—"

    best_r = 0.0
    best_partner = "—"
    for col in wide.columns:
        sub = joined[[col, "__candidate__"]].dropna()
        if len(sub) < 10 or sub[col].std() == 0 or sub["__candidate__"].std() == 0:
            continue
        r = float(sub[col].corr(sub["__candidate__"]))
        if abs(r) > abs(best_r):
            best_r = r
            best_partner = col
    return best_r, best_partner


def _validity_r(
    panel: pd.DataFrame,
    position: str,
    engine: Engine,
) -> float:
    """Correlate candidate value at season t with Pro Bowl selection at t+1.

    Uses ``validity.build_panel`` for the player_id × season × pro_bowl_next
    flag, then merges in the candidate.
    """
    if panel.empty:
        return float("nan")
    validity_panel = build_validity_panel(engine)
    vp = validity_panel[validity_panel["position"] == position][
        ["player_id", "season", "pro_bowl_next_year"]
    ]
    merged = panel.merge(vp, on=["player_id", "season"], how="inner")
    if len(merged) < 10 or merged["value"].std() == 0:
        return float("nan")
    return float(merged["value"].corr(merged["pro_bowl_next_year"]))


def _verdict_hint(yoy_mean: float, xsect: float, max_r: float, validity: float) -> str:
    if pd.isna(yoy_mean) or pd.isna(xsect):
        return "INSUFFICIENT DATA"
    if yoy_mean < 0.20 and (pd.isna(validity) or validity < 0.10):
        return "NOISE — reject or weight ≤0.05"
    if abs(max_r) >= 0.85:
        return "STRONG REDUNDANCY with existing component"
    if abs(max_r) >= 0.60:
        return "MEANINGFUL OVERLAP — consider replacement"
    if yoy_mean < 0.20 and xsect >= 0.5 and not pd.isna(validity) and validity >= 0.15:
        return "CONTEXT-DEPENDENT — light weight ok"
    if yoy_mean >= 0.20 and abs(max_r) < 0.60:
        if not pd.isna(validity) and validity >= 0.15:
            return "STRONG ADD candidate"
        return "Independent signal; weak validity"
    return "Review"


def score_candidate(
    name: str,
    panel: pd.DataFrame,
    position: str,
    *,
    season_pairs: list[tuple[int, int]],
    engine: Engine | None = None,
) -> CandidateScore:
    """Score one candidate panel against the four criteria.

    ``panel`` must have columns: player_id, season, value (the candidate's
    raw rate or efficiency for the qualified cohort). Pass only qualified
    player-seasons.
    """
    eng = engine or get_engine()
    yoy = _yoy_pairs(panel, season_pairs)
    rs = [r for *_, r in yoy if not pd.isna(r)]
    yoy_mean = float(np.mean(rs)) if rs else float("nan")
    xsect = _xsect_std(panel)
    max_r, partner = _max_r_with_existing(panel, position, eng)
    validity = _validity_r(panel, position, eng)
    n = int(panel["value"].notna().sum())
    return CandidateScore(
        name=name,
        n_player_seasons=n,
        yoy_mean_r=yoy_mean,
        yoy_pairs=yoy,
        xsect_std=xsect,
        max_r_with_existing=max_r,
        max_r_partner=partner,
        validity_r=validity,
        verdict_hint=_verdict_hint(yoy_mean, xsect, max_r, validity),
    )


def format_results_table(scores: list[CandidateScore]) -> str:
    """Pretty-print the audit output as a table."""
    rows = []
    header = f"{'CANDIDATE':<36} {'n':>4} {'YoY r':>7} {'xsect':>6} {'max_r':>7} {'partner':<28} {'PB r':>6}   verdict"
    rows.append(header)
    rows.append("-" * len(header))
    for s in scores:
        yoy_str = f"{s.yoy_mean_r:+.3f}" if not pd.isna(s.yoy_mean_r) else "  n/a"
        x_str = f"{s.xsect_std:.2f}" if not pd.isna(s.xsect_std) else "n/a"
        mr_str = f"{s.max_r_with_existing:+.3f}"
        v_str = f"{s.validity_r:+.3f}" if not pd.isna(s.validity_r) else "  n/a"
        partner = s.max_r_partner[-28:] if s.max_r_partner else "—"
        rows.append(
            f"{s.name:<36} {s.n_player_seasons:>4d} {yoy_str:>7} "
            f"{x_str:>6} {mr_str:>7} {partner:<28} {v_str:>6}   "
            f"{s.verdict_hint}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# QB candidate fetcher — worked example.
# When you do the QB exhaustive audit (queue item #4), expand this function
# to cover every plausible QB candidate from the data inventory.
# ---------------------------------------------------------------------------

def qb_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame]]:
    """Worked example: a small set of QB candidate panels.

    Returns list of (candidate_name, panel) where panel has columns
    player_id, season, value. Filters to QB-qualified player-seasons.

    This is a STARTER set for the foundation phase. Expanding to the full
    QB candidate inventory (NGS aggressiveness, time_to_throw, sack_rate,
    pressure_faced_rate, bad_throw_rate, red_zone_efficiency, etc.) happens
    during the QB exhaustive audit itself.
    """
    # 1. Get the set of qualified QB seasons we're allowed to score.
    qb_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id
        FROM season_grades sg
        JOIN players p USING (player_id)
        WHERE sg.position = 'QB' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        qb_ids = pd.read_sql(qb_sql, conn)

    candidates: list[tuple[str, pd.DataFrame]] = []

    # --- Candidate A: NGS aggressiveness ---
    # `aggressiveness` = % of attempts where the closest defender within 1
    # yard at catch point. Higher = throws into tighter windows.
    import nflreadpy as nfl

    ngs_frames = []
    for season in sorted(qb_ids["season"].unique()):
        if season < 2017:  # NGS data starts 2017 for stable QB coverage
            continue
        ngs = nfl.load_nextgen_stats(seasons=[int(season)], stat_type="passing")
        # nflreadpy returns polars by default; coerce to pandas
        if hasattr(ngs, "to_pandas"):
            ngs = ngs.to_pandas()
        # week=0 row is season aggregate; we want that one
        ngs = ngs[ngs["week"] == 0][["player_gsis_id", "aggressiveness", "avg_time_to_throw"]]
        ngs["season"] = season
        ngs_frames.append(ngs)
    if ngs_frames:
        ngs_all = pd.concat(ngs_frames, ignore_index=True)
        ngs_all = ngs_all.rename(columns={"player_gsis_id": "gsis_id"})
        ngs_all = ngs_all.merge(qb_ids, on=["gsis_id", "season"], how="inner")

        for col, display in [
            ("aggressiveness", "qb_ngs_aggressiveness"),
            ("avg_time_to_throw", "qb_ngs_time_to_throw"),
        ]:
            panel = ngs_all[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel))

    # --- Candidate B: sack rate avoided (lower = better; high → bad QB) ---
    # Pull from nflvs_player_stats. sacks_suffered / dropbacks
    sack_frames = []
    for season in sorted(qb_ids["season"].unique()):
        ps = nfl.load_player_stats(seasons=[int(season)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "QB"][
            ["player_id", "attempts", "sacks_suffered"]
        ].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        # season totals (player_stats is per-player-season for this loader)
        agg = ps.groupby("gsis_id", as_index=False).agg(
            attempts=("attempts", "sum"),
            sacks=("sacks_suffered", "sum"),
        )
        agg["season"] = season
        sack_frames.append(agg)
    if sack_frames:
        sack_all = pd.concat(sack_frames, ignore_index=True)
        sack_all["sack_rate"] = sack_all["sacks"] / (sack_all["attempts"] + sack_all["sacks"]).replace(0, np.nan)
        sack_all = sack_all.merge(qb_ids, on=["gsis_id", "season"], how="inner")
        panel = sack_all[["player_id", "season", "sack_rate"]].rename(columns={"sack_rate": "value"})
        panel = panel.dropna(subset=["value"])
        candidates.append(("qb_sack_rate_suffered", panel))

    return candidates


_QB_OFFENSE_SEASONS = [
    (2017, 2018), (2018, 2019), (2019, 2020), (2020, 2021),
    (2021, 2022), (2022, 2023), (2023, 2024), (2024, 2025),
]


def run_qb_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Worked-example end-to-end audit for QB (with the small candidate set
    defined in ``qb_candidates``). Expand the candidate set when running
    the real QB exhaustive audit.
    """
    eng = engine or get_engine()
    cands = qb_candidates(eng)
    return [
        score_candidate(name, panel, "QB",
                        season_pairs=_QB_OFFENSE_SEASONS, engine=eng)
        for name, panel in cands
    ]


__all__ = [
    "CandidateScore",
    "format_results_table",
    "qb_candidates",
    "run_qb_audit",
    "score_candidate",
]
