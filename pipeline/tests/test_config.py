"""Tests for environment-variable parsing."""

from __future__ import annotations

import pytest

from nfl_grades.config import Settings


def test_seasons_accepts_comma_separated_string(monkeypatch):
    monkeypatch.setenv("SEASONS", "2016,2017,2018")
    s = Settings()
    assert s.seasons == [2016, 2017, 2018]


def test_seasons_accepts_list_default():
    s = Settings()
    assert 2024 in s.seasons


def test_seasons_strips_whitespace(monkeypatch):
    monkeypatch.setenv("SEASONS", "2022, 2023 , 2024")
    s = Settings()
    assert s.seasons == [2022, 2023, 2024]


def test_seasons_rejects_garbage(monkeypatch):
    monkeypatch.setenv("SEASONS", "2022,not-a-year")
    with pytest.raises(ValueError):
        Settings()
