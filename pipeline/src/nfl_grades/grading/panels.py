"""Component panels for the evaluation harness, read from the database.

Builds the inputs ``grading.evaluation`` scores: every Component of a
position's Formula (plus any requested Candidates) per player, season and
split (full season, odd weeks, even weeks), the full-season Qualified
cohort with each player's primary team, and same-season Pro Bowl labels.

Component values come from each grader's own ``extract_features`` with a
week-parity filter, so the full-season split reproduces the stored
Components exactly. Only completed seasons are read. Read-only.

Halves are extracted with the grader's minimum-to-grade bar pro-rated
to half a season, as a mid-season Provisional grade would be. Where a
source has no per-week values the halves use the closest weekly source:
RB RYOE comes from the NGS season summary for the full season but from
NGS weekly rows (games with 10+ carries only) for the halves, shrunk by
those rows' attempts.

Adding a position (#14): give its grader's ``extract_features`` a
``week_parity`` argument, then add a ``PositionSource``. Adding a
Candidate: add a ``Candidate`` whose extract returns player_id, raw, n.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import TextClause, text
from sqlalchemy.engine import Connection

from nfl_grades.grading import evaluation, qb, rb, te, validity, wr
from nfl_grades.grading.filters import (
    QB_DROPBACK_FILTER_SQL,
    QB_DROPBACK_PLAYER_SQL,
    RB_REC_FILTER_SQL,
    RB_RUSH_FILTER_SQL,
    WEEK_PARITY_SQL,
)
from nfl_grades.grading.progress import COMPLETE, FULL_SEASON_GAMES, SeasonProgress
from nfl_grades.grading.weights import (
    QB_V1_SHRINKAGE_K,
    QB_V1_WEIGHTS,
    RB_COMPONENT_RYOE_PER_ATTEMPT,
    RB_V1_SHRINKAGE_K,
    RB_V1_WEIGHTS,
    TE_ROLE_BLOCKING,
    TE_V1_SHRINKAGE_K,
    TE_V1_WEIGHTS,
    WR_V1_SHRINKAGE_K,
    WR_V1_WEIGHTS,
)

# (conn, season, week_parity) -> one row per player.
Extract = Callable[[Connection, int, int | None], pd.DataFrame]

_PARITY: dict[str, int | None] = {"full": None, "odd": 1, "even": 0}

# Odd or even weeks are half a season of volume.
_HALF_SEASON = SeasonProgress(through_week=FULL_SEASON_GAMES // 2, games=FULL_SEASON_GAMES / 2)


@dataclass(frozen=True)
class PositionSource:
    """Where a position's Components, cohort and teams come from.

    ``extract`` returns the grader's features frame (player_id, full_name
    and the columns named in ``component_specs``); ``qualified`` is the
    grader's own full-season Qualified rule. ``team_sql`` takes
    ``:season`` and returns player_id, team_id, n: the volume a player
    had with each team, so the primary team is the one with the most.
    """

    position: str
    extract: Extract
    component_specs: Mapping[str, tuple[str, str]]
    weights: Mapping[str, float]
    shrinkage_k: Mapping[str, float]
    qualified: Callable[[pd.DataFrame], pd.Series]
    team_sql: TextClause
    primary: str

    @property
    def formula(self) -> evaluation.Formula:
        return evaluation.Formula(self.weights, self.shrinkage_k)


@dataclass(frozen=True)
class Candidate:
    """A proposed Component the harness can score. ``extract`` returns
    player_id, raw (the per-play rate) and n (its sample size)."""

    name: str
    position: str
    description: str
    shrinkage_k: float
    extract: Extract


@dataclass(frozen=True)
class EvaluationData:
    panel: pd.DataFrame
    roster: pd.DataFrame
    pro_bowl: pd.DataFrame


# ---------------------------------------------------------------------------
# Primary team
# ---------------------------------------------------------------------------


def _team_sql(position: str, plays: Sequence[tuple[str, str]]) -> TextClause:
    """Volume per (player, team): the plays in ``plays``, each a (player
    id column, play filter) pair, credited to the offense."""
    union = "\n        UNION ALL\n        ".join(
        f"""SELECT {player_col} AS gsis_id, posteam
        FROM plays
        WHERE season = :season AND ({play_filter}) AND {WEEK_PARITY_SQL}"""
        for player_col, play_filter in plays
    )
    return text(f"""
        WITH volume AS (
        {union}
        )
        SELECT p.player_id, ta.team_id, COUNT(*) AS n
        FROM volume t
        JOIN players p ON p.gsis_id = t.gsis_id
        JOIN team_aliases ta ON ta.alias = t.posteam
        WHERE p.position = '{position}'
        GROUP BY p.player_id, ta.team_id
    """)


_TARGETS = ("receiver_player_id", RB_REC_FILTER_SQL)
_CARRIES = ("rusher_player_id", RB_RUSH_FILTER_SQL)


# ---------------------------------------------------------------------------
# QB
# ---------------------------------------------------------------------------

_QB_DROPBACKS_CTE = f"""
    WITH dropbacks AS (
        SELECT {QB_DROPBACK_PLAYER_SQL} AS gsis_id, posteam, sack
        FROM plays
        WHERE season = :season
          AND {QB_DROPBACK_FILTER_SQL}
          AND {WEEK_PARITY_SQL}
    )
