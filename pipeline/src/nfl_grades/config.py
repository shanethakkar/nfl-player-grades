"""Runtime configuration, driven by environment variables / .env.

All pipeline code should import `settings` from here rather than reading env
vars directly. This makes tests trivial to configure and keeps env access in
one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Typed view of environment variables."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgres://nflgrades:nflgrades@localhost:5432/nflgrades",
        alias="DATABASE_URL",
    )

    # NoDecode opts out of pydantic-settings' default JSON-parsing of complex
    # types; our validator below handles comma-separated strings.
    seasons: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: list(range(2016, 2026)),
        alias="SEASONS",
    )

    pipeline_cache_dir: Path = Field(
        default=REPO_ROOT / "pipeline" / ".cache",
        alias="PIPELINE_CACHE_DIR",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("seasons", mode="before")
    @classmethod
    def _parse_seasons(cls, v: object) -> list[int]:
        """Accept comma-separated strings, lists, or tuples."""
        if v is None:
            return list(range(2016, 2026))
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        raise TypeError(f"SEASONS must be a string or list, got {type(v).__name__}")

    @field_validator("pipeline_cache_dir", mode="after")
    @classmethod
    def _resolve_cache_dir(cls, v: Path) -> Path:
        """Resolve relative cache paths against REPO_ROOT, not cwd."""
        return v if v.is_absolute() else (REPO_ROOT / v).resolve()


settings = Settings()
