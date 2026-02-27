"""
bot/handlers/channel_post.py

Listens on SOURCE_CHANNEL for new video / document uploads.
On every new file:
  1. Parse filename → metadata
  2. Look up or create a movie record in MongoDB
  3. Fetch TMDB poster (on first encounter)
  4. Build formatted caption
  5. Post (or edit) the message in DEST_CHANNEL
  6. Store file_id in DB so the File Store Bot can forward it later

Grouping strategy
─────────────────
When a file arrives we immediately post (or edit) the DEST_CHANNEL message.
If another quality for the same movie arrives within GROUP_WAIT_SECONDS we
edit the message to include both.  After that window the post is considered
"settled."  A second wave (e.g. a 4K upload days later) also triggers an edit.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.enums import ChatType, MessageMediaType
from pyrogram.types import Message

from bot.client import app
from bot.database.mongo import Database
from bot.utils.caption_builder import build_caption, build_caption_from_docs
from bot.utils.file_parser import MovieMeta, parse_filename
from bot.utils.link_generator import build_deep_link, generate_group_id
from bot.utils.tmdb import tmdb
from config import settings

logger = logging.getLogger(__name__)

# Track in-flight grouping timers:  movie_key → asyncio.Task
_pending_timers: dict[str, asyncio.Task] = {}


# ── Filter helper ──────────────────────────────────────────────────────────────

def _is_source_channel(_, __, message: Message) -> bool:
    """Return True only for messages from SOURCE_CHANNEL."""
    cid = str(message.chat.id)
    src = str(settings.SOURCE_CHANNEL)
    return cid == src or message.chat.username == src.lstrip("@")


source_channel_filter = filters.create(_is_source_channel)


# ── Handler ────────────────────────────────────────────────────────────────────

@app.on_message(
    source_channel_filter
    & (filters.video | filters.document)
)
async def on_file_received(client: Client, message: Message) -> None:
    """Entry point for every new file posted in SOURCE_CHANNEL."""
    try:
        await _process_file(client, message)
    except Exception as exc:
        logger.exception("Unhandled error in on_file_received: %s", exc)


async def _process_file(client: Client, message: Message) -> None:
    # ── 1. Determine filename & size ──────────────────────────────────────────
    media = message.video or message.document
    if media is None:
        return

    filename: str = (
        getattr(media, "file_name", None)
        or getattr(media, "mime_type", "unknown")
        or "unknown"
    )
    file_size: int      = getattr(media, "file_size", 0) or 0
    file_unique_id: str = media.file_unique_id
    file_id: str        = media.file_id

    # ── The caption you typed when uploading the file in SOURCE_CHANNEL ───────
    # This is the exact text that will appear as the ♨️ line in the post.
    # If no caption was typed, we fall back to the parsed filename reconstruction.
    file_caption: str = (message.caption or "").strip()

    logger.info("New file in SOURCE_CHANNEL: '%s' (%s bytes)", filename, file_size)
    logger.info("File caption from uploader : '%s'", file_caption or "(none — will use parsed filename)")

    # ── 2. Parse metadata from filename (used for grouping + header fields) ───
    meta: MovieMeta = parse_filename(filename, file_size)
    if not meta.title:
        logger.warning("Could not extract title from '%s'. Skipping.", filename)
        return

    movie_key = meta.movie_key
    logger.info("Parsed → title='%s', year=%s, key='%s'", meta.title, meta.year, movie_key)

    # ── 3. Quality document (stored in DB per file) ───────────────────────────
    quality_doc = {
        "file_id":        file_id,
        "file_unique_id": file_unique_id,
        "raw_filename":   filename,
        # ↓ This is the key change — store the ACTUAL caption from the uploader.
        # If no caption was provided, fall back to the auto-generated filename.
        "file_caption":   file_caption if file_caption else meta.caption_filename(),
        "title":          meta.title,
        "year":           meta.year,
        "quality":        meta.quality,
        "resolution":     meta.resolution,
        "codec":          meta.codec,
        "audio_langs":    meta.audio_langs,
        "audio_format":   meta.audio_format,
        "audio_bitrate":  meta.audio_bitrate,
        "file_size_bytes":meta.file_size_bytes,
        "has_esub":       meta.has_esub,
        "extension":      meta.extension,
    }

    # ── 4. Check existing movie record ────────────────────────────────────────
    existing = await Database.get_movie(movie_key)

    if existing:
        group_id       = existing["group_id"]
        poster_url     = existing.get("poster_url", settings.FALLBACK_POSTER)
        dest_message_id= existing.get("dest_message_id")
    else:
        # First encounter — generate group_id and fetch poster
        group_id = generate_group_id(movie_key)
        poster_url, _, _ = await tmdb.search_movie(meta.title, meta.year)

    deep_link = build_deep_link(group_id)

    # ── 5. Upsert DB ─────────────────────────────────────────────────────────
    doc = await Database.upsert_movie(
        movie_key=movie_key,
        title=meta.title,
        year=meta.year,
        group_id=group_id,
        new_quality=quality_doc,
        dest_message_id=existing.get("dest_message_id") if existing else None,
        poster_url=poster_url,
    )

    # ── 6. Cancel existing timer for this movie (new file arrived) ────────────
    if movie_key in _pending_timers:
        _pending_timers[movie_key].cancel()
        logger.debug("Cancelled grouping timer for '%s'.", movie_key)

    # ── 7. Schedule post/edit after GROUP_WAIT_SECONDS ───────────────────────
    task = asyncio.create_task(
        _delayed_post(client, movie_key, deep_link, doc["qualities"], poster_url, doc)
    )
    _pending_timers[movie_key] = task


async def _delayed_post(
    client: Client,
    movie_key: str,
    deep_link: str,
    qualities: list,
    poster_url: str,
    doc: dict,
) -> None:
    """
    Wait GROUP_WAIT_SECONDS, then post or edit the DEST_CHANNEL message.
    This allows multiple qualities uploaded in quick succession to be
    grouped into a single post.
    """
    try:
        await asyncio.sleep(settings.GROUP_WAIT_SECONDS)
    except asyncio.CancelledError:
        # Another file arrived; the new task will handle posting
        return
    finally:
        _pending_timers.pop(movie_key, None)

    # Re-fetch latest doc in case more qualities arrived during sleep
    fresh_doc = await Database.get_movie(movie_key)
    if not fresh_doc:
        return

    qualities = fresh_doc["qualities"]
    deep_link  = build_deep_link(fresh_doc["group_id"])
    poster_url = fresh_doc.get("poster_url", settings.FALLBACK_POSTER)

    caption = build_caption_from_docs(
        qualities,
        deep_link,
        title=fresh_doc["title"],
        year=fresh_doc.get("year"),
    )

    dest_message_id: Optional[int] = fresh_doc.get("dest_message_id")

    if dest_message_id:
        # Edit existing post
        await _edit_post(client, dest_message_id, caption)
    else:
        # Send new post
        new_msg_id = await _send_post(client, poster_url, caption)
        if new_msg_id:
            await Database.movies.update_one(
                {"movie_key": movie_key},
                {"$set": {"dest_message_id": new_msg_id}},
            )


async def _send_post(client: Client, poster_url: str, caption: str) -> Optional[int]:
    """Send a new photo post to DEST_CHANNEL and return its message_id."""
    dest = settings.DEST_CHANNEL
    try:
        msg = await client.send_photo(
            chat_id=dest,
            photo=poster_url,
            caption=caption,
            parse_mode="html",
        )
        logger.info("Posted new message id=%s to DEST_CHANNEL.", msg.id)
        return msg.id
    except Exception as exc:
        logger.error("Failed to send photo to DEST_CHANNEL: %s", exc)
        # Retry without photo
        try:
            msg = await client.send_message(
                chat_id=dest,
                text=caption,
                parse_mode="html",
                disable_web_page_preview=True,
            )
            logger.info("Fallback text message id=%s sent.", msg.id)
            return msg.id
        except Exception as exc2:
            logger.error("Fallback text send also failed: %s", exc2)
            return None


async def _edit_post(client: Client, message_id: int, caption: str) -> None:
    """Edit caption of an existing DEST_CHANNEL post."""
    dest = settings.DEST_CHANNEL
    try:
        await client.edit_message_caption(
            chat_id=dest,
            message_id=message_id,
            caption=caption,
            parse_mode="html",
        )
        logger.info("Edited message id=%s with updated qualities.", message_id)
    except Exception as exc:
        # Caption edit can fail if message has no media; try text edit
        try:
            await client.edit_message_text(
                chat_id=dest,
                message_id=message_id,
                text=caption,
                parse_mode="html",
                disable_web_page_preview=True,
            )
            logger.info("Edited text message id=%s.", message_id)
        except Exception as exc2:
            logger.error("Edit failed for message id=%s: %s | %s", message_id, exc, exc2)
