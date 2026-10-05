"""Tests for the Pro Bowl face-validity labels (ADR-0029): a position-aware
name join, special-teams selections excluded, and only seasons with an
observable label kept."""

from __future__ import annotations

import pandas as pd
import pytest

from nfl_grades.grading.validity import compute_validity, label_pro_bowl, position_group


def _grades(rows: list[tuple[str, int, str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["player_id", "season", "position", "full_name", "composite_grade"]
    )


def _selections(rows: list[tuple[int, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["season", "name", "position"])


class TestPositionGroup:
    @pytest.mark.parametrize(
        ("graded", "roster"),
        [
            ("QB", "QB"),
            ("RB", "FB"),
            ("CB", "FS"),
            ("S", "CB"),
            ("EDGE", "OLB"),
            ("iDL", "DE"),
            ("LB", "ILB"),
            ("K", "K"),
            ("P", "P"),
        ],
    )
    def test_graded_and_roster_positions_share_a_group(self, graded: str, roster: str) -> None:
        assert position_group(graded) == position_group(roster)

    @pytest.mark.parametrize("roster", ["KR", "PR", "ST", "LS", "OT", "OG", "C"])
    def test_special_teams_and_ol_selections_have_no_player_group(self, roster: str) -> None:
        assert position_group(roster) is None


class TestLabelProBowl:
    def test_same_named_players_at_different_positions_do_not_share_selections(self) -> None:
        grades = _grades(
            [
                ("qb", 2019, "QB", "Sam Carter", 80.0),
                ("edge", 2019, "EDGE", "Sam Carter", 70.0),
                ("cb", 2019, "CB", "Byron Murphy", 60.0),
                ("dt", 2019, "iDL", "Byron Murphy", 65.0),
            ]
        )
        selections = _selections([(2019, "Sam Carter", "DE"), (2019, "Byron Murphy", "DT")])

        labeled = label_pro_bowl(grades, selections).set_index("player_id")["pro_bowl"]

        assert labeled.to_dict() == {"qb": 0, "edge": 1, "cb": 0, "dt": 1}

    def test_special_teams_selections_do_not_count(self) -> None:
        grades = _grades([("wr", 2019, "WR", "Andre Roberts", 50.0)])
        selections = _selections([(2019, "Andre Roberts", "KR")])

        labeled = label_pro_bowl(grades, selections)

        assert labeled["pro_bowl"].tolist() == [0]

    def test_names_are_matched_after_normalization(self) -> None:
        grades = _grades([("tj", 2019, "EDGE", "T.J. Watt", 90.0)])
        selections = _selections([(2019, "TJ Watt", "OLB")])

        assert label_pro_bowl(grades, selections)["pro_bowl"].tolist() == [1]

    def test_renamed_players_match_their_current_name_only_in_their_group(self) -> None:
        # The roster says "Josh Allen" for the Jaguars edge rusher, who is
        # "Josh Hines-Allen" in the players table.
        grades = _grades(
            [
                ("qb", 2021, "QB", "Josh Allen", 85.0),
                ("edge", 2021, "EDGE", "Josh Hines-Allen", 75.0),
            ]
        )
        selections = _selections([(2021, "Josh Allen", "DE")])

        labeled = label_pro_bowl(grades, selections).set_index("player_id")["pro_bowl"]

        assert labeled.to_dict() == {"qb": 0, "edge": 1}

    def test_unlabeled_seasons_are_excluded(self) -> None:
        # Labels exist for 2019 and 2020 only. 2018 and 2021 are unobservable,
        # not "not selected".
        grades = _grades(
            [(f"p{season}", season, "QB", "Somebody", 50.0) for season in (2018, 2019, 2020, 2021)]
        )
        selections = _selections([(2019, "Star A", "QB"), (2020, "Star B", "QB")])

        labeled = label_pro_bowl(grades, selections)

        assert sorted(labeled["season"]) == [2019, 2020]

    def test_same_season_by_default(self) -> None:
        grades = _grades([("qb", 2019, "QB", "Lamar Jackson", 95.0)])
        selections = _selections([(2019, "Lamar Jackson", "QB"), (2020, "Other QB", "QB")])

        assert label_pro_bowl(grades, selections)["pro_bowl"].tolist() == [1]

    def test_next_season_flag_labels_with_the_following_season(self) -> None:
        grades = _grades(
            [
                ("a", 2019, "QB", "Lamar Jackson", 95.0),
                ("a", 2020, "QB", "Lamar Jackson", 80.0),
            ]
        )
        selections = _selections([(2019, "Lamar Jackson", "QB"), (2020, "Other QB", "QB")])

        labeled = label_pro_bowl(grades, selections, next_season=True)

        # 2019 is labeled by the 2020 roster (not selected); 2020 has no 2021
        # roster, so it is unobservable and dropped.
        assert labeled[["season", "pro_bowl"]].values.tolist() == [[2019, 0]]

    def test_extra_columns_pass_through(self) -> None:
        grades = _grades([("qb", 2019, "QB", "Lamar Jackson", 95.0)]).assign(value=1.5)
        selections = _selections([(2019, "Lamar Jackson", "QB")])

        assert label_pro_bowl(grades, selections)["value"].tolist() == [1.5]


class TestComputeValidity:
    def test_correlates_grade_with_selection_within_position(self) -> None:
        panel = pd.DataFrame(
            {
                "player_id": [f"p{i}" for i in range(10)] + ["wr"],
                "season": [2019] * 11,
                "position": ["QB"] * 10 + ["WR"],
                "composite_grade": [float(i) for i in range(10)] + [99.0],
                "pro_bowl": [0] * 8 + [1, 1] + [1],
            }
        )

        result = compute_validity(panel, "QB")

        expected = panel.iloc[:10]["composite_grade"].corr(panel.iloc[:10]["pro_bowl"])
        assert result.n_player_seasons == 10
        assert result.n_pro_bowls == 2
        assert result.pearson_r == pytest.approx(expected)
        assert result.seasons_covered == "2019-2019"
