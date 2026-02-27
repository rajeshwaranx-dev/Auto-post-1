"""
bot/database/mongo.py

Collections
───────────
movies      — one document per unique movie (keyed on normalised title + year)
pending     — temporary staging area while we wait to group qualities
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import motor.motor_asyncio
from pymongo import ASCENDING, IndexModel, ReturnDocument

from config import settings

logger = logging.getLogger(__name__)


class Database:
    _client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
    _db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    @classmethod
    async def connect(cls) -> None:
        cls._client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=10_000,
        )
        cls._db = cls._client[settings.DB_NAME]
        await cls._ensure_indexes()
        logger.info("Motor connected to MongoDB database '%s'.", settings.DB_NAME)

    @classmethod
    async def disconnect(cls) -> None:
        if cls._client:
            cls._client.close()
            logger.info("Motor disconnected.")

    @classmethod
    async def _ensure_indexes(cls) -> None:
        await cls.movies.create_indexes(
            [
                IndexModel([("movie_key", ASCENDING)], unique=True),
                IndexModel([("title", ASCENDING)]),
                IndexModel([("year", ASCENDING)]),
                IndexModel([("group_id", ASCENDING)], unique=True, sparse=True),
            ]
        )
        await cls.pending.create_indexes(
            [
                IndexModel([("movie_key", ASCENDING)]),
                IndexModel([("created_at", ASCENDING)]),
            ]
        )

    # ── Shorthand properties ───────────────────────────────────────────────────

    @classmethod
    @property
    def movies(cls) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return cls._db["movies"]

    @classmethod
    @property
    def pending(cls) -> motor.motor_asyncio.AsyncIOMotorCollection:
        return cls._db["pending"]

    # ── Movie helpers ──────────────────────────────────────────────────────────

    @classmethod
    async def get_movie(cls, movie_key: str) -> Optional[Dict[str, Any]]:
        return await cls.movies.find_one({"movie_key": movie_key})

    @classmethod
    async def upsert_movie(
        cls,
        movie_key: str,
        title: str,
        year: Optional[int],
        group_id: str,
        new_quality: Dict[str, Any],
        dest_message_id: Optional[int] = None,
        poster_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert or update a movie document.
        Adds *new_quality* to the qualities array if not already present
        (deduplication by file_unique_id).
        Returns the updated document.
        """
        now = datetime.now(timezone.utc)

        update: Dict[str, Any] = {
            "$set": {
                "title": title,
                "year": year,
                "group_id": group_id,
                "updated_at": now,
            },
            "$setOnInsert": {
                "movie_key": movie_key,
                "created_at": now,
            },
            "$addToSet": {
                "qualities": new_quality,
            },
        }
        if dest_message_id is not None:
            update["$set"]["dest_message_id"] = dest_message_id
        if poster_url:
            update["$set"]["poster_url"] = poster_url

        doc = await cls.movies.find_one_and_update(
            {"movie_key": movie_key},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc

    @classmethod
    async def get_by_group_id(cls, group_id: str) -> Optional[Dict[str, Any]]:
        return await cls.movies.find_one({"group_id": group_id})

    # ── Pending (grouping buffer) helpers ──────────────────────────────────────

    @classmethod
    async def add_pending(cls, movie_key: str, entry: Dict[str, Any]) -> None:
        """Stage a quality entry while waiting to group."""
        await cls.pending.insert_one(
            {
                "movie_key": movie_key,
                "entry": entry,
                "created_at": datetime.now(timezone.utc),
            }
        )

    @classmethod
    async def pop_pending(cls, movie_key: str) -> List[Dict[str, Any]]:
        """Return and delete all pending entries for a movie_key."""
        cursor = cls.pending.find({"movie_key": movie_key})
        docs = await cursor.to_list(length=None)
        if docs:
            ids = [d["_id"] for d in docs]
            await cls.pending.delete_many({"_id": {"$in": ids}})
        return [d["entry"] for d in docs]

    @classmethod
    async def has_pending(cls, movie_key: str) -> bool:
        return bool(await cls.pending.find_one({"movie_key": movie_key}))
