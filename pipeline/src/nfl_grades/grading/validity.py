"""Downstream predictive validity check.

For each position, computes the Pearson correlation between this-year
composite grade and next-year Pro Bowl selection (0/1) across qualified
player-seasons. This is the external "is the composite measuring something
real" check, complementing the internal YoY r and correlation diagnostics.

Pro Bowl roster data: ``pipeline/data/pro_bowl_selections.csv``
(curated from Wikipedia Pro Bowl pages, 2018-2024 seasons).

The ``season`` column in the CSV is the regular-season year the player
was honored FOR (so e.g. the "2024 Pro Bowl Games" honors are stored
as season=2023 — but in this codebase we use the regular-season year
the Wikipedia article describes, e.g. 2025 Pro Bowl Games honors players
from the 2024 regular season, stored as season=2024).

Read-only — does not write to DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nfl_grades.db import get_engine

PRO_BOWL_CSV = (
    Path(__file__).resolve().parents[3] / "data" / "pro_bowl_selections.csv"
)


@dataclass(frozen=True)
class ValidityResult:
    position: str
    n_player_seasons: int
    n_pro_bowls_next_year: int
    pearson_r: float
    pro_bowl_rate: float  # base rate in the cohort
    seasons_covered: str


# Suffixes commonly tacked on names (Jr., Sr., II, III, etc.).
_SUFFIX_RE = re.compile(r"\s+(Jr\.?|Sr\.?|II|III|IV|V)$", re.IGNORECASE)
# Multiple whitespace.
_WS_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Aggressively normalize a player name for join purposes.

    Drops punctuation, suffixes, and case. "T. J. Watt" / "T.J. Watt" /
    "TJ Watt" all become "tj watt".
    """
    if not isinstance(name, str):
        return ""
    n = name
    # Drop trailing suffixes before stripping dots (so "Brown Jr." matches).
    n = _SUFFIX_RE.sub("", n)
    # Replace all non-alphanumeric except apostrophe with space.
    n = re.sub(r"[^A-Za-z0-9']", " ", n)
    # Drop apostrophes (so D'Andre matches DAndre — better hit rate even
    # though it's slightly more aggressive).
    n = n.replace("'", "")
    n = _WS_RE.sub(" ", n).strip().lower()
    return n


def _load_pro_bowl_csv() -> pd.DataFrame:
    df = pd.read_csv(PRO_BOWL_CSV)
    df["name_normalized"] = df["name"].apply(normalize_name)
    return df


_GRADES_SQL = text(
    """
    SELECT
        sg.player_id,
        sg.season,
        sg.position,
        sg.composite_grade,
        sg.qualified,
        p.full_name
    FROM season_grades sg
    JOIN players p USING (player_id)
    WHERE sg.qualified = true
      AND sg.composite_grade IS NOT NULL
    """
)


def build_panel(engine: Engine) -> pd.DataFrame:
    """Build the full (player_id, season, position, grade, pro_bowl_next) panel.

    Pro Bowl flag: did this player appear on the Pro Bowl roster for
    ``season + 1``? Match is by normalized name (suffix-stripped, dots
    dropped, lower-cased) — Pro Bowl rosters don't carry player_ids.
    """
    pro_bowl = _load_pro_bowl_csv()
    with engine.connect() as conn:
        grades = pd.read_sql(_GRADES_SQL, conn)
    grades["name_normalized"] = grades["full_name"].apply(normalize_name)

    # Pro Bowl flag: any Pro Bowl row matching name_normalized for season+1.
    # Note: Pro Bowl `season` in our CSV = regular-season year (so 2024
    # = the 2025 Pro Bowl Games, honoring 2024 performance).
    pb_set = set(zip(pro_bowl["name_normalized"], pro_bowl["season"]))
    grades["pro_bowl_next_year"] = [
        1 if (name, season + 1) in pb_set else 0
        for name, season in zip(grades["name_normalized"], grades["season"])
    ]
    return grades


def compute_validity(panel: pd.DataFrame, position: str) -> ValidityResult:
    sub = panel[panel["position"] == position].copy()
    # Only include rows where we COULD observe a next-year Pro Bowl
    # (i.e., season + 1 must be within our Pro Bowl data range).
    pb_seasons = _load_pro_bowl_csv()["season"]
    max_pb_season = int(pb_seasons.max())
    sub = sub[sub["season"] + 1 <= max_pb_season]
    sub = sub[sub["season"] + 1 >= int(pb_seasons.min())]

    n = len(sub)
    n_pb = int(sub["pro_bowl_next_year"].sum())
    if n < 5 or sub["composite_grade"].std() == 0:
        r = float("nan")
    else:
        r = float(sub["composite_grade"].corr(sub["pro_bowl_next_year"]))
    seasons = sub["season"].unique()
    if len(seasons):
        seasons_str = f"{seasons.min()}-{seasons.max()}"
    else:
        seasons_str = "—"
    return ValidityResult(
        position=position,
        n_player_seasons=n,
        n_pro_bowls_next_year=n_pb,
        pearson_r=r,
        pro_bowl_rate=n_pb / n if n else float("nan"),
        seasons_covered=seasons_str,
    )


def run_all(engine: Engine | None = None) -> list[ValidityResult]:
    eng = engine or get_engine()
    panel = build_panel(eng)
    positions = sorted(panel["position"].unique())
    return [compute_validity(panel, p) for p in positions]


def diagnose_match_rate(engine: Engine | None = None) -> dict[str, float]:
    """Sanity check: what fraction of Pro Bowl rows are matched to a player_id?

    Drops below 90% indicate name-normalization issues that should be fixed
    before trusting the validity numbers.
    """
    eng = engine or get_engine()
    panel = build_panel(eng)
    pro_bowl = _load_pro_bowl_csv()

    grade_names = set(panel["name_normalized"])
    pb_names = set(pro_bowl["name_normalized"])
    matched = pb_names & grade_names
    return {
        "n_pro_bowl_unique_players": len(pb_names),
        "n_matched_in_grades": len(matched),
        "match_rate": len(matched) / len(pb_names) if pb_names else 0.0,
        "n_unmatched": len(pb_names - grade_names),
        "unmatched_sample": sorted(list(pb_names - grade_names))[:15],
    }


__all__ = [
    "ValidityResult",
    "build_panel",
    "compute_validity",
    "diagnose_match_rate",
    "normalize_name",
    "run_all",
]
