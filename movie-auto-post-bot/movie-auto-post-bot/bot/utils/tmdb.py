"""
bot/utils/tmdb.py

Fetches movie poster and metadata from The Movie Database (TMDB) API.
Uses aiohttp for fully async HTTP calls.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

TMDB_BASE        = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE  = "https://image.tmdb.org/t/p/w500"


class TMDBClient:
    """Thin async wrapper around TMDB search/details endpoints."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str, **params) -> Optional[dict]:
        session = await self._get_session()
        params["api_key"]  = settings.TMDB_API_KEY
        params["language"] = settings.TMDB_LANGUAGE
        url = f"{TMDB_BASE}{path}"
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("TMDB %s → HTTP %s", path, resp.status)
        except aiohttp.ClientError as exc:
            logger.error("TMDB request error: %s", exc)
        return None

    async def search_movie(
        self, title: str, year: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Returns (poster_url, overview, tmdb_id) for the best match.
        Falls back to settings.FALLBACK_POSTER if nothing found.
        """
        params: dict = {"query": title, "include_adult": "false"}
        if year:
            params["year"] = year

        data = await self._get("/search/movie", **params)
        if not data or not data.get("results"):
            logger.info("TMDB: no results for '%s' (%s). Using fallback.", title, year)
            return settings.FALLBACK_POSTER, None, None

        # Pick best match: prefer exact year match, else first result
        results = data["results"]
        best = None
        if year:
            for r in results:
                release = r.get("release_date", "")
                if release.startswith(str(year)):
                    best = r
                    break
        if best is None:
            best = results[0]

        poster_path = best.get("poster_path")
        poster_url  = (
            f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else settings.FALLBACK_POSTER
        )
        overview    = best.get("overview") or None
        tmdb_id     = str(best.get("id")) if best.get("id") else None

        logger.info(
            "TMDB: found '%s' (id=%s, poster=%s)",
            best.get("title"),
            tmdb_id,
            poster_url,
        )
        return poster_url, overview, tmdb_id


# Module-level singleton
tmdb = TMDBClient()
