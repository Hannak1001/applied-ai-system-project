"""Home-page playlists and the shared "top picks" helper.

Playlists are not hand-curated: each is just a preset taste profile run
through the same retrieval + scoring pipeline as a user's own profile.
"""

from typing import Dict, List, Tuple

from .recommender import recommend_songs
from .retrieval import RetrievalResult, retrieve

PLAYLISTS: List[Dict] = [
    {"id": "focus", "name": "Deep Focus", "tile": "#1B2733",
     "tagline": "Calm and steady, nothing to distract you",
     "profile": {"genre": "any", "mood": "focused", "energy": 0.35, "likes_acoustic": True}},
    {"id": "gym", "name": "Gym Hype", "tile": "#33211C",
     "tagline": "Fast, loud and built to keep you moving",
     "profile": {"genre": "any", "mood": "energetic", "energy": 0.9, "likes_acoustic": False}},
    {"id": "chill", "name": "Late Night Chill", "tile": "#1C2530",
     "tagline": "Slow it down and wind the day away",
     "profile": {"genre": "any", "mood": "chill", "energy": 0.3, "likes_acoustic": True}},
    {"id": "pop", "name": "Feel-Good Pop", "tile": "#332B1B",
     "tagline": "Bright, easy pop for a good mood",
     "profile": {"genre": "pop", "mood": "happy", "energy": 0.7, "likes_acoustic": False}},
    {"id": "rain", "name": "Rainy Day", "tile": "#1F2430",
     "tagline": "Quiet and a little melancholy",
     "profile": {"genre": "any", "mood": "melancholy", "energy": 0.4, "likes_acoustic": True}},
    {"id": "slow", "name": "Slow Dance", "tile": "#2E2024",
     "tagline": "Warm, gentle and romantic",
     "profile": {"genre": "any", "mood": "romantic", "energy": 0.45, "likes_acoustic": True}},
    {"id": "gems", "name": "Hidden Gems", "tile": "#232620",
     "tagline": "Lesser-known tracks worth finding",
     "profile": {"genre": "any", "mood": "moody", "energy": 0.55, "likes_acoustic": False,
                 "max_popularity": 40}},
]


def diverse_top(
    profile: Dict, songs: List[Dict], k: int, per_artist: int = 1
) -> Tuple[List[Tuple[Dict, float, str]], RetrievalResult]:
    """Top-k scored songs with at most `per_artist` songs from any one artist."""
    result = retrieve(profile, songs)
    ranked = recommend_songs(profile, result.candidates, k=len(result.candidates))
    picks, seen = [], {}
    for song, score, reasons in ranked:
        artist = song["artist"].split(",")[0].strip().lower()
        if seen.get(artist, 0) >= per_artist:
            continue
        seen[artist] = seen.get(artist, 0) + 1
        picks.append((song, score, reasons))
        if len(picks) == k:
            break
    return picks, result
