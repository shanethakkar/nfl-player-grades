"""Canonical position taxonomy + mapping from nflreadpy fields.

nflreadpy returns two related fields per player:

  - ``position_group``: broad bucket — QB, RB, WR, TE, OL, DL, LB, DB, ST/SPEC
  - ``position``: specific label — NT, DT, DI, DE, CB, FS, SS, T, G, C, K, ...

Our pipeline grades within 13 canonical buckets defined here. The DL group
needs to be split into iDL vs EDGE because they grade on completely
different components (interior pressure rate vs. edge speed-to-power); the
DB group needs to be split into CB vs S for the same reason.

See ``docs/exploration/2026-04-23-rosters.md`` for the full source-data
analysis behind these mappings.

This module is pure: no DB, no I/O, no DataFrame dependencies. Easy to
unit-test (and the tests live in ``tests/ingest/test_positions.py``).
"""

from __future__ import annotations

from typing import Final, Literal

# ---------------------------------------------------------------------------
# Lookup tables for the two splits that need disambiguation
# ---------------------------------------------------------------------------

# Defensive line: split into interior (iDL) vs edge (EDGE) by specific label.
# Sources: load_players.position values seen for position_group=='DL', plus
# load_rosters.depth_chart_position values inside DL.
_DL_INTERIOR: Final[frozenset[str]] = frozenset({
    "DT", "NT", "DI", "DL",   # defensive tackle, nose tackle, "interior", generic
})
_DL_EDGE: Final[frozenset[str]] = frozenset({
    "DE", "EDGE",             # defensive end, edge rusher (rare modern label)
})

# Defensive backs: CB vs S split.
_DB_CB: Final[frozenset[str]] = frozenset({
    "CB", "DB",               # cornerback (DB is rare generic — bucket as CB by default; see note)
})
_DB_SAFETY: Final[frozenset[str]] = frozenset({
    "S", "FS", "SS", "SAF",
})

# Specialists.
_SPECIALIST_GROUPS: Final[frozenset[str]] = frozenset({"ST", "SPEC", "SPECIALIST"})
_SPECIALIST_CODES: Final[dict[str, str]] = {
    "K":  "K",
    "PK": "K",     # placekicker (rare alt label)
    "P":  "P",
    "LS": "LS",
}

# Direct one-to-one mappings.
_DIRECT_GROUP: Final[dict[str, str]] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",   # fullback grades as RB in v1; small population
    "WR": "WR",
    "TE": "TE",
    "OL": "OL",
    "LB": "LB",
}

# ---------------------------------------------------------------------------
# Canonical positions used everywhere downstream of ingest.
# Keep this list authoritative — schema constraints, grading weights,
# UI filters all key off these strings.
# ---------------------------------------------------------------------------
CanonicalPosition = Literal[
    "QB",
    "RB",
    "WR",
    "TE",
    "OL",
    "iDL",
    "EDGE",
    "LB",
    "CB",
    "S",
    "K",
    "P",
    "LS",
]

CANONICAL_POSITIONS: Final[tuple[CanonicalPosition, ...]] = (
    "QB", "RB", "WR", "TE", "OL", "iDL", "EDGE", "LB", "CB", "S", "K", "P", "LS",
)


class UnknownPositionError(ValueError):
    """Raised when (position_group, position) can't be classified.

    Carries the original inputs so the caller can log them and decide
    whether to drop the row, default to a fallback, or fail loudly.
    """

    def __init__(self, position_group: str | None, position: str | None) -> None:
        self.position_group = position_group
        self.position = position
        super().__init__(
            f"Cannot map (position_group={position_group!r}, position={position!r}) "
            "to a canonical position."
        )


def canonical_position(
    position_group: str | None,
    position: str | None,
) -> CanonicalPosition:
    """Map nflreadpy's (position_group, position) to a canonical bucket.

    Args:
        position_group: Broad bucket from ``load_players.position_group`` or
            ``load_rosters.position`` (which is actually the group, not the
            specific label — nflreadpy naming is confusing here).
        position: Specific label from ``load_players.position`` or
            ``load_rosters.depth_chart_position``. Required to disambiguate
            DL → iDL/EDGE and DB → CB/S; ignored for groups that map 1:1.

    Returns:
        One of ``CANONICAL_POSITIONS``.

    Raises:
        UnknownPositionError: If the inputs don't match any rule. Caller
            should log the offending player's gsis_id and either skip the
            row or escalate.

    Examples:
        >>> canonical_position("QB", "QB")
        'QB'
        >>> canonical_position("DL", "DT")     # Aaron Donald
        'iDL'
        >>> canonical_position("DL", "DE")     # Myles Garrett
        'EDGE'
        >>> canonical_position("DB", "CB")
        'CB'
        >>> canonical_position("DB", "FS")
        'S'
    """
    g = (position_group or "").strip().upper()
    p = (position or "").strip().upper()

    # Specialists: group is ST/SPEC, OR position itself is K/P/LS (rosters
    # often puts specialists at the top level without a group bucket).
    if g in _SPECIALIST_GROUPS or p in _SPECIALIST_CODES:
        if p in _SPECIALIST_CODES:
            return _SPECIALIST_CODES[p]  # type: ignore[return-value]
        raise UnknownPositionError(position_group, position)

    # Direct one-to-one groups.
    if g in _DIRECT_GROUP:
        return _DIRECT_GROUP[g]  # type: ignore[return-value]

    # DL split.
    if g == "DL":
        if p in _DL_INTERIOR:
            return "iDL"
        if p in _DL_EDGE:
            return "EDGE"
        raise UnknownPositionError(position_group, position)

    # DB split.
    if g == "DB":
        if p in _DB_SAFETY:
            return "S"
        if p in _DB_CB:
            return "CB"
        # Default unknown DB to CB (most common); but log via the exception so
        # callers can decide. Defaulting silently would hide upstream churn.
        raise UnknownPositionError(position_group, position)

    # Last-resort: maybe the *position* is one we recognize as a group.
    # Handles cases like rosters where some rows have group=='' and only the
    # specific code, e.g. position='QB' standalone.
    if p in _DIRECT_GROUP:
        return _DIRECT_GROUP[p]  # type: ignore[return-value]

    raise UnknownPositionError(position_group, position)
