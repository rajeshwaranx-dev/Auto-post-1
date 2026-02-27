"""
config.py — All configuration is read from environment variables.
Copy .env.example → .env and fill in your values before starting.
"""
import os
from dataclasses import dataclass, field
from typing import List


def _required(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file or deployment environment."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Config:
    # ── Telegram ───────────────────────────────────────────────────────────────
    API_ID: int             = field(default_factory=lambda: int(_required("API_ID")))
    API_HASH: str           = field(default_factory=lambda: _required("API_HASH"))
    BOT_TOKEN: str          = field(default_factory=lambda: _required("BOT_TOKEN"))

    # Channel/chat where raw video files are uploaded (negative int or @username)
    SOURCE_CHANNEL: str     = field(default_factory=lambda: _required("SOURCE_CHANNEL"))

    # The public destination channel where formatted posts appear (@username or id)
    DEST_CHANNEL: str       = field(default_factory=lambda: _required("DEST_CHANNEL"))

    # Your existing File Store Bot username (without @)
    FILE_STORE_BOT: str     = field(default_factory=lambda: _required("FILE_STORE_BOT"))

    # ── MongoDB ────────────────────────────────────────────────────────────────
    MONGO_URI: str          = field(default_factory=lambda: _required("MONGO_URI"))
    DB_NAME: str            = field(default_factory=lambda: _optional("DB_NAME", "movie_bot"))

    # ── TMDB ──────────────────────────────────────────────────────────────────
    TMDB_API_KEY: str       = field(default_factory=lambda: _required("TMDB_API_KEY"))
    TMDB_LANGUAGE: str      = field(default_factory=lambda: _optional("TMDB_LANGUAGE", "en-US"))

    # Fallback poster URL when TMDB returns nothing
    FALLBACK_POSTER: str    = field(
        default_factory=lambda: _optional(
            "FALLBACK_POSTER",
            "https://i.imgur.com/4eDKRcS.jpeg",
        )
    )

    # ── Misc ──────────────────────────────────────────────────────────────────
    LOG_LEVEL: str          = field(default_factory=lambda: _optional("LOG_LEVEL", "INFO"))

    # Seconds to wait before editing a post with newly grouped quality
    GROUP_WAIT_SECONDS: int = field(default_factory=lambda: _int("GROUP_WAIT_SECONDS", 30))


# Singleton — import this everywhere
settings = Config()
