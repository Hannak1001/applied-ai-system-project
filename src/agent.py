"""Step 1: the conversational agent.

The agent asks a few adaptive questions and turns the answers into a profile
dict that the existing scorer (`recommender.score_song`) already understands:

    {"genre", "mood", "energy", "likes_acoustic", "activity"}

Gemini (free tier) extracts preferences from free-text answers when a
GEMINI_API_KEY is available. If there is no key, the SDK is missing, or a call
fails, a rule-based keyword extractor does the same job, so the agent always
works offline.
"""

import json
import re
from typing import Dict, List, Optional

from .llm import generate_json, load_env

MAX_QUESTIONS = 4

# Vocabulary shared with the data prep step (moods get derived from the
# dataset's valence/energy so they line up with this list).
MOODS: List[str] = [
    "happy", "energetic", "intense", "chill",
    "focused", "melancholy", "romantic", "moody",
]

MOOD_KEYWORDS: Dict[str, List[str]] = {
    "happy": ["happy", "upbeat", "cheerful", "joy", "fun", "good mood", "sunny"],
    "energetic": ["energetic", "hype", "pumped", "workout", "gym", "run", "party", "dance"],
    "intense": ["intense", "aggressive", "angry", "heavy", "hard", "loud"],
    "chill": ["chill", "relax", "calm", "mellow", "laid back", "wind down", "sleep", "cozy"],
    "focused": ["focus", "study", "work", "concentrat", "coding", "homework", "read"],
    "melancholy": ["sad", "melanchol", "down", "cry", "heartbreak", "lonely", "blue"],
    "romantic": ["romantic", "love", "date", "sweet", "intimate"],
    "moody": ["moody", "dark", "brooding", "late night", "night drive", "atmospheric"],
}

# Activity -> sensible defaults, used to fill gaps without another question.
ACTIVITY_PRESETS: Dict[str, Dict] = {
    "workout": {"mood": "energetic", "energy": 0.9, "likes_acoustic": False},
    "study": {"mood": "focused", "energy": 0.35, "likes_acoustic": True},
    "relax": {"mood": "chill", "energy": 0.3, "likes_acoustic": True},
    "party": {"mood": "energetic", "energy": 0.85, "likes_acoustic": False},
    "commute": {"mood": "happy", "energy": 0.65, "likes_acoustic": False},
    "sleep": {"mood": "chill", "energy": 0.15, "likes_acoustic": True},
}

ACTIVITY_KEYWORDS: Dict[str, List[str]] = {
    "workout": ["workout", "gym", "run", "exercise", "lift"],
    "study": ["study", "homework", "focus", "coding", "work", "read"],
    "relax": ["relax", "unwind", "wind down", "chill out"],
    "party": ["party", "dance", "club", "pregame"],
    "commute": ["commute", "drive", "driving", "walk", "road trip", "bus", "train"],
    "sleep": ["sleep", "bed", "nap"],
}

# Keywords -> genre names used in the Kaggle dataset.
GENRE_ALIASES: Dict[str, str] = {
    "pop": "pop", "rock": "rock", "hip hop": "hip-hop", "hip-hop": "hip-hop",
    "rap": "hip-hop", "r&b": "r-n-b", "rnb": "r-n-b", "jazz": "jazz",
    "classical": "classical", "country": "country", "folk": "folk",
    "edm": "edm", "electronic": "electronic", "house": "house",
    "techno": "techno", "metal": "metal", "punk": "punk", "indie": "indie",
    "k-pop": "k-pop", "kpop": "k-pop", "latin": "latin", "reggae": "reggae",
    "blues": "blues", "soul": "soul", "funk": "funk", "disco": "disco",
    "ambient": "ambient", "lofi": "chill", "lo-fi": "chill", "acoustic": "acoustic",
    "piano": "piano", "reggaeton": "reggaeton", "gospel": "gospel",
}

ENERGY_WORDS = [
    (["very high energy", "super high energy", "max energy", "intense", "hype", "pumped"], 0.9),
    (["high energy", "high-energy", "upbeat", "fast", "energetic", "lively"], 0.8),
    (["medium", "moderate", "mid-tempo", "balanced"], 0.55),
    (["low energy", "low-energy", "slow", "soft", "quiet", "mellow", "calm", "chill"], 0.3),
    (["very low", "sleepy", "barely there"], 0.15),
]

