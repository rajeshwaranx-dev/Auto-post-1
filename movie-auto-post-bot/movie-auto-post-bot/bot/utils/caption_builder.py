"""
bot/utils/caption_builder.py

Builds the final Telegram message caption in the exact format:

🎬 Title: MovieName
📅 Year : 2025
📀 Quality: BluRay
🎧 Audio: Tamil + Telugu + Hindi + English

🔺 Telegram File 🔻

♨️ Movie (2025) BR-Rip - x264 - [Tamil + Telugu + Hindi] - (AAC 2.0) - 450MB - ESub.mkv
♨️ Movie (2025) BluRay - 720p - x264 - [Tamil + Telugu + Hindi + Eng] - (DD+5.1 - 192Kbps) - 1.3GB - ESub.mkv

📦 Get all files in one link:
https://t.me/FileStoreBot?start=unique_group_id

Note ❗: If the link is not working, copy it and paste into your browser.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from bot.utils.file_parser import MovieMeta


def build_caption(
    qualities: List[MovieMeta],
    group_deep_link: str,
    title: Optional[str] = None,
    year: Optional[int] = None,
) -> str:
    """
    Build the full formatted caption for a movie post.

    :param qualities: List of MovieMeta objects (one per quality/file).
    :param group_deep_link: The "Get all files" URL.
    :param title: Override title (uses first quality's title by default).
    :param year: Override year.
    :return: Ready-to-send caption string.
    """
    if not qualities:
        return ""

    # Use first meta as representative
    rep = qualities[0]
    movie_title = title or rep.title
    movie_year  = year  or rep.year

    # Collect unique qualities for the header line
    quality_set = _unique_ordered([m.quality for m in qualities if m.quality])
    quality_str = " | ".join(quality_set) if quality_set else "—"

    # Collect all unique audio langs across qualities
    all_langs: List[str] = []
    for m in qualities:
        for lang in m.audio_langs:
            if lang not in all_langs:
                all_langs.append(lang)
    lang_str = " + ".join(all_langs) if all_langs else "—"

    lines: List[str] = [
        f"🎬 <b>Title</b>: {movie_title}",
        f"📅 <b>Year</b>  : {movie_year or '—'}",
        f"📀 <b>Quality</b>: {quality_str}",
        f"🎧 <b>Audio</b>: {lang_str}",
        "",
        "🔺 <b>Telegram File</b> 🔻",
        "",
    ]

    for meta in qualities:
        filename = meta.caption_filename()
        lines.append(f"♨️ {filename}")

    lines += [
        "",
        f"📦 <b>Get all files in one link:</b>",
        f"<code>{group_deep_link}</code>",
        "",
        "Note ❗: If the link is not working, copy it and paste into your browser.",
    ]

    return "\n".join(lines)


def build_caption_from_docs(
    quality_docs: List[Dict[str, Any]],
    group_deep_link: str,
    title: Optional[str] = None,
    year: Optional[int] = None,
) -> str:
    """
    Same as build_caption but accepts raw MongoDB quality dicts
    (for re-building captions on edit/update).
    """
    metas = [_doc_to_meta(d) for d in quality_docs]
    return build_caption(metas, group_deep_link, title=title, year=year)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _unique_ordered(lst: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _doc_to_meta(doc: Dict[str, Any]) -> MovieMeta:
    """Reconstruct a MovieMeta from a stored quality dict."""
    from bot.utils.file_parser import MovieMeta  # local import avoids circulars
    m = MovieMeta(raw_filename=doc.get("raw_filename", ""))
    m.title         = doc.get("title", "")
    m.year          = doc.get("year")
    m.quality       = doc.get("quality", "")
    m.resolution    = doc.get("resolution", "")
    m.codec         = doc.get("codec", "")
    m.audio_langs   = doc.get("audio_langs", [])
    m.audio_format  = doc.get("audio_format", "")
    m.audio_bitrate = doc.get("audio_bitrate", "")
    m.file_size_bytes = doc.get("file_size_bytes", 0)
    m.has_esub      = doc.get("has_esub", False)
    m.extension     = doc.get("extension", "mkv")
    return m