"""

_QB_SACK_RATE_SQL = text(
    _QB_DROPBACKS_CTE
    + """
    SELECT p.player_id, AVG(COALESCE(d.sack, FALSE)::int) AS raw, COUNT(*) AS n
    FROM dropbacks d
    JOIN players p ON p.gsis_id = d.gsis_id
    WHERE p.position = 'QB'
    GROUP BY p.player_id
    """
)


def _qb_extract(conn: Connection, season: int, week_parity: int | None) -> pd.DataFrame:
    return qb.extract_features(conn, season, week_parity=week_parity)


# ---------------------------------------------------------------------------
# RB, WR, TE
# ---------------------------------------------------------------------------


def _season_or_half(grader_extract: Callable[..., pd.DataFrame]) -> Extract:
    """A grader's extract with its min-to-grade bar pro-rated for a half."""

    def extract(conn: Connection, season: int, week_parity: int | None) -> pd.DataFrame:
        progress = COMPLETE if week_parity is None else _HALF_SEASON
        return grader_extract(conn, season, progress, week_parity=week_parity)

    return extract


def _rb_extract(conn: Connection, season: int, week_parity: int | None) -> pd.DataFrame:
    """RB features plus ``n_ryoe``, RYOE's sample size: every carry for
    the full season (as the grader shrinks it; the NGS summary covers them
    all), but only the NGS attempts behind a half's weekly rows, which
    skip games under 10 carries."""
    features = _season_or_half(rb.extract_features)(conn, season, week_parity)
    if features.empty:
        return features
    n_col = "n_carries" if week_parity is None else "n_ngs_rush_attempts"
    return features.assign(n_ryoe=features[n_col])


_RB_COMPONENT_SPECS = {
    **rb._COMPONENT_SPECS,
    RB_COMPONENT_RYOE_PER_ATTEMPT: ("ryoe_per_attempt", "n_ryoe"),
}


def _te_qualified(features: pd.DataFrame) -> pd.Series:
    """TE Qualified rule, refusing a Qualified blocking TE.

    The harness scores every TE on ``TE_V1_WEIGHTS``. Blocking TEs are
    graded on ``TE_V1_BLOCKING_WEIGHTS``, but none has been Qualified
    (40+ targets at under 5% of 800+ snaps) in 2016-2025, and the Formula
    of an unqualified player never reaches a metric. If one appears, the
    harness needs per-role Formulas first.
    """
    qualified = te.qualified(features)
    blocking = qualified & (features["role"] == TE_ROLE_BLOCKING)
    if blocking.any():
        raise ValueError(
            f"{int(blocking.sum())} Qualified blocking TE(s): the harness scores one "
            "Formula per position and can't reproduce their grade"
        )
    return qualified


def _sql_candidate(sql: TextClause) -> Extract:
    def extract(conn: Connection, season: int, week_parity: int | None) -> pd.DataFrame:
        rows = conn.execute(sql, {"season": season, "week_parity": week_parity}).mappings()
        return pd.DataFrame(rows, columns=["player_id", "raw", "n"])

    return extract


