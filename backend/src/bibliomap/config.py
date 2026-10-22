"""Runtime settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openalex_api_key: str | None
    openalex_mailto: str | None


def get_settings() -> Settings:
    return Settings(
        openalex_api_key=os.environ.get("BIBLIOMAP_OPENALEX_API_KEY") or None,
        openalex_mailto=os.environ.get("BIBLIOMAP_OPENALEX_MAILTO") or None,
    )