# Feedback phrases about how well-known the songs should be.
FAMILIAR_PHRASES = ["more familiar", "more popular", "well known", "well-known",
                    "mainstream", "more hits", "something i know", "bigger songs"]
DISCOVER_PHRASES = ["less known", "more obscure", "hidden gem", "something new",
                    "discover", "underground", "less popular", "deeper cuts"]

QUESTIONS: Dict[str, str] = {
    "mood": "What kind of mood are you in, or what are you doing right now (studying, working out, winding down)?",
    "genre": "Any genre you're into right now? (e.g. pop, rock, jazz, hip-hop, or 'surprise me')",
    "energy": "How much energy do you want: low and mellow, medium, or high and driving?",
    "acoustic": "Do you prefer acoustic, organic sounds, or more electronic/produced ones?",
}
# Ask in this order; slots that are already known get skipped.
QUESTION_ORDER = ["mood", "mood2", "genre", "energy", "acoustic"]
QUESTIONS["mood2"] = ("Tell me a bit more: what are you doing, or how do you want to feel? "
                      "(e.g. studying, working out, relaxing, something upbeat)")
# Slots whose answers may mention a genre.
GENRE_SLOTS = (None, "mood", "mood2", "genre")


def _contains(text: str, keywords: List[str]) -> bool:
    return any(k in text for k in keywords)