POSITIONS: dict[str, PositionSource] = {
    "QB": PositionSource(
        position="QB",
        extract=_qb_extract,
        component_specs=qb._COMPONENT_SPECS,
        weights=QB_V1_WEIGHTS,
        shrinkage_k=QB_V1_SHRINKAGE_K,
        qualified=qb.qualified,
        team_sql=_team_sql("QB", [(QB_DROPBACK_PLAYER_SQL, QB_DROPBACK_FILTER_SQL)]),
        primary="qb_epa_per_dropback",
    ),
    # Primary: rushing EPA/attempt, the RB outcome every back has in every
    # season (NGS RYOE covers ~50 RBs a season and none before 2018).
    "RB": PositionSource(
        position="RB",
        extract=_rb_extract,
        component_specs=_RB_COMPONENT_SPECS,
        weights=RB_V1_WEIGHTS,
        shrinkage_k=RB_V1_SHRINKAGE_K,
        qualified=rb.qualified,
        team_sql=_team_sql("RB", [_CARRIES, _TARGETS]),
        primary="rb_rush_epa_per_attempt",
    ),
    "WR": PositionSource(
        position="WR",
        extract=_season_or_half(wr.extract_features),
        component_specs=wr._COMPONENT_SPECS,
        weights=WR_V1_WEIGHTS,
        shrinkage_k=WR_V1_SHRINKAGE_K,
        qualified=wr.qualified,
        team_sql=_team_sql("WR", [_TARGETS]),
        primary="wr_rec_epa_per_target",
    ),
    "TE": PositionSource(
        position="TE",
        extract=_season_or_half(te.extract_features),
        component_specs=te._COMPONENT_SPECS,
        weights=TE_V1_WEIGHTS,
        shrinkage_k=TE_V1_SHRINKAGE_K,
        qualified=_te_qualified,
        team_sql=_team_sql("TE", [_TARGETS]),
        primary="te_rec_epa_per_target",
    ),
}

CANDIDATES: dict[str, Candidate] = {
    c.name: c
    for c in [
        Candidate(
            name="qb_sack_rate",
            position="QB",
            description="Sacks per dropback, scrambles included. Lower is better: weight it negative.",
            shrinkage_k=150.0,
            extract=_sql_candidate(_QB_SACK_RATE_SQL),
        ),
    ]
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load(
    conn: Connection,
    source: PositionSource,
    *,
    candidates: Sequence[Candidate] = (),
    seasons: Sequence[int] | None = None,
) -> EvaluationData:
    """Read the panel, roster and Pro Bowl labels for ``source``.

    ``seasons`` defaults to every season in the harness windows.
    """
    if seasons is None:
        seasons = sorted({s for window in evaluation.WINDOWS.values() for s in window})
    panels: list[pd.DataFrame] = []
    rosters: list[pd.DataFrame] = []
    for season in seasons:
        for split, parity in _PARITY.items():
            features = source.extract(conn, season, parity)
            if features.empty:
                continue
            panels.append(
                evaluation.melt_features(
                    features, source.component_specs, season=season, split=split
                )
            )
            for c in candidates:
                values = c.extract(conn, season, parity)
                panels.append(
                    evaluation.melt_features(
                        values, {c.name: ("raw", "n")}, season=season, split=split
                    )
                )
            if split == "full":
                rosters.append(_roster(conn, source, features, season))

    if not rosters:
        raise ValueError(f"no {source.position} data for seasons {list(seasons)}")
    roster = pd.concat(rosters, ignore_index=True)
    labels = validity.label_pro_bowl(
        roster[roster["qualified"]].assign(position=source.position),
        validity.load_pro_bowl_selections(),
    )
    return EvaluationData(
        panel=pd.concat(panels, ignore_index=True),
        roster=roster[["player_id", "season", "team", "qualified"]],
        pro_bowl=labels[["player_id", "season", "pro_bowl"]],
    )


def _roster(
    conn: Connection, source: PositionSource, features: pd.DataFrame, season: int
) -> pd.DataFrame:
    volume = pd.DataFrame(
        conn.execute(source.team_sql, {"season": season, "week_parity": None}).mappings(),
        columns=["player_id", "team_id", "n"],
    )
    primary_team = (
        volume.sort_values(["n", "team_id"])
        .drop_duplicates("player_id", keep="last")
        .set_index("player_id")["team_id"]
    )
    return pd.DataFrame(
        {
            "player_id": features["player_id"].to_numpy(),
            "season": season,
            "full_name": features["full_name"].to_numpy(),
            "team": primary_team.reindex(features["player_id"]).to_numpy(),
            "qualified": source.qualified(features).to_numpy(dtype=bool),
        }
    )


__all__ = ["CANDIDATES", "POSITIONS", "Candidate", "EvaluationData", "PositionSource", "load"]
