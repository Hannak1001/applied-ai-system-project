"""Album art and 30-second previews from the free Deezer API (no key needed).

Deezer is searched by "title artist". A hit is only accepted if its title and
artist actually resemble ours, so a song never gets someone else's preview.
Every function degrades to "no media" on failure; the UI still works.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional

import requests

SEARCH_URL = "https://api.deezer.com/search"
CACHE_SECONDS = 30 * 60  # preview links are signed and expire, so refresh them
MISS_SECONDS = 120       # remember "not found" briefly so reruns don't hammer the API
TIMEOUT = 6


@dataclass
class Media:
    preview_url: Optional[str]
    cover_url: Optional[str]
    deezer_url: Optional[str]


_cache: Dict[str, tuple] = {}  # key -> (fetched_at, Media or None)


def _norm(text: str) -> str:
    """Lowercase, drop '(feat. x)' / '- remastered' tails and punctuation."""
    text = text.lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)
    text = re.sub(r"\s-\s.*$", " ", text)
    return re.sub(r"[^\w\s]", " ", text).strip()


def _first_artist(artist: str) -> str:
    return _norm(artist.split(",")[0])


def is_match(title: str, artist: str, hit_title: str, hit_artist: str) -> bool:
    """Does a Deezer result plausibly refer to our song?"""
    t_ratio = SequenceMatcher(None, _norm(title), _norm(hit_title)).ratio()
    ours, theirs = _first_artist(artist), _norm(hit_artist)
    artist_ok = bool(ours) and (ours in theirs or theirs in ours
                                or SequenceMatcher(None, ours, theirs).ratio() >= 0.7)
    return t_ratio >= 0.75 and artist_ok


def _clean_title(title: str) -> str:
    """Drop '(feat. x)' and '- Remastered 1999' tails; Deezer's search chokes on them."""
    title = re.sub(r"\(.*?\)|\[.*?\]", " ", title)
    title = re.sub(r"\s-\s.*$", " ", title)
    return " ".join(title.split())


def _search(query: str) -> List[Dict]:
    try:
        response = requests.get(SEARCH_URL, params={"q": query, "limit": 8}, timeout=TIMEOUT)
        return response.json().get("data", []) or []
    except Exception:
        return []


def _fetch(title: str, artist: str) -> Optional[Media]:
    clean, first_artist = _clean_title(title) or title, artist.split(",")[0].strip()
    # Most specific query first; the title-only one catches odd artist spellings.
    for query in (f"{clean} {first_artist}", clean):
        for hit in _search(query):
            if is_match(title, artist, hit.get("title", ""), hit.get("artist", {}).get("name", "")):
                album = hit.get("album", {})
                return Media(hit.get("preview") or None,
                             album.get("cover_big") or album.get("cover_medium"),
                             hit.get("link"))
    return None


def lookup(title: str, artist: str) -> Optional[Media]:
    key = f"{title}|{artist}"
    cached = _cache.get(key)
    if cached:
        age = time.time() - cached[0]
        if age < (CACHE_SECONDS if cached[1] else MISS_SECONDS):
            return cached[1]
    media = _fetch(title, artist)
    _cache[key] = (time.time(), media)  # misses expire fast: they may be a network blip
    return media


def lookup_many(songs: List[Dict]) -> List[Optional[Media]]:
    """Look up several songs in parallel, keeping the input order."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(lambda s: lookup(s["title"], s["artist"]), songs))
