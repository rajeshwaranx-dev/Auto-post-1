"""
bot/utils/file_parser.py

Parses a raw Telegram filename into structured movie metadata.

Examples handled:
  Avatar.The.Way.of.Water.2022.BluRay.1080p.x265.HEVC.[Tamil+Telugu+Hindi+Eng].DD+5.1.640Kbps.ESub.mkv
  RRR (2022) WEBRip 720p x264 [Tamil - Telugu - Hindi] AAC 2.0 450MB ESub.mkv
  Avengers.Endgame.2019.BRRip.480p.x264.Tamil.AAC.300MB.mkv
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional


# ── Constants ──────────────────────────────────────────────────────────────────

QUALITY_MAP = {
    "bluray": "BluRay",
    "blu-ray": "BluRay",
    "blu_ray": "BluRay",
    "bdrip": "BluRay",
    "brrip": "BRRip",
    "br-rip": "BRRip",
    "webrip": "WEBRip",
    "web-rip": "WEBRip",
    "webdl": "WEB-DL",
    "web-dl": "WEB-DL",
    "hdrip": "HDRip",
    "hd-rip": "HDRip",
    "dvdrip": "DVDRip",
    "dvd-rip": "DVDRip",
    "hdts": "HDTS",
    "hd-ts": "HDTS",
    "hdcam": "HDCAM",
    "camrip": "CAMRip",
    "tvrip": "TVRip",
}

RESOLUTION_PATTERNS = [
    (r"\b2160p\b", "2160p"),
    (r"\b1080p\b", "1080p"),
    (r"\b720p\b", "720p"),
    (r"\b480p\b", "480p"),
    (r"\b360p\b", "360p"),
]

CODEC_MAP = {
    "x265": "x265",
    "x264": "x264",
    "hevc": "HEVC",
    "h265": "HEVC",
    "h.265": "HEVC",
    "h264": "x264",
    "h.264": "x264",
    "xvid": "XviD",
    "divx": "DivX",
    "av1": "AV1",
    "vp9": "VP9",
}

AUDIO_FORMAT_PATTERNS = [
    (r"dd\+\s*5\.1|dolby\s*digital\s*plus\s*5\.1|ddp5\.1", "DD+5.1"),
    (r"dd\s*5\.1|dolby\s*digital\s*5\.1|dd5\.1", "DD 5.1"),
    (r"dd\+\s*7\.1|ddp7\.1", "DD+7.1"),
    (r"dts[-\s]?hd|dts-ma", "DTS-HD MA"),
    (r"\bdts\b", "DTS"),
    (r"truehd\s*atmos|truehd", "TrueHD"),
    (r"aac\s*2\.0|aac2\.0", "AAC 2.0"),
    (r"aac\s*5\.1|aac5\.1", "AAC 5.1"),
    (r"\baac\b", "AAC"),
    (r"ac3\s*5\.1|ac3", "AC3"),
    (r"mp3", "MP3"),
    (r"opus", "Opus"),
    (r"flac", "FLAC"),
    (r"e-ac-3|eac3", "EAC-3"),
]

AUDIO_BITRATE_RE = re.compile(
    r"(\d{2,4})\s*kbps", re.IGNORECASE
)

LANGUAGE_MAP = {
    "tamil": "Tamil",
    "tam": "Tamil",
    "telugu": "Telugu",
    "tel": "Telugu",
    "hindi": "Hindi",
    "hin": "Hindi",
    "english": "English",
    "eng": "English",
    "malayalam": "Malayalam",
    "mal": "Malayalam",
    "kannada": "Kannada",
    "kan": "Kannada",
    "bengali": "Bengali",
    "ben": "Bengali",
    "punjabi": "Punjabi",
    "marathi": "Marathi",
    "korean": "Korean",
    "japanese": "Japanese",
    "chinese": "Chinese",
    "french": "French",
    "spanish": "Spanish",
    "arabic": "Arabic",
    "russian": "Russian",
    "german": "German",
    "italian": "Italian",
    "portuguese": "Portuguese",
}

# Junk tags to strip from title
JUNK_TAGS = re.compile(
    r"\b("
    r"extended|theatrical|directors?\s*cut|unrated|remastered|"
    r"proper|readnfo|internal|retail|scene|yify|yts|rarbg|"
    r"fgt|ganool|mkvcage|psarips|pahe|piracy|torrent|"
    r"www\.[a-z0-9]+\.[a-z]+"
    r")\b",
    re.IGNORECASE,
)


# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class MovieMeta:
    raw_filename: str
    title: str = ""
    year: Optional[int] = None
    quality: str = ""
    resolution: str = ""
    codec: str = ""
    audio_langs: List[str] = field(default_factory=list)
    audio_format: str = ""
    audio_bitrate: str = ""
    file_size_bytes: int = 0
    has_esub: bool = False
    extension: str = ""
    # ── The ACTUAL caption the uploader typed when sending the file ───────────
    # This takes priority over the auto-reconstructed filename in the post.
    # Populated from message.caption in channel_post.py.
    file_caption: str = ""

    # Derived
    @property
    def file_size_human(self) -> str:
        return _human_size(self.file_size_bytes)

    @property
    def movie_key(self) -> str:
        """Normalised key used for grouping: 'the dark knight_2008'"""
        t = self.title.lower().strip()
        y = str(self.year) if self.year else ""
        return f"{t}_{y}"

    @property
    def quality_label(self) -> str:
        """Short quality label for the caption line."""
        parts = [p for p in [self.quality, self.resolution] if p]
        return " - ".join(parts)

    @property
    def audio_label(self) -> str:
        langs = " + ".join(self.audio_langs) if self.audio_langs else ""
        fmt = self.audio_format
        br = self.audio_bitrate
        if fmt and br:
            fmt_str = f"({fmt} - {br})"
        elif fmt:
            fmt_str = f"({fmt})"
        else:
            fmt_str = ""
        parts = [p for p in [langs, fmt_str] if p]
        return " - ".join(parts) if parts else "Unknown"

    def caption_filename(self) -> str:
        """
        Reconstruct a clean filename for the caption line, e.g.:
          Movie (2025) BluRay - 1080p - x264 - [Tamil + Hindi] - (DD+5.1 - 640Kbps) - 3.3GB - ESub.mkv
        """
        parts: List[str] = [f"{self.title} ({self.year})"] if self.year else [self.title]
        if self.quality:
            parts.append(self.quality)
        if self.resolution:
            parts.append(self.resolution)
        if self.codec:
            parts.append(self.codec)
        if self.audio_langs:
            parts.append(f"[{' + '.join(self.audio_langs)}]")
        if self.audio_format or self.audio_bitrate:
            if self.audio_format and self.audio_bitrate:
                parts.append(f"({self.audio_format} - {self.audio_bitrate})")
            elif self.audio_format:
                parts.append(f"({self.audio_format})")
        if self.file_size_bytes:
            parts.append(self.file_size_human)
        if self.has_esub:
            parts.append("ESub")
        ext = self.extension or "mkv"
        return " - ".join(parts) + f".{ext}"


# ── Core parser ────────────────────────────────────────────────────────────────

def parse_filename(filename: str, file_size_bytes: int = 0) -> MovieMeta:
    meta = MovieMeta(raw_filename=filename, file_size_bytes=file_size_bytes)

    # Strip extension
    name, _, ext = filename.rpartition(".")
    if not name:
        name = filename
        ext = ""
    meta.extension = ext.lower()

    # Normalise separators
    normalised = _normalise(name)

    # ESub detection
    meta.has_esub = bool(re.search(r"\besub\b", normalised, re.IGNORECASE))

    # ── Extraction order matters ───────────────────────────────────────────────
    meta.resolution  = _extract_resolution(normalised)
    meta.quality     = _extract_quality(normalised)
    meta.codec       = _extract_codec(normalised)
    meta.audio_format, meta.audio_bitrate = _extract_audio_format(normalised)
    meta.audio_langs = _extract_languages(normalised)
    meta.year        = _extract_year(normalised)
    meta.title       = _extract_title(normalised, meta.year)

    return meta


# ── Private helpers ────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    """Replace dots/underscores (not inside brackets) with spaces."""
    # Preserve content inside [ ] and ( ) as-is, normalise outside
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"(?<!\[)\.(?!\d{4}[\.\s\]])(?!\w+\])", " ", s)
    s = s.replace("_", " ")
    return s


def _extract_year(s: str) -> Optional[int]:
    # Look for 4-digit year between 1900-2099
    matches = re.findall(r"\b(19\d{2}|20\d{2})\b", s)
    return int(matches[-1]) if matches else None


def _extract_resolution(s: str) -> str:
    for pattern, label in RESOLUTION_PATTERNS:
        if re.search(pattern, s, re.IGNORECASE):
            return label
    return ""


def _extract_quality(s: str) -> str:
    for token, label in QUALITY_MAP.items():
        if re.search(r"\b" + re.escape(token) + r"\b", s, re.IGNORECASE):
            return label
    return ""


def _extract_codec(s: str) -> str:
    for token, label in CODEC_MAP.items():
        if re.search(r"\b" + re.escape(token) + r"\b", s, re.IGNORECASE):
            return label
    return ""


def _extract_audio_format(s: str) -> tuple[str, str]:
    fmt = ""
    for pattern, label in AUDIO_FORMAT_PATTERNS:
        if re.search(pattern, s, re.IGNORECASE):
            fmt = label
            break
    br_match = AUDIO_BITRATE_RE.search(s)
    br = f"{br_match.group(1)}Kbps" if br_match else ""
    return fmt, br


def _extract_languages(s: str) -> List[str]:
    # First try to find a bracketed language block  [Tamil + Telugu + Hindi]
    bracket_match = re.search(r"[\[\(]([^\]\)]+)[\]\)]", s)
    found: List[str] = []
    if bracket_match:
        block = bracket_match.group(1)
        langs = re.split(r"[\+\-,&/|]|\s+", block)
        for lang in langs:
            lang = lang.strip()
            mapped = LANGUAGE_MAP.get(lang.lower())
            if mapped and mapped not in found:
                found.append(mapped)

    # Fall back to scanning whole string
    if not found:
        for token, label in LANGUAGE_MAP.items():
            if re.search(r"\b" + re.escape(token) + r"\b", s, re.IGNORECASE):
                if label not in found:
                    found.append(label)

    return found


def _extract_title(s: str, year: Optional[int]) -> str:
    """
    Everything before the year (or first quality/codec/resolution token) is the title.
    """
    # Try to cut at year
    if year:
        idx = s.find(str(year))
        if idx != -1:
            title = s[:idx].strip()
            title = _clean_title(title)
            if title:
                return title

    # Cut at first technical token
    technical_re = re.compile(
        r"\b("
        r"bluray|blu-ray|bdrip|brrip|webrip|webdl|web-dl|hdrip|dvdrip|"
        r"x264|x265|hevc|h264|h265|"
        r"480p|720p|1080p|2160p|"
        r"aac|dd5|ddp|dts|mp3|"
        r"esub"
        r")\b",
        re.IGNORECASE,
    )
    m = technical_re.search(s)
    if m:
        title = s[: m.start()].strip()
        title = _clean_title(title)
        if title:
            return title

    return _clean_title(s)


def _clean_title(s: str) -> str:
    s = JUNK_TAGS.sub("", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"[\[\(\{\]\)\}]+", "", s)
    s = re.sub(r"[-_]{2,}", "", s)
    s = s.strip(" -_.,|:")
    return s.title()


def _human_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}" if unit != "MB" and unit != "GB" else f"{size_bytes:.2f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f}PB"
