"""DB helper for the 2026-09-27 opponent-adjustment analyses (see ../README.md)."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from nfl_grades.db import get_engine


def engine():
    return get_engine()


def q(sql, **kw):
    with engine().connect() as c:
        return pd.read_sql(text(sql), c, params=kw)
