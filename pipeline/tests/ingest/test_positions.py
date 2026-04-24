"""Pure unit tests for the position-mapping module.

No DB, no network, no DataFrames. Locks down the canonical taxonomy and
the DL/DB splits with named, recognizable players.
"""

from __future__ import annotations

import pytest

from nfl_grades.ingest._positions import (
    CANONICAL_POSITIONS,
    UnknownPositionError,
    canonical_position,
)


class TestDirectGroups:
    """Groups that map 1:1 to our canonical bucket."""

    @pytest.mark.parametrize(
        ("group", "specific", "expected"),
        [
            ("QB", "QB", "QB"),
            ("RB", "RB", "RB"),
            ("RB", "FB", "RB"),     # FB grades as RB in v1
            ("FB", "FB", "RB"),     # FB-only group also maps to RB
            ("WR", "WR", "WR"),
            ("TE", "TE", "TE"),
            ("OL", "T", "OL"),      # all OL collapses
            ("OL", "G", "OL"),
            ("OL", "C", "OL"),
            ("LB", "ILB", "LB"),
            ("LB", "OLB", "LB"),
            ("LB", "MLB", "LB"),
        ],
    )
    def test_direct_groups(self, group: str, specific: str, expected: str) -> None:
        assert canonical_position(group, specific) == expected


class TestDLSplit:
    """Defensive line: interior vs edge.

    The canonical hard cases — specific players whose classification we
    must NOT silently break.
    """

    def test_aaron_donald_is_idl(self) -> None:
        assert canonical_position("DL", "DT") == "iDL"

    def test_vita_vea_is_idl(self) -> None:
        assert canonical_position("DL", "NT") == "iDL"

    def test_myles_garrett_is_edge(self) -> None:
        assert canonical_position("DL", "DE") == "EDGE"

    def test_di_label_maps_to_idl(self) -> None:
        # Some PFR-derived labels use "DI" for defensive interior.
        assert canonical_position("DL", "DI") == "iDL"

    def test_unknown_dl_position_raises(self) -> None:
        with pytest.raises(UnknownPositionError) as exc:
            canonical_position("DL", "WTF")
        assert exc.value.position_group == "DL"
        assert exc.value.position == "WTF"


class TestDBSplit:
    """Defensive backs: cornerback vs safety."""

    def test_cb_is_cb(self) -> None:
        assert canonical_position("DB", "CB") == "CB"

    def test_fs_is_safety(self) -> None:
        assert canonical_position("DB", "FS") == "S"

    def test_ss_is_safety(self) -> None:
        assert canonical_position("DB", "SS") == "S"

    def test_generic_s_is_safety(self) -> None:
        assert canonical_position("DB", "S") == "S"

    def test_unknown_db_raises(self) -> None:
        with pytest.raises(UnknownPositionError):
            canonical_position("DB", "XYZ")


class TestSpecialists:
    """Kickers, punters, long-snappers."""

    def test_kicker_via_spec_group(self) -> None:
        assert canonical_position("SPEC", "K") == "K"

    def test_kicker_via_st_group(self) -> None:
        assert canonical_position("ST", "K") == "K"

    def test_punter_via_spec(self) -> None:
        assert canonical_position("SPEC", "P") == "P"

    def test_long_snapper(self) -> None:
        assert canonical_position("SPEC", "LS") == "LS"

    def test_kicker_via_position_only(self) -> None:
        # rosters often puts specialists at top level without a group bucket.
        assert canonical_position(None, "K") == "K"
        assert canonical_position("", "P") == "P"
        assert canonical_position(None, "LS") == "LS"


class TestEdgeCases:
    """Whitespace, case, unknowns."""

    def test_whitespace_tolerated(self) -> None:
        assert canonical_position(" QB ", " QB ") == "QB"

    def test_case_tolerated(self) -> None:
        assert canonical_position("qb", "qb") == "QB"

    def test_position_only_qb(self) -> None:
        # rosters DataFrames sometimes have group=='' and position=='QB'.
        assert canonical_position(None, "QB") == "QB"

    def test_completely_unknown_raises(self) -> None:
        with pytest.raises(UnknownPositionError):
            canonical_position("ZZZ", "WAT")

    def test_both_none_raises(self) -> None:
        with pytest.raises(UnknownPositionError):
            canonical_position(None, None)


class TestCanonicalSet:
    """Make sure the documented canonical bucket list is what we think."""

    def test_exactly_thirteen(self) -> None:
        assert len(CANONICAL_POSITIONS) == 13

    def test_all_returned_values_are_canonical(self) -> None:
        # Sample inputs covering every return path; their outputs must all
        # be in the canonical set.
        cases = [
            ("QB", "QB"), ("RB", "RB"), ("WR", "WR"), ("TE", "TE"),
            ("OL", "T"), ("DL", "DT"), ("DL", "DE"), ("LB", "ILB"),
            ("DB", "CB"), ("DB", "FS"), ("SPEC", "K"), ("SPEC", "P"),
            ("SPEC", "LS"),
        ]
        outputs = {canonical_position(g, p) for g, p in cases}
        assert outputs == set(CANONICAL_POSITIONS)
