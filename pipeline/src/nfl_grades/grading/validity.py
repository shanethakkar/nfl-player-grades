"""Pro Bowl face-validity report (ADR-0029).

For each position, the Pearson correlation between a qualified player's
composite grade and whether he was a Pro Bowl selection in the **same**
season (``next_season=True`` labels with the following season instead).
This is a sanity check that grades line up with reputation, never a gate
for Formula changes: those go through the evaluation harness.

Pro Bowl roster data: ``pipeline/data/pro_bowl_selections.csv``, curated
from the Wikipedia Pro Bowl pages. ``season`` is the regular-season year
the players were honored for (the "2025 Pro Bowl Games" roster is stored
as season=2024).

Labels are trustworthy only when:

- the join matches on normalized name **and** position group, because
  rosters carry no player ids (Josh Allen QB and Josh Allen EDGE are
  different people);
- special-teams selections (KR/PR/ST/LS) are dropped, since they say
  nothing about a position grade;
- seasons with no roster in the CSV are dropped rather than counted as
  "not selected".

The 2020 roster has no replacement selections (the game was canceled), so
it is the original selections only; other seasons include replacements.

The labeling and correlation functions are pure. ``build_panel`` and
``run_all`` read grades from the DB for the CLI. Read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nfl_grades.db import get_engine

PRO_BOWL_CSV = Path(__file__).resolve().parents[3] / "data" / "pro_bowl_selections.csv"

# Graded positions and Pro Bowl roster slots, mapped to a group in which a
# name match means the same player. The front seven is one group because
# Pro Bowl OLB covers both 3-4 edge rushers (graded EDGE) and off-ball
# linebackers (graded LB), and DE covers players we grade as iDL
# (ADR-0030). OL is graded per team and special teams not at all, so those
# slots map to no group.
_POSITION_GROUPS: Final[dict[str, str]] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "CB": "DB",
    "S": "DB",
    "FS": "DB",
    "SS": "DB",
    "EDGE": "FRONT7",
    "iDL": "FRONT7",
    "LB": "FRONT7",
    "DE": "FRONT7",
    "DT": "FRONT7",
    "OLB": "FRONT7",
    "ILB": "FRONT7",
    "K": "K",
    "P": "P",
}


def position_group(position: str) -> str | None:
    """Group a graded position or Pro Bowl roster slot for the name join.

    Returns None for slots that never match a position grade (OL, KR, PR,
    ST, LS).
    """
    return _POSITION_GROUPS.get(position)


@dataclass(frozen=True)
class ValidityResult:
    position: str
    n_player_seasons: int
    n_pro_bowls: int
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


def compact_name(name: str) -> str:
    """Normalized name with spaces removed, for the join key.

    Rosters write "TJ Watt" where the players table has "T.J. Watt", which
    normalizes to "t j watt"; compacting makes them equal.
    """
    return normalize_name(name).replace(" ", "")


# Roster name -> players-table name, keyed by position group, for players
# who changed the name they go by. Group-keyed because "Josh Allen" the
# edge rusher must not become the QB.
_ROSTER_NAME_ALIASES: Final[dict[tuple[str, str], str]] = {
    ("Josh Allen", "FRONT7"): "Josh Hines-Allen",
    ("Darius Leonard", "FRONT7"): "Shaquille Leonard",
    ("Justin Madubuike", "FRONT7"): "Nnamdi Madubuike",
    ("Patrick Surtain", "DB"): "Pat Surtain II",
    ("Patrick Surtain II", "DB"): "Pat Surtain II",
    ("Tariq Woolen", "DB"): "Riq Woolen",
}


def load_pro_bowl_selections() -> pd.DataFrame:
    """The curated roster CSV: season, name, position, conference."""
    return pd.read_csv(PRO_BOWL_CSV)


def label_pro_bowl(
    grades: pd.DataFrame,
    selections: pd.DataFrame,
    *,
    next_season: bool = False,
) -> pd.DataFrame:
    """Attach a 0/1 ``pro_bowl`` label to each graded player-season.

    ``grades`` needs player_id, season, position (graded) and full_name;
    other columns pass through. ``selections`` needs season, name and
    position (roster slot). A row is labeled from the roster of its own
    season, or of the following season with ``next_season``. Rows whose
    labeling season has no roster are dropped, so they are never counted
    as "not selected".
    """
    offset = 1 if next_season else 0
    rostered = set(selections["season"].astype(int))
    selected = {
        (compact_name(_ROSTER_NAME_ALIASES.get((name, group), name)), group, int(season))
        for name, position, season in zip(
            selections["name"], selections["position"], selections["season"], strict=True
        )
        if (group := position_group(position)) is not None
    }
    out = grades[(grades["season"] + offset).isin(rostered)].copy()
    out["pro_bowl"] = [
        int((compact_name(name), position_group(position), int(season) + offset) in selected)
        for name, position, season in zip(
            out["full_name"], out["position"], out["season"], strict=True
        )
    ]
    return out


def compute_validity(
    panel: pd.DataFrame,
    position: str,
    value_col: str = "composite_grade",
) -> ValidityResult:
    """Pearson r between ``value_col`` and the ``pro_bowl`` label for one
    position. ``panel`` comes from :func:`label_pro_bowl`."""
    sub = panel[panel["position"] == position]
    n = len(sub)
    n_pb = int(sub["pro_bowl"].sum())
    if n < 5 or sub[value_col].std() == 0:
        r = float("nan")
    else:
        r = float(sub[value_col].corr(sub["pro_bowl"]))
    seasons = sub["season"].unique()
    seasons_str = f"{seasons.min()}-{seasons.max()}" if len(seasons) else "—"
    return ValidityResult(
        position=position,
        n_player_seasons=n,
        n_pro_bowls=n_pb,
        pearson_r=r,
        pro_bowl_rate=n_pb / n if n else float("nan"),
        seasons_covered=seasons_str,
    )


# Completed seasons only: a Provisional season has no Pro Bowl yet.
_GRADES_SQL = text(
    """
    SELECT
        sg.player_id,
        sg.season,
        sg.position,
        sg.composite_grade,
        p.full_name
    FROM season_grades sg
    JOIN players p USING (player_id)
    WHERE sg.qualified = true
      AND sg.composite_grade IS NOT NULL
      AND sg.through_week IS NULL
    """
)


def build_panel(engine: Engine, *, next_season: bool = False) -> pd.DataFrame:
    """Qualified completed-season grades labeled with Pro Bowl selection."""
    with engine.connect() as conn:
        grades = pd.read_sql(_GRADES_SQL, conn)
    return label_pro_bowl(grades, load_pro_bowl_selections(), next_season=next_season)


def run_all(engine: Engine | None = None, *, next_season: bool = False) -> list[ValidityResult]:
    panel = build_panel(engine or get_engine(), next_season=next_season)
    positions = sorted(panel["position"].unique())
    return [compute_validity(panel, p) for p in positions]


def diagnose_match_rate(engine: Engine | None = None) -> dict[str, object]:
    """Sanity check: what fraction of Pro Bowl selections match a graded
    player of the same position group?

    Drops below 90% indicate name-normalization issues that should be fixed
    before trusting the validity numbers. OL and special-teams selections
    are not counted: they can never match a position grade.
    """
    eng = engine or get_engine()
    with eng.connect() as conn:
        grades = pd.read_sql(_GRADES_SQL, conn)
    pro_bowl = load_pro_bowl_selections()

    grade_keys = {
        (compact_name(name), position_group(position))
        for name, position in zip(grades["full_name"], grades["position"], strict=True)
    }
    pb_keys = {
        (compact_name(_ROSTER_NAME_ALIASES.get((name, group), name)), group)
        for name, position in zip(pro_bowl["name"], pro_bowl["position"], strict=True)
        if (group := position_group(position)) is not None
    }
    unmatched = pb_keys - grade_keys
    return {
        "n_pro_bowl_unique_players": len(pb_keys),
        "n_matched_in_grades": len(pb_keys & grade_keys),
        "match_rate": len(pb_keys & grade_keys) / len(pb_keys) if pb_keys else 0.0,
        "n_unmatched": len(unmatched),
        "unmatched_sample": sorted(f"{name} ({group})" for name, group in unmatched)[:15],
    }


__all__ = [
    "ValidityResult",
    "build_panel",
    "compact_name",
    "compute_validity",
    "diagnose_match_rate",
    "label_pro_bowl",
    "load_pro_bowl_selections",
    "normalize_name",
    "position_group",
    "run_all",
]
