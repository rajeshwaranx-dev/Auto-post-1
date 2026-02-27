"""
bot/utils/link_generator.py

Generates unique, URL-safe group IDs for the "Get all files" deep link.
The ID is stored in MongoDB and the File Store Bot resolves it to a list
of Telegram file_ids when a user clicks the link.
"""
from __future__ import annotations

import hashlib
import time

from config import settings


def generate_group_id(movie_key: str) -> str:
    """
    Deterministic but unique group ID derived from movie_key + current
    timestamp so two uploads of the same movie at different times get
    different IDs (unless deliberately re-used).

    Format: first 12 chars of SHA-256(movie_key + timestamp_ms)
    Short enough for a Telegram start parameter.
    """
    seed = f"{movie_key}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return digest[:12]


def build_deep_link(group_id: str) -> str:
    """Return the full t.me deep link for the File Store Bot."""
    bot = settings.FILE_STORE_BOT.lstrip("@")
    return f"https://t.me/{bot}?start={group_id}"