def extract_rule_based(text: str, asking: Optional[str] = None) -> Dict:
    """Pull preferences out of free text using keyword matching.

    `asking` is the slot the agent just asked about. It lets short answers
    like "high" or "acoustic" be understood in context.
    """
    t = text.lower().strip()
    found: Dict = {}

    for activity, words in ACTIVITY_KEYWORDS.items():
        if _contains(t, words):
            found["activity"] = activity
            break

    for mood, words in MOOD_KEYWORDS.items():
        if _contains(t, words):
            found["mood"] = mood
            break

    # Only read genres from answers that can contain one, so "acoustic" as an
    # answer to the sound question isn't mistaken for the genre "acoustic".
    # Longest alias first so "hip hop" wins over "pop".
    if asking in GENRE_SLOTS:
        for alias in sorted(GENRE_ALIASES, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", t):
                found["genre"] = GENRE_ALIASES[alias]
                break
    if asking in GENRE_SLOTS and re.search(r"surprise|any genre|no preference|don'?t care|anything", t):
        found["genre"] = "any"

    if asking in (None, "energy"):
        for words, value in ENERGY_WORDS:
            if _contains(t, words):
                found["energy"] = value
                break
        if asking == "energy" and "energy" not in found:
            if re.search(r"\bhigh\b|driving", t):
                found["energy"] = 0.85
            elif re.search(r"\blow\b", t):
                found["energy"] = 0.3
    number = re.search(r"\b(0?\.\d+|1\.0|[0-9]|10)\b", t) if asking == "energy" else None
    if number:
        value = float(number.group())
        found["energy"] = value / 10 if value > 1 else value

    if re.search(r"\bnot acoustic|electronic|produced|synth|no acoustic", t):
        found["likes_acoustic"] = False
    elif re.search(r"acoustic|organic|unplugged|natural", t):
        found["likes_acoustic"] = True

    return found


def extract_with_gemini(text: str, asking: Optional[str], known: Dict) -> Optional[Dict]:
    """Ask Gemini to turn free text into structured preferences.

    Returns None on any failure so the caller can fall back to the rules.
    """
    prompt = (
        "You extract music taste preferences from a user's message.\n"
        f"Allowed moods: {', '.join(MOODS)}.\n"
        f"Allowed activities: {', '.join(ACTIVITY_PRESETS)}.\n"
        "Return ONLY a JSON object with any of these keys that the message "
        "clearly states or implies (omit unknown keys):\n"
        '  "mood": one allowed mood,\n'
        '  "activity": one allowed activity,\n'
        '  "genre": a lowercase genre like pop, rock, jazz, hip-hop, edm, '
        'classical, or "any" if they have no preference,\n'
        '  "energy": number 0.0-1.0 (0 = very calm, 1 = very intense),\n'
        '  "likes_acoustic": true if they like acoustic/organic sound, false '
        "if they prefer electronic/produced.\n"
        f"The agent just asked about: {asking or 'general taste'}.\n"
        f"Already known: {json.dumps(known)}\n"
        f'User message: "{text}"'
    )
    data = generate_json(prompt)
    return _clean(data) if isinstance(data, dict) else None


def _clean(data: Dict) -> Dict:
    """Keep only valid values, so a bad LLM reply can't corrupt the profile."""
    out: Dict = {}
    if data.get("mood") in MOODS:
        out["mood"] = data["mood"]
    if data.get("activity") in ACTIVITY_PRESETS:
        out["activity"] = data["activity"]
    genre = data.get("genre")
    if isinstance(genre, str) and genre.strip():
        genre = genre.strip().lower()
        out["genre"] = GENRE_ALIASES.get(genre, genre)
    energy = data.get("energy")
    if isinstance(energy, (int, float)) and not isinstance(energy, bool):
        out["energy"] = min(1.0, max(0.0, float(energy)))
    if isinstance(data.get("likes_acoustic"), bool):
        out["likes_acoustic"] = data["likes_acoustic"]
    return out


class MusicAgent:
    """Asks up to MAX_QUESTIONS adaptive questions and builds a profile.

    Usage:
        agent = MusicAgent()
        while (q := agent.next_question()):
            agent.submit_answer(input(q + " "))
        profile = agent.build_profile()
    """

    def __init__(self, use_llm: bool = True):
        load_env()
        self.use_llm = use_llm
        self.known: Dict = {}
        self.asked: List[str] = []
        self.liked: List[Dict] = []        # songs the user thumbed up
        self.disliked_ids: set = set()     # songs the user never wants to see again
        self.requests: List[Dict] = []     # settled profile snapshots, for the stats page
        self.last_source = "rules"  # "gemini" or "rules", for the UI/tests

    def ready(self) -> bool:
        """Enough to recommend: we know the mood or the activity. Everything else
        (genre, energy, sound) has sensible defaults and can be refined while browsing."""
        return "mood" in self.known or "activity" in self.known

    def _missing_slots(self) -> List[str]:
        missing = []
        for slot in QUESTION_ORDER:
            if slot in ("mood", "mood2") and not self.ready():
                missing.append(slot)
            elif slot == "genre" and "genre" not in self.known:
                missing.append(slot)
            elif slot == "energy" and "energy" not in self.known and "activity" not in self.known:
                missing.append(slot)
            elif slot == "acoustic" and "likes_acoustic" not in self.known and "activity" not in self.known:
                missing.append(slot)
        return missing

    def next_question(self) -> Optional[str]:
        """The next question, or None once we know enough (or hit the cap)."""
        if len(self.asked) >= MAX_QUESTIONS:
            return None
        for slot in self._missing_slots():
            if slot not in self.asked:
                self.asked.append(slot)
                return QUESTIONS[slot]
        return None

    def submit_answer(self, text: str) -> Dict:
        """Update what we know from a free-text answer; returns what was found."""
        asking = self.asked[-1] if self.asked else None
        found = None
        if self.use_llm:
            found = extract_with_gemini(text, asking, self.known)
            if found is not None:
                self.last_source = "gemini"
        if found is None:
            found = extract_rule_based(text, asking)
            self.last_source = "rules"
        self.known.update(found)
        return found

    def apply_feedback(self, text: str) -> Dict:
        """Refine the profile from feedback.

        Two kinds of feedback:
        - relative tweaks ("more upbeat", "calmer", "less acoustic") nudge the
          current profile;
        - a new request ("gym energetic music", "something sad") is read like
          a normal answer. A new mood or activity starts a fresh context, so
          leftovers from the old one (e.g. study's low energy) don't linger.
        """
        t = text.lower()
        profile = self.build_profile()
        relative = False

        if _contains(t, ["more upbeat", "more energy", "faster", "more energetic", "pump"]):
            self.known["energy"] = min(1.0, profile["energy"] + 0.15)
            relative = True
        if _contains(t, ["calmer", "less energy", "slower", "more mellow", "less intense"]):
            self.known["energy"] = max(0.0, profile["energy"] - 0.15)
            relative = True
        if "less acoustic" in t or "more electronic" in t:
            self.known["likes_acoustic"] = False
            relative = True
        if "more acoustic" in t:
            self.known["likes_acoustic"] = True
            relative = True
        if _contains(t, FAMILIAR_PHRASES):
            # Step up the popularity floor each time: 50 -> 65 -> 80.
            floor = self.known.get("min_popularity") or 35
            self.known["min_popularity"] = min(80, floor + 15)
            self.known.pop("max_popularity", None)
            relative = True
        if _contains(t, DISCOVER_PHRASES):
            self.known["max_popularity"] = 45
            self.known.pop("min_popularity", None)
            relative = True
        if relative:
            return self.build_profile()

        found = None
        if self.use_llm:
            found = extract_with_gemini(text, None, self.known)
            if found is not None:
                self.last_source = "gemini"
        if found is None:
            found = extract_rule_based(text, None)
            self.last_source = "rules"

        if "mood" in found or "activity" in found:
            # New context resets mood/energy/sound, but genre and how familiar
            # the user wants songs to be are taste, so they carry over.
            keep = ("genre", "min_popularity", "max_popularity")
            self.known = {k: v for k, v in self.known.items() if k in keep}
        self.known.update(found)
        return self.build_profile()

    def log_request(self) -> None:
        """Record the current taste as one request (call once a message is fully processed)."""
        p = self.build_profile()
        self.requests.append({"mood": p["mood"], "genre": p["genre"],
                              "energy": p["energy"], "likes_acoustic": p["likes_acoustic"]})

    def export_state(self) -> Dict:
        """Everything needed to resume this conversation later (JSON-safe)."""
        return {"known": self.known, "asked": self.asked, "liked": self.liked,
                "disliked_ids": sorted(self.disliked_ids), "requests": self.requests}

    @classmethod
    def from_state(cls, state: Dict, use_llm: bool = True) -> "MusicAgent":
        agent = cls(use_llm=use_llm)
        agent.known = dict(state.get("known", {}))
        agent.asked = list(state.get("asked", []))
        agent.liked = list(state.get("liked", []))
        agent.disliked_ids = set(state.get("disliked_ids", []))
        agent.requests = list(state.get("requests", []))
        return agent

    def like_song(self, song: Dict) -> Dict:
        """Thumbs up: steer toward songs like this one."""
        if all(song["id"] != s["id"] for s in self.liked):
            self.liked.append(song)
        self.disliked_ids.discard(song["id"])
        profile = self.build_profile()
        self.known["mood"] = song["mood"]
        self.known["energy"] = round(profile["energy"] + 0.5 * (song["energy"] - profile["energy"]), 2)
        self.known["likes_acoustic"] = song["acousticness"] >= 0.5
        return self.build_profile()

    def dislike_song(self, song: Dict) -> Dict:
        """Thumbs down: hide this song and nudge energy away from it."""
        self.disliked_ids.add(song["id"])
        self.liked = [s for s in self.liked if s["id"] != song["id"]]
        profile = self.build_profile()
        gap = profile["energy"] - song["energy"]
        if abs(gap) < 0.25:  # only meaningful if the song was close to the target
            step = 0.1 if gap >= 0 else -0.1
            self.known["energy"] = round(min(1.0, max(0.0, profile["energy"] + step)), 2)
        return self.build_profile()

    def build_profile(self) -> Dict:
        """Final profile for the scorer. Fills gaps from activity, then defaults."""
        preset = ACTIVITY_PRESETS.get(self.known.get("activity"), {})
        genre = self.known.get("genre", "any")
        return {
            "genre": genre,
            "mood": self.known.get("mood", preset.get("mood", "happy")),
            "energy": self.known.get("energy", preset.get("energy", 0.6)),
            "likes_acoustic": self.known.get(
                "likes_acoustic", preset.get("likes_acoustic", False)
            ),
            "activity": self.known.get("activity"),
            "min_popularity": self.known.get("min_popularity"),
            "max_popularity": self.known.get("max_popularity"),
            "exclude_ids": sorted(self.disliked_ids),
            # Which of mood/genre/energy/likes_acoustic the user actually expressed (directly
            # or via an activity). The rest are defaults, and explanations must say so.
            "stated": sorted(k for k in ("mood", "genre", "energy", "likes_acoustic")
                             if k in self.known or (
                                 "activity" in self.known and k != "genre")),
        }
