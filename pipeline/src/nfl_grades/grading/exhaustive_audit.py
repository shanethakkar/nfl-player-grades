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
    *,
    exclude_self: str | None = None,
) -> tuple[float, str]:
    """Compute the largest absolute Pearson r between the candidate and any
    currently-shipped component for this position.

    Returns (max_abs_r, partner_component_name). If no existing components,
    returns (0.0, "—"). Pass ``exclude_self`` when scoring a component that
    is already in the formula (avoids self-correlation = 1.0).
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
    if exclude_self:
        existing = existing[existing["component_name"] != exclude_self]
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
        return "NOISE - reject or weight <=0.05"
    if abs(max_r) >= 0.85:
        return "STRONG REDUNDANCY with existing component"
    if abs(max_r) >= 0.60:
        return "MEANINGFUL OVERLAP - consider replacement"
    if yoy_mean < 0.20 and xsect >= 0.5 and not pd.isna(validity) and validity >= 0.15:
        return "CONTEXT-DEPENDENT - light weight ok"
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
    is_existing_component: bool = False,
) -> CandidateScore:
    """Score one candidate panel against the four criteria.

    ``panel`` must have columns: player_id, season, value (the candidate's
    raw rate or efficiency for the qualified cohort). Pass only qualified
    player-seasons.

    ``is_existing_component`` should be True when ``name`` is already in
    ``stat_components`` for this position — the existing-component
    correlation check will then exclude the candidate from the comparison
    set (avoids self-correlation = 1.0).
    """
    eng = engine or get_engine()
    yoy = _yoy_pairs(panel, season_pairs)
    rs = [r for *_, r in yoy if not pd.isna(r)]
    yoy_mean = float(np.mean(rs)) if rs else float("nan")
    xsect = _xsect_std(panel)
    exclude = name if is_existing_component else None
    max_r, partner = _max_r_with_existing(panel, position, eng, exclude_self=exclude)
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

def qb_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full QB candidate set for the exhaustive audit.

    Returns list of (candidate_name, panel, is_existing_component) tuples.
    Panel columns: player_id, season, value. Filters to QB-qualified
    player-seasons only.

    Candidates pulled from:
      - stat_components (current QB formula components, re-scored)
      - nflvs_player_stats (per-season totals: TD rate, INT rate, first-down rate,
        sack rate, sack fumble rate, PACR, rush EPA per rush attempt)
      - ngs_passing (aggressiveness, time-to-throw, air-yards-to-sticks,
        air-yards-differential, intended air yards, expected completion %)
      - pfr_advstats pass (bad throw %, pressure rate faced)

    Existing-component candidates are flagged with is_existing_component=True
    so the correlation check excludes self-correlation.
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # ---------- 1. Qualified QB ID set ----------
    qb_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name
        FROM season_grades sg
        JOIN players p USING (player_id)
        WHERE sg.position = 'QB' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        qb_ids = pd.read_sql(qb_sql, conn)
    seasons = sorted(qb_ids["season"].unique())

    # ---------- 2. Currently-shipped components (re-score) ----------
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'QB'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 'qb_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # ---------- 3. nflvs_player_stats: per-season totals → rates ----------
    nflvs_frames = []
    for s in seasons:
        ps = nfl.load_player_stats(seasons=[int(s)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "QB"][[
            "player_id", "attempts", "completions", "passing_tds",
            "passing_interceptions", "passing_first_downs",
            "sacks_suffered", "sack_fumbles",
            "passing_yards", "passing_air_yards",
            "rushing_epa", "carries",
        ]].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        agg = ps.groupby("gsis_id", as_index=False).sum(numeric_only=True)
        agg["season"] = s
        nflvs_frames.append(agg)
    if nflvs_frames:
        nflvs = pd.concat(nflvs_frames, ignore_index=True)
        nflvs = nflvs.merge(qb_ids, on=["gsis_id", "season"], how="inner")
        # dropbacks ≈ attempts + sacks
        nflvs["dropbacks"] = nflvs["attempts"] + nflvs["sacks_suffered"]

        nflvs["td_rate"] = nflvs["passing_tds"] / nflvs["attempts"].replace(0, np.nan)
        nflvs["int_rate"] = nflvs["passing_interceptions"] / nflvs["attempts"].replace(0, np.nan)
        nflvs["first_down_rate"] = nflvs["passing_first_downs"] / nflvs["dropbacks"].replace(0, np.nan)
        nflvs["sack_rate_suffered"] = nflvs["sacks_suffered"] / nflvs["dropbacks"].replace(0, np.nan)
        nflvs["sack_fumble_rate"] = (
            nflvs["sack_fumbles"] / nflvs["sacks_suffered"].replace(0, np.nan)
        )
        # PACR = passing yards / passing air yards (air-yards conversion)
        nflvs["pacr"] = nflvs["passing_yards"] / nflvs["passing_air_yards"].replace(0, np.nan)
        nflvs["rush_epa_per_rush"] = (
            nflvs["rushing_epa"] / nflvs["carries"].replace(0, np.nan)
        )

        for col, display in [
            ("td_rate", "qb_td_rate"),
            ("int_rate", "qb_int_rate"),
            ("first_down_rate", "qb_first_down_rate"),
            ("sack_rate_suffered", "qb_sack_rate_suffered"),
            ("sack_fumble_rate", "qb_sack_fumble_rate"),
            ("pacr", "qb_pacr"),
            ("rush_epa_per_rush", "qb_rush_epa_per_rush"),
        ]:
            panel = nflvs[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            # Outlier guard: at least 50 plays of the denominator
            if col == "rush_epa_per_rush":
                panel = panel[nflvs["carries"] >= 10].reset_index(drop=True)
            elif col == "sack_fumble_rate":
                panel = panel[nflvs["sacks_suffered"] >= 5].reset_index(drop=True)
            candidates.append((display, panel, False))

    # ---------- 4. ngs_passing: NGS season-summary metrics (week=0) ----------
    ngs_frames = []
    for s in seasons:
        if s < 2017:
            continue
        ngs = nfl.load_nextgen_stats(seasons=[int(s)], stat_type="passing")
        if hasattr(ngs, "to_pandas"):
            ngs = ngs.to_pandas()
        ngs = ngs[ngs["week"] == 0][[
            "player_gsis_id",
            "aggressiveness", "avg_time_to_throw",
            "avg_air_yards_to_sticks", "avg_air_yards_differential",
            "avg_intended_air_yards", "expected_completion_percentage",
            "completion_percentage_above_expectation",
        ]].copy()
        ngs["season"] = s
        ngs_frames.append(ngs)
    if ngs_frames:
        ngs_all = pd.concat(ngs_frames, ignore_index=True)
        ngs_all = ngs_all.rename(columns={"player_gsis_id": "gsis_id"})
        ngs_all = ngs_all.merge(qb_ids, on=["gsis_id", "season"], how="inner")
        for col, display in [
            ("aggressiveness", "qb_ngs_aggressiveness"),
            ("avg_time_to_throw", "qb_ngs_time_to_throw"),
            ("avg_air_yards_to_sticks", "qb_ngs_air_yards_to_sticks"),
            ("avg_air_yards_differential", "qb_ngs_air_yards_differential"),
            ("avg_intended_air_yards", "qb_ngs_intended_air_yards"),
            ("expected_completion_percentage", "qb_ngs_expected_completion_pct"),
            ("completion_percentage_above_expectation", "qb_ngs_cpoe"),
        ]:
            panel = ngs_all[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # ---------- 5. pfr_advstats pass (2018+): bad throw rate, pressure rate ----------
    pfr_frames = []
    for s in seasons:
        if s < 2018:
            continue
        pfr = nfl.load_pfr_advstats(seasons=[int(s)], stat_type="pass")
        if hasattr(pfr, "to_pandas"):
            pfr = pfr.to_pandas()
        pfr = pfr[[
            "pfr_player_id", "pfr_player_name",
            "passing_bad_throws", "passing_bad_throw_pct",
            "times_pressured", "times_pressured_pct",
            "times_sacked",
        ]].copy()
        # PFR per-game → sum to season
        agg = pfr.groupby("pfr_player_name", as_index=False).agg(
            bad_throws=("passing_bad_throws", "sum"),
            times_pressured=("times_pressured", "sum"),
            times_sacked=("times_sacked", "sum"),
            n_games=("pfr_player_id", "count"),
        )
        agg["season"] = s
        pfr_frames.append(agg)
    if pfr_frames:
        pfr_all = pd.concat(pfr_frames, ignore_index=True)
        # Match PFR name to our player name (PFR uses different gsis-equivalent)
        qb_names = qb_ids[["player_id", "season", "full_name"]].copy()
        qb_names["name_norm"] = qb_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_all["name_norm"] = pfr_all["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_all.merge(qb_names, on=["name_norm", "season"], how="inner")
        # Rates need a denominator: roughly attempts. Pull from nflvs.
        if nflvs_frames:
            denom = nflvs[["player_id", "season", "attempts", "dropbacks"]]
            merged = merged.merge(denom, on=["player_id", "season"], how="left")
            merged["bad_throw_pct"] = merged["bad_throws"] / merged["attempts"].replace(0, np.nan)
            merged["pressure_rate_faced"] = merged["times_pressured"] / merged["dropbacks"].replace(0, np.nan)
            for col, display in [
                ("bad_throw_pct", "qb_pfr_bad_throw_pct"),
                ("pressure_rate_faced", "qb_pfr_pressure_rate_faced"),
            ]:
                panel = merged[["player_id", "season", col]].rename(columns={col: "value"})
                panel = panel.dropna(subset=["value"])
                candidates.append((display, panel, False))

    return candidates


_QB_OFFENSE_SEASONS = [
    (2017, 2018), (2018, 2019), (2019, 2020), (2020, 2021),
    (2021, 2022), (2022, 2023), (2023, 2024), (2024, 2025),
]


def run_qb_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full QB exhaustive audit using ``qb_candidates`` as input."""
    eng = engine or get_engine()
    cands = qb_candidates(eng)
    return [
        score_candidate(
            name, panel, "QB",
            season_pairs=_QB_OFFENSE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


_WR_OFFENSE_SEASONS = _QB_OFFENSE_SEASONS  # same range


def wr_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full WR candidate set for the exhaustive audit.

    Candidates pulled from:
      - stat_components (current WR formula components, re-scored)
      - nflvs_player_stats (per-season totals → rates: TD rate, first-down
        rate, yards/target, catch rate, target share, air-yards share)
      - ngs_receiving (avg_cushion, avg_intended_air_yards, NGS YAC,
        air-yards share — to confirm/refute earlier rejections under
        validity)
      - ftn_receiving_charting (contested_catch_rate, created_reception_rate,
        beyond the current drop_rate)
      - pfr_advstats rec (broken tackles per reception, PFR drop rate,
        receiver passer rating)

    Skips already-strongly-rejected redundant candidates (wopr, racr — both
    have detailed prior research showing structural redundancy). Those
    rejections are documented in research/wr-v1-1.md and don't need
    re-validation under the four-criterion framework.
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # ---------- 1. Qualified WR ID set ----------
    wr_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name
        FROM season_grades sg
        JOIN players p USING (player_id)
        WHERE sg.position = 'WR' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        wr_ids = pd.read_sql(wr_sql, conn)
    seasons = sorted(wr_ids["season"].unique())

    # ---------- 2. Currently-shipped components (re-score) ----------
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'WR'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 'wr_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # ---------- 3. nflvs_player_stats: per-season WR totals → rates ----------
    nflvs_frames = []
    for s in seasons:
        ps = nfl.load_player_stats(seasons=[int(s)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "WR"][[
            "player_id",
            "targets", "receptions",
            "receiving_yards", "receiving_air_yards",
            "receiving_tds", "receiving_first_downs",
            "target_share", "air_yards_share",
        ]].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        # Note: target_share / air_yards_share are pre-computed per-game
        # in nflvs. Summing them per season is wrong; instead recompute
        # from totals. But the per-game numbers are also reasonable averages.
        # For this audit we take the max per (gsis_id, season) row (which
        # for season-aggregate rows is the season figure) — nflreadpy's
        # load_player_stats returns season totals by default.
        agg = ps.groupby("gsis_id", as_index=False).agg(
            targets=("targets", "sum"),
            receptions=("receptions", "sum"),
            receiving_yards=("receiving_yards", "sum"),
            receiving_air_yards=("receiving_air_yards", "sum"),
            receiving_tds=("receiving_tds", "sum"),
            receiving_first_downs=("receiving_first_downs", "sum"),
            target_share=("target_share", "mean"),
            air_yards_share=("air_yards_share", "mean"),
        )
        agg["season"] = s
        nflvs_frames.append(agg)
    if nflvs_frames:
        nflvs = pd.concat(nflvs_frames, ignore_index=True)
        nflvs = nflvs.merge(wr_ids, on=["gsis_id", "season"], how="inner")

        nflvs["td_rate"] = nflvs["receiving_tds"] / nflvs["targets"].replace(0, np.nan)
        nflvs["first_down_rate"] = nflvs["receiving_first_downs"] / nflvs["targets"].replace(0, np.nan)
        nflvs["yards_per_target"] = nflvs["receiving_yards"] / nflvs["targets"].replace(0, np.nan)
        nflvs["catch_rate"] = nflvs["receptions"] / nflvs["targets"].replace(0, np.nan)

        for col, display in [
            ("td_rate", "wr_td_rate"),
            ("first_down_rate", "wr_first_down_rate"),
            ("yards_per_target", "wr_yards_per_target"),
            ("catch_rate", "wr_catch_rate"),
            ("target_share", "wr_target_share"),
            ("air_yards_share", "wr_air_yards_share"),
        ]:
            panel = nflvs[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # ---------- 4. ngs_receiving: NGS week=0 season summary ----------
    ngs_frames = []
    for s in seasons:
        if s < 2017:
            continue
        ngs = nfl.load_nextgen_stats(seasons=[int(s)], stat_type="receiving")
        if hasattr(ngs, "to_pandas"):
            ngs = ngs.to_pandas()
        ngs = ngs[ngs["week"] == 0][[
            "player_gsis_id",
            "avg_cushion", "avg_intended_air_yards",
            "avg_yac_above_expectation",
            "percent_share_of_intended_air_yards",
            "catch_percentage",
        ]].copy()
        ngs["season"] = s
        ngs_frames.append(ngs)
    if ngs_frames:
        ngs_all = pd.concat(ngs_frames, ignore_index=True)
        ngs_all = ngs_all.rename(columns={"player_gsis_id": "gsis_id"})
        ngs_all = ngs_all.merge(wr_ids, on=["gsis_id", "season"], how="inner")
        for col, display in [
            ("avg_cushion", "wr_ngs_cushion"),
            ("avg_intended_air_yards", "wr_ngs_intended_air_yards"),
            ("avg_yac_above_expectation", "wr_ngs_yac_above_expectation"),
            ("percent_share_of_intended_air_yards", "wr_ngs_air_yards_share"),
            ("catch_percentage", "wr_ngs_catch_pct"),
        ]:
            panel = ngs_all[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # ---------- 5. FTN charting (2022+): contested + created rates ----------
    ftn_sql = text(
        """
        SELECT player_id, season, catchable_balls, contested_balls,
               created_receptions
        FROM ftn_receiving_charting
        WHERE catchable_balls > 0
        """
    )
    with engine.connect() as conn:
        ftn = pd.read_sql(ftn_sql, conn)
    ftn = ftn.merge(
        wr_ids[["player_id", "season"]], on=["player_id", "season"], how="inner"
    )
    if not ftn.empty:
        ftn["contested_rate"] = ftn["contested_balls"] / ftn["catchable_balls"].replace(0, np.nan)
        ftn["created_rate"] = ftn["created_receptions"] / ftn["catchable_balls"].replace(0, np.nan)
        for col, display in [
            ("contested_rate", "wr_ftn_contested_rate"),
            ("created_rate", "wr_ftn_created_reception_rate"),
        ]:
            panel = ftn[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            # Outlier guard: at least 25 catchable balls
            panel = panel[ftn["catchable_balls"] >= 25].reset_index(drop=True)
            candidates.append((display, panel, False))

    # ---------- 6. pfr_advstats rec (2018+): broken tackles, PFR drops ----------
    pfr_frames = []
    for s in seasons:
        if s < 2018:
            continue
        pfr = nfl.load_pfr_advstats(seasons=[int(s)], stat_type="rec")
        if hasattr(pfr, "to_pandas"):
            pfr = pfr.to_pandas()
        pfr = pfr[[
            "pfr_player_name",
            "receiving_broken_tackles", "receiving_drop", "receiving_rat",
        ]].copy()
        agg = pfr.groupby("pfr_player_name", as_index=False).agg(
            broken_tackles=("receiving_broken_tackles", "sum"),
            drops_pfr=("receiving_drop", "sum"),
            receiving_rat=("receiving_rat", "mean"),
        )
        agg["season"] = s
        pfr_frames.append(agg)
    if pfr_frames and nflvs_frames:
        pfr_all = pd.concat(pfr_frames, ignore_index=True)
        wr_names = wr_ids[["player_id", "season", "full_name"]].copy()
        wr_names["name_norm"] = wr_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_all["name_norm"] = pfr_all["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_all.merge(wr_names, on=["name_norm", "season"], how="inner")
        denom = nflvs[["player_id", "season", "receptions", "targets"]]
        merged = merged.merge(denom, on=["player_id", "season"], how="left")
        merged["broken_tackle_per_rec"] = (
            merged["broken_tackles"] / merged["receptions"].replace(0, np.nan)
        )
        merged["pfr_drop_pct"] = (
            merged["drops_pfr"] / merged["targets"].replace(0, np.nan)
        )
        for col, display in [
            ("broken_tackle_per_rec", "wr_pfr_broken_tackle_per_rec"),
            ("pfr_drop_pct", "wr_pfr_drop_pct"),
            ("receiving_rat", "wr_pfr_receiving_rat"),
        ]:
            panel = merged[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    return candidates


def run_wr_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full WR exhaustive audit."""
    eng = engine or get_engine()
    cands = wr_candidates(eng)
    return [
        score_candidate(
            name, panel, "WR",
            season_pairs=_WR_OFFENSE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


# ---------------------------------------------------------------------------
# RB candidates
# ---------------------------------------------------------------------------

_RB_OFFENSE_SEASONS = _QB_OFFENSE_SEASONS  # same range


def rb_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full RB candidate set for the exhaustive audit.

    Candidates pulled from:
      - stat_components (current RB formula components, re-scored)
      - nflvs_player_stats (per-season totals → rates: rush TD, first-down,
        yards/carry, catch rate)
      - ngs_rushing (efficiency, rush_pct_over_expected, time_to_los,
        eight-defenders — re-validate previously-rejected candidates with
        validity scoring)
      - pfr_advstats rush (broken_tackle rate, yards_after_contact,
        yards_before_contact — RB-skill-after-contact)

    Outlier guards: candidates require sample-size floor (e.g. carries >= 80
    for rush-rate candidates) to keep the panel restricted to genuinely
    qualified RBs.
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # 1. Qualified RB ID set
    rb_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name
        FROM season_grades sg
        JOIN players p USING (player_id)
        WHERE sg.position = 'RB' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        rb_ids = pd.read_sql(rb_sql, conn)
    seasons = sorted(rb_ids["season"].unique())

    # 2. Currently-shipped components (re-score)
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'RB'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 'rb_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # 3. nflvs_player_stats RB totals → rates
    nflvs_frames = []
    for s in seasons:
        ps = nfl.load_player_stats(seasons=[int(s)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "RB"][[
            "player_id", "carries",
            "rushing_yards", "rushing_tds", "rushing_first_downs",
            "targets", "receptions",
            "receiving_yards", "receiving_tds",
        ]].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        agg = ps.groupby("gsis_id", as_index=False).sum(numeric_only=True)
        agg["season"] = s
        nflvs_frames.append(agg)
    if nflvs_frames:
        nflvs = pd.concat(nflvs_frames, ignore_index=True)
        nflvs = nflvs.merge(rb_ids, on=["gsis_id", "season"], how="inner")
        nflvs["yards_per_carry"] = nflvs["rushing_yards"] / nflvs["carries"].replace(0, np.nan)
        nflvs["rush_td_rate"] = nflvs["rushing_tds"] / nflvs["carries"].replace(0, np.nan)
        nflvs["rush_first_down_rate"] = nflvs["rushing_first_downs"] / nflvs["carries"].replace(0, np.nan)
        nflvs["catch_rate"] = nflvs["receptions"] / nflvs["targets"].replace(0, np.nan)
        nflvs["rec_td_rate"] = nflvs["receiving_tds"] / nflvs["targets"].replace(0, np.nan)
        for col, display, denom_col, min_n in [
            ("yards_per_carry", "rb_yards_per_carry", "carries", 80),
            ("rush_td_rate", "rb_rush_td_rate", "carries", 80),
            ("rush_first_down_rate", "rb_rush_first_down_rate", "carries", 80),
            ("catch_rate", "rb_catch_rate", "targets", 20),
            ("rec_td_rate", "rb_rec_td_rate", "targets", 20),
        ]:
            mask = nflvs[denom_col] >= min_n
            panel = nflvs.loc[mask, ["player_id", "season", col]].rename(
                columns={col: "value"}
            )
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # 4. NGS rushing (re-validate prior rejections)
    ngs_frames = []
    for s in seasons:
        if s < 2017:
            continue
        ngs = nfl.load_nextgen_stats(seasons=[int(s)], stat_type="rushing")
        if hasattr(ngs, "to_pandas"):
            ngs = ngs.to_pandas()
        ngs = ngs[ngs["week"] == 0][[
            "player_gsis_id",
            "efficiency", "avg_time_to_los",
            "rush_pct_over_expected",
            "percent_attempts_gte_eight_defenders",
            "rush_yards_over_expected_per_att",
        ]].copy()
        ngs["season"] = s
        ngs_frames.append(ngs)
    if ngs_frames:
        ngs_all = pd.concat(ngs_frames, ignore_index=True)
        ngs_all = ngs_all.rename(columns={"player_gsis_id": "gsis_id"})
        ngs_all = ngs_all.merge(rb_ids, on=["gsis_id", "season"], how="inner")
        for col, display in [
            ("efficiency", "rb_ngs_efficiency"),
            ("avg_time_to_los", "rb_ngs_time_to_los"),
            ("rush_pct_over_expected", "rb_ngs_rush_pct_over_expected"),
            ("percent_attempts_gte_eight_defenders", "rb_ngs_pct_eight_defenders"),
            ("rush_yards_over_expected_per_att", "rb_ngs_ryoe_per_att"),
        ]:
            panel = ngs_all[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # 5. pfr_advstats rush (2018+): broken tackles + yards after contact
    pfr_frames = []
    for s in seasons:
        if s < 2018:
            continue
        pfr = nfl.load_pfr_advstats(seasons=[int(s)], stat_type="rush")
        if hasattr(pfr, "to_pandas"):
            pfr = pfr.to_pandas()
        pfr = pfr[[
            "pfr_player_name", "carries",
            "rushing_broken_tackles",
            "rushing_yards_after_contact",
            "rushing_yards_before_contact",
        ]].copy()
        agg = pfr.groupby("pfr_player_name", as_index=False).agg(
            carries=("carries", "sum"),
            broken_tackles=("rushing_broken_tackles", "sum"),
            yac=("rushing_yards_after_contact", "sum"),
            ybc=("rushing_yards_before_contact", "sum"),
        )
        agg["season"] = s
        pfr_frames.append(agg)
    if pfr_frames:
        pfr_all = pd.concat(pfr_frames, ignore_index=True)
        rb_names = rb_ids[["player_id", "season", "full_name"]].copy()
        rb_names["name_norm"] = rb_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_all["name_norm"] = pfr_all["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_all.merge(rb_names, on=["name_norm", "season"], how="inner")
        merged["broken_tackle_per_carry"] = merged["broken_tackles"] / merged["carries"].replace(0, np.nan)
        merged["yac_per_carry"] = merged["yac"] / merged["carries"].replace(0, np.nan)
        merged["ybc_per_carry"] = merged["ybc"] / merged["carries"].replace(0, np.nan)
        for col, display in [
            ("broken_tackle_per_carry", "rb_pfr_broken_tackle_rate"),
            ("yac_per_carry", "rb_pfr_yards_after_contact"),
            ("ybc_per_carry", "rb_pfr_yards_before_contact"),
        ]:
            mask = merged["carries"] >= 80
            panel = merged.loc[mask, ["player_id", "season", col]].rename(
                columns={col: "value"}
            )
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    return candidates


def run_rb_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full RB exhaustive audit."""
    eng = engine or get_engine()
    cands = rb_candidates(eng)
    return [
        score_candidate(
            name, panel, "RB",
            season_pairs=_RB_OFFENSE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


# ---------------------------------------------------------------------------
# TE candidates
# ---------------------------------------------------------------------------

_TE_OFFENSE_SEASONS = _QB_OFFENSE_SEASONS  # same range


def te_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full TE candidate set for the exhaustive audit.

    Parallels wr_candidates but with TE position filter. Candidates pulled
    from:
      - stat_components (current TE formula components, re-scored)
      - nflvs_player_stats (per-season totals → rates)
      - ngs_receiving (separation, cushion, intended air yards, NGS YAC)
      - ftn_receiving_charting (contested rate, created reception rate)
      - pfr_advstats rec (broken tackles per reception, PFR drops)
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # 1. Qualified TE ID set
    te_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name
        FROM season_grades sg
        JOIN players p USING (player_id)
        WHERE sg.position = 'TE' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        te_ids = pd.read_sql(te_sql, conn)
    seasons = sorted(te_ids["season"].unique())

    # 2. Currently-shipped components (re-score)
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'TE'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 'te_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # 3. nflvs_player_stats TE totals → rates
    nflvs_frames = []
    for s in seasons:
        ps = nfl.load_player_stats(seasons=[int(s)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "TE"][[
            "player_id",
            "targets", "receptions",
            "receiving_yards", "receiving_air_yards",
            "receiving_tds", "receiving_first_downs",
            "target_share", "air_yards_share",
        ]].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        agg = ps.groupby("gsis_id", as_index=False).agg(
            targets=("targets", "sum"),
            receptions=("receptions", "sum"),
            receiving_yards=("receiving_yards", "sum"),
            receiving_air_yards=("receiving_air_yards", "sum"),
            receiving_tds=("receiving_tds", "sum"),
            receiving_first_downs=("receiving_first_downs", "sum"),
            target_share=("target_share", "mean"),
            air_yards_share=("air_yards_share", "mean"),
        )
        agg["season"] = s
        nflvs_frames.append(agg)
    if nflvs_frames:
        nflvs = pd.concat(nflvs_frames, ignore_index=True)
        nflvs = nflvs.merge(te_ids, on=["gsis_id", "season"], how="inner")
        nflvs["td_rate"] = nflvs["receiving_tds"] / nflvs["targets"].replace(0, np.nan)
        nflvs["first_down_rate"] = nflvs["receiving_first_downs"] / nflvs["targets"].replace(0, np.nan)
        nflvs["yards_per_target"] = nflvs["receiving_yards"] / nflvs["targets"].replace(0, np.nan)
        nflvs["catch_rate"] = nflvs["receptions"] / nflvs["targets"].replace(0, np.nan)
        for col, display in [
            ("td_rate", "te_td_rate"),
            ("first_down_rate", "te_first_down_rate"),
            ("yards_per_target", "te_yards_per_target"),
            ("catch_rate", "te_catch_rate"),
            ("target_share", "te_target_share"),
            ("air_yards_share", "te_air_yards_share"),
        ]:
            panel = nflvs[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # 4. ngs_receiving (2017+)
    ngs_frames = []
    for s in seasons:
        if s < 2017:
            continue
        ngs = nfl.load_nextgen_stats(seasons=[int(s)], stat_type="receiving")
        if hasattr(ngs, "to_pandas"):
            ngs = ngs.to_pandas()
        ngs = ngs[ngs["week"] == 0][[
            "player_gsis_id",
            "avg_cushion", "avg_intended_air_yards",
            "avg_yac_above_expectation",
            "percent_share_of_intended_air_yards",
            "catch_percentage",
        ]].copy()
        ngs["season"] = s
        ngs_frames.append(ngs)
    if ngs_frames:
        ngs_all = pd.concat(ngs_frames, ignore_index=True)
        ngs_all = ngs_all.rename(columns={"player_gsis_id": "gsis_id"})
        ngs_all = ngs_all.merge(te_ids, on=["gsis_id", "season"], how="inner")
        for col, display in [
            ("avg_cushion", "te_ngs_cushion"),
            ("avg_intended_air_yards", "te_ngs_intended_air_yards"),
            ("avg_yac_above_expectation", "te_ngs_yac_above_expectation"),
            ("percent_share_of_intended_air_yards", "te_ngs_air_yards_share"),
            ("catch_percentage", "te_ngs_catch_pct"),
        ]:
            panel = ngs_all[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # 5. FTN (2022+)
    ftn_sql = text(
        """
        SELECT player_id, season, catchable_balls, contested_balls,
               created_receptions
        FROM ftn_receiving_charting
        WHERE catchable_balls > 0
        """
    )
    with engine.connect() as conn:
        ftn = pd.read_sql(ftn_sql, conn)
    ftn = ftn.merge(
        te_ids[["player_id", "season"]], on=["player_id", "season"], how="inner"
    )
    if not ftn.empty:
        ftn["contested_rate"] = ftn["contested_balls"] / ftn["catchable_balls"].replace(0, np.nan)
        ftn["created_rate"] = ftn["created_receptions"] / ftn["catchable_balls"].replace(0, np.nan)
        for col, display in [
            ("contested_rate", "te_ftn_contested_rate"),
            ("created_rate", "te_ftn_created_reception_rate"),
        ]:
            panel = ftn[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            # Outlier guard: at least 15 catchable balls (TEs have smaller
            # denominators than WRs)
            panel = panel[ftn["catchable_balls"] >= 15].reset_index(drop=True)
            candidates.append((display, panel, False))

    # 6. PFR rec (2018+): broken tackles per reception
    pfr_frames = []
    for s in seasons:
        if s < 2018:
            continue
        pfr = nfl.load_pfr_advstats(seasons=[int(s)], stat_type="rec")
        if hasattr(pfr, "to_pandas"):
            pfr = pfr.to_pandas()
        pfr = pfr[[
            "pfr_player_name",
            "receiving_broken_tackles", "receiving_drop", "receiving_rat",
        ]].copy()
        agg = pfr.groupby("pfr_player_name", as_index=False).agg(
            broken_tackles=("receiving_broken_tackles", "sum"),
            drops_pfr=("receiving_drop", "sum"),
            receiving_rat=("receiving_rat", "mean"),
        )
        agg["season"] = s
        pfr_frames.append(agg)
    if pfr_frames and nflvs_frames:
        pfr_all = pd.concat(pfr_frames, ignore_index=True)
        te_names = te_ids[["player_id", "season", "full_name"]].copy()
        te_names["name_norm"] = te_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_all["name_norm"] = pfr_all["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_all.merge(te_names, on=["name_norm", "season"], how="inner")
        denom = nflvs[["player_id", "season", "receptions", "targets"]]
        merged = merged.merge(denom, on=["player_id", "season"], how="left")
        merged["broken_tackle_per_rec"] = (
            merged["broken_tackles"] / merged["receptions"].replace(0, np.nan)
        )
        merged["pfr_drop_pct"] = (
            merged["drops_pfr"] / merged["targets"].replace(0, np.nan)
        )
        for col, display in [
            ("broken_tackle_per_rec", "te_pfr_broken_tackle_per_rec"),
            ("pfr_drop_pct", "te_pfr_drop_pct"),
            ("receiving_rat", "te_pfr_receiving_rat"),
        ]:
            panel = merged[["player_id", "season", col]].rename(columns={col: "value"})
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    return candidates


def run_te_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full TE exhaustive audit."""
    eng = engine or get_engine()
    cands = te_candidates(eng)
    return [
        score_candidate(
            name, panel, "TE",
            season_pairs=_TE_OFFENSE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


# ---------------------------------------------------------------------------
# CB candidates
# ---------------------------------------------------------------------------

# Defensive positions only have data 2018+ from PFR.
_DEFENSIVE_SEASONS = [
    (2018, 2019), (2019, 2020), (2020, 2021), (2021, 2022),
    (2022, 2023), (2023, 2024), (2024, 2025),
]


def _pfr_def_aggregated(seasons: list[int], position_filter: frozenset[str]):
    """Helper: pull pfr_advstats_def, aggregate per (pfr_id, season),
    return DataFrame keyed by pfr_player_name + season (for our name-join).
    """
    import nflreadpy as nfl

    out = []
    for s in seasons:
        if s < 2018:
            continue
        df = nfl.load_pfr_advstats(seasons=[int(s)], stat_type="def")
        if hasattr(df, "to_pandas"):
            df = df.to_pandas()
        if "game_type" in df.columns:
            df = df[df["game_type"] == "REG"].copy()
        # Aggregate to season totals.
        agg = df.groupby("pfr_player_name", as_index=False).agg(
            targets=("def_targets", "sum"),
            completions=("def_completions_allowed", "sum"),
            yards=("def_yards_allowed", "sum"),
            tds=("def_receiving_td_allowed", "sum"),
            ints=("def_ints", "sum"),
            yac=("def_yards_after_catch", "sum"),
            adot=("def_adot", "mean"),
            missed_tackles=("def_missed_tackles", "sum"),
            comb_tackles=("def_tackles_combined", "sum"),
        )
        agg["season"] = s
        out.append(agg)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True)


def cb_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full CB candidate set for the exhaustive audit.

    CB data starts 2018 (PFR coverage data limitation).

    Candidates pulled from:
      - stat_components (current CB formula components, re-scored)
      - pfr_advstats_def (per-game; aggregated → individual rates that
        v1.1 consolidated into passer_rating_allowed):
          comp_pct, yards_per_target, int_rate, td_rate_allowed, adot
      - missed_tackle_rate (already in Safety formula; check if CB-relevant)
      - tackles_per_snap (could be a CB skill signal)
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # 1. Qualified CB ID set + snap counts (for tackle rate denominator)
    cb_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name,
               ps.snaps_defense
        FROM season_grades sg
        JOIN players p USING (player_id)
        LEFT JOIN (
            SELECT DISTINCT ON (player_id, season) player_id, season, snaps_defense
            FROM player_seasons
            ORDER BY player_id, season, snaps_defense DESC NULLS LAST
        ) ps ON ps.player_id = sg.player_id AND ps.season = sg.season
        WHERE sg.position = 'CB' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        cb_ids = pd.read_sql(cb_sql, conn)
    seasons = sorted(cb_ids["season"].unique())

    # 2. Currently-shipped components
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'CB'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 'cb_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # 3. PFR def_advstats — individual rate candidates
    pfr_agg = _pfr_def_aggregated(seasons, position_filter=frozenset({"CB"}))
    if not pfr_agg.empty:
        # Join by name + season to CB players
        cb_names = cb_ids[["player_id", "season", "full_name", "snaps_defense"]].copy()
        cb_names["name_norm"] = cb_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_agg["name_norm"] = pfr_agg["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_agg.merge(cb_names, on=["name_norm", "season"], how="inner")
        merged["comp_pct_allowed"] = merged["completions"] / merged["targets"].replace(0, np.nan)
        merged["yards_per_target"] = merged["yards"] / merged["targets"].replace(0, np.nan)
        merged["int_rate"] = merged["ints"] / merged["targets"].replace(0, np.nan)
        merged["td_rate_allowed"] = merged["tds"] / merged["targets"].replace(0, np.nan)
        merged["missed_tackle_rate"] = merged["missed_tackles"] / (
            merged["comb_tackles"] + merged["missed_tackles"]
        ).replace(0, np.nan)
        merged["tackles_per_snap"] = merged["comb_tackles"] / merged["snaps_defense"].replace(0, np.nan)
        merged["adot_allowed"] = merged["adot"]
        for col, display, denom_col, min_n in [
            ("comp_pct_allowed", "cb_comp_pct_allowed", "targets", 25),
            ("yards_per_target", "cb_yards_per_target_allowed", "targets", 25),
            ("int_rate", "cb_int_rate", "targets", 25),
            ("td_rate_allowed", "cb_td_rate_allowed", "targets", 25),
            ("missed_tackle_rate", "cb_missed_tackle_rate", "comb_tackles", 20),
            ("tackles_per_snap", "cb_tackles_per_snap", "snaps_defense", 200),
            ("adot_allowed", "cb_adot_allowed", "targets", 25),
        ]:
            mask = merged[denom_col].fillna(0) >= min_n
            panel = merged.loc[mask, ["player_id", "season", col]].rename(
                columns={col: "value"}
            )
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    return candidates


def run_cb_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full CB exhaustive audit."""
    eng = engine or get_engine()
    cands = cb_candidates(eng)
    return [
        score_candidate(
            name, panel, "CB",
            season_pairs=_DEFENSIVE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


# ---------------------------------------------------------------------------
# Safety candidates
# ---------------------------------------------------------------------------

def s_candidates(engine: Engine) -> list[tuple[str, pd.DataFrame, bool]]:
    """Full Safety candidate set for the exhaustive audit.

    Same pattern as CB. Safety formula has 6 components vs CB's 4
    (tackles, missed_tackle, backfield_disruption are S-specific).
    """
    import nflreadpy as nfl

    candidates: list[tuple[str, pd.DataFrame, bool]] = []

    # 1. Qualified S IDs + snap counts
    s_sql = text(
        """
        SELECT sg.player_id, sg.season, p.gsis_id, p.full_name,
               ps.snaps_defense
        FROM season_grades sg
        JOIN players p USING (player_id)
        LEFT JOIN (
            SELECT DISTINCT ON (player_id, season) player_id, season, snaps_defense
            FROM player_seasons
            ORDER BY player_id, season, snaps_defense DESC NULLS LAST
        ) ps ON ps.player_id = sg.player_id AND ps.season = sg.season
        WHERE sg.position = 'S' AND sg.qualified = true
        """
    )
    with engine.connect() as conn:
        s_ids = pd.read_sql(s_sql, conn)
    seasons = sorted(s_ids["season"].unique())

    # 2. Currently-shipped components
    existing_sql = text(
        """
        SELECT sc.player_id, sc.season, sc.component_name, sc.raw_value
        FROM stat_components sc
        JOIN season_grades sg
          ON sg.player_id = sc.player_id
         AND sg.season    = sc.season
         AND sg.position  = 'S'
        WHERE sg.qualified = true
          AND sc.component_name LIKE 's_%'
          AND sc.raw_value IS NOT NULL
        """
    )
    with engine.connect() as conn:
        existing = pd.read_sql(existing_sql, conn)
    for comp_name, sub in existing.groupby("component_name"):
        panel = sub[["player_id", "season", "raw_value"]].rename(
            columns={"raw_value": "value"}
        )
        candidates.append((comp_name, panel, True))

    # 3. PFR def_advstats — same pull as CB
    pfr_agg = _pfr_def_aggregated(seasons, position_filter=frozenset({"S"}))
    if not pfr_agg.empty:
        s_names = s_ids[["player_id", "season", "full_name", "snaps_defense"]].copy()
        s_names["name_norm"] = s_names["full_name"].str.lower().str.replace(".", "", regex=False)
        pfr_agg["name_norm"] = pfr_agg["pfr_player_name"].str.lower().str.replace(".", "", regex=False)
        merged = pfr_agg.merge(s_names, on=["name_norm", "season"], how="inner")
        merged["comp_pct_allowed"] = merged["completions"] / merged["targets"].replace(0, np.nan)
        merged["yards_per_target"] = merged["yards"] / merged["targets"].replace(0, np.nan)
        merged["int_rate"] = merged["ints"] / merged["targets"].replace(0, np.nan)
        merged["td_rate_allowed"] = merged["tds"] / merged["targets"].replace(0, np.nan)
        merged["adot_allowed"] = merged["adot"]
        merged["yac_per_target_allowed"] = merged["yac"] / merged["targets"].replace(0, np.nan)
        for col, display, denom_col, min_n in [
            ("comp_pct_allowed", "s_comp_pct_allowed", "targets", 15),
            ("yards_per_target", "s_yards_per_target_allowed", "targets", 15),
            ("int_rate", "s_int_rate", "targets", 15),
            ("td_rate_allowed", "s_td_rate_allowed", "targets", 15),
            ("adot_allowed", "s_adot_allowed", "targets", 15),
            ("yac_per_target_allowed", "s_yac_per_target_allowed", "targets", 15),
        ]:
            mask = merged[denom_col].fillna(0) >= min_n
            panel = merged.loc[mask, ["player_id", "season", col]].rename(
                columns={col: "value"}
            )
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    # 4. nflvs aggregates: forced fumbles + interceptions per snap (defensive
    # playmaking distinct from coverage)
    nflvs_frames = []
    for s in seasons:
        if s < 2018:
            continue
        ps = nfl.load_player_stats(seasons=[int(s)])
        if hasattr(ps, "to_pandas"):
            ps = ps.to_pandas()
        ps = ps[ps["position"] == "S"][[
            "player_id",
            "def_fumbles_forced",
            "def_interceptions",
            "def_tackles_for_loss",
            "def_sacks",
        ]].copy()
        ps = ps.rename(columns={"player_id": "gsis_id"})
        agg = ps.groupby("gsis_id", as_index=False).sum(numeric_only=True)
        agg["season"] = s
        nflvs_frames.append(agg)
    if nflvs_frames:
        nflvs = pd.concat(nflvs_frames, ignore_index=True)
        nflvs = nflvs.merge(s_ids, on=["gsis_id", "season"], how="inner")
        nflvs["forced_fumble_per_snap"] = nflvs["def_fumbles_forced"] / nflvs["snaps_defense"].replace(0, np.nan)
        nflvs["int_per_snap"] = nflvs["def_interceptions"] / nflvs["snaps_defense"].replace(0, np.nan)
        nflvs["tfl_per_snap"] = nflvs["def_tackles_for_loss"] / nflvs["snaps_defense"].replace(0, np.nan)
        nflvs["sack_per_snap"] = nflvs["def_sacks"] / nflvs["snaps_defense"].replace(0, np.nan)
        for col, display in [
            ("forced_fumble_per_snap", "s_forced_fumble_per_snap"),
            ("int_per_snap", "s_int_per_snap"),
            ("tfl_per_snap", "s_tfl_per_snap"),
            ("sack_per_snap", "s_sack_per_snap"),
        ]:
            mask = nflvs["snaps_defense"].fillna(0) >= 400
            panel = nflvs.loc[mask, ["player_id", "season", col]].rename(
                columns={col: "value"}
            )
            panel = panel.dropna(subset=["value"])
            candidates.append((display, panel, False))

    return candidates


def run_s_audit(engine: Engine | None = None) -> list[CandidateScore]:
    """Run the full Safety exhaustive audit."""
    eng = engine or get_engine()
    cands = s_candidates(eng)
    return [
        score_candidate(
            name, panel, "S",
            season_pairs=_DEFENSIVE_SEASONS,
            engine=eng,
            is_existing_component=is_existing,
        )
        for name, panel, is_existing in cands
    ]


__all__ = [
    "CandidateScore",
    "format_results_table",
    "qb_candidates",
    "run_qb_audit",
    "score_candidate",
    "wr_candidates",
    "run_wr_audit",
    "rb_candidates",
    "run_rb_audit",
    "te_candidates",
    "run_te_audit",
    "cb_candidates",
    "run_cb_audit",
    "s_candidates",
    "run_s_audit",
]
