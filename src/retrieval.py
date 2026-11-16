"""Step 2b: retrieval. Narrow the whole catalog to a short candidate list.

The scorer then ranks only those candidates. If the strict filter finds too
few songs, filters are relaxed one at a time, and the retrieval result says
exactly which ones were relaxed so explanations can stay honest about it.
"""

from dataclasses import dataclass
from typing import Dict, List

MIN_CANDIDATES = 12  # enough for 6 distinct-artist cards; each genre has only ~70 songs
MAX_CANDIDATES = 100
ENERGY_WINDOW = 0.2
WIDE_ENERGY_WINDOW = 0.35

# (label, use_genre, use_mood, energy window). Tried in order; the first tier
# with enough songs wins. Mood outranks genre, matching the scorer's weights.
TIERS = [
    ("genre + mood + energy", True, True, ENERGY_WINDOW),
    ("mood + energy (genre relaxed)", False, True, ENERGY_WINDOW),
    ("genre + energy (mood relaxed)", True, False, ENERGY_WINDOW),
    ("mood + wider energy", False, True, WIDE_ENERGY_WINDOW),
    ("wider energy only", False, False, WIDE_ENERGY_WINDOW),
]


@dataclass
class RetrievalResult:
    candidates: List[Dict]
    tier: str       # which filter tier produced the candidates
    relaxed: bool   # True if the strictest filter was not used
    popularity_relaxed: bool = False  # True if the popularity request was dropped


def retrieve(profile: Dict, songs: List[Dict], limit: int = MAX_CANDIDATES) -> RetrievalResult:
    """Return candidate songs matching the profile's mood, genre and energy."""
    excluded = set(profile.get("exclude_ids") or ())
    if excluded:
        songs = [s for s in songs if s["id"] not in excluded]

    # Familiarity request ("more familiar" / "something new"). If it leaves too
    # few songs, drop it rather than return a thin or empty list.
    low = profile.get("min_popularity")
    high = profile.get("max_popularity")
    popularity_relaxed = False
    if (low is not None or high is not None) and songs and "popularity" in songs[0]:
        pool = [s for s in songs
                if (low is None or s["popularity"] >= low)
                and (high is None or s["popularity"] <= high)]
        if len(pool) >= MIN_CANDIDATES:
            songs = pool
        else:
            popularity_relaxed = True

    genre = profile.get("genre", "any")
    use_genre_pref = genre not in (None, "", "any")

    chosen, chosen_tier = [], TIERS[-1][0]
    for label, use_genre, use_mood, window in TIERS:
        if use_genre and not use_genre_pref:
            continue  # nothing to filter on, so this tier equals a later one
        matches = [
            s for s in songs
            if (not use_genre or s["genre"] == genre)
            and (not use_mood or s["mood"] == profile["mood"])
            and abs(s["energy"] - profile["energy"]) <= window
        ]
        if len(matches) >= MIN_CANDIDATES:
            chosen, chosen_tier = matches, label
            break
    else:
        # Even the loosest tier was thin (tiny catalog): fall back to everything.
        chosen, chosen_tier = list(songs), "entire catalog"

    # Closest in energy first, so the cap keeps the best-fitting songs.
    chosen = sorted(chosen, key=lambda s: abs(s["energy"] - profile["energy"]))[:limit]
    strict = TIERS[0][0] if use_genre_pref else TIERS[1][0]
    return RetrievalResult(
        chosen, chosen_tier, relaxed=chosen_tier != strict,
        popularity_relaxed=popularity_relaxed,
    )
