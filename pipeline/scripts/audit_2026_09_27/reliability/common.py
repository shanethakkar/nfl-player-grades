"""Shared helpers for the 2026-09-27 reliability analyses (see ../README.md)."""
from __future__ import annotations

import pathlib

import pandas as pd
from sqlalchemy import text

from nfl_grades.config import settings
from nfl_grades.db import get_engine

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = settings.pipeline_cache_dir / "audit_2026_09_27" / "reliability"
OUT.mkdir(parents=True, exist_ok=True)


def engine():
    return get_engine()


def q(sql, **p):
    with engine().connect() as c:
        return pd.read_sql(text(sql), c, params=p)
