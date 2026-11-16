"""'Your taste' statistics, computed from saved chats.

A request is a settled profile snapshot the agent logged after a user message
(see MusicAgent.log_request). A mood or genre is counted when it *changes*
from the previous snapshot in the same chat, so tweaking energy ("calmer")
doesn't count as asking for the same mood again.
"""

from collections import Counter
from typing import Dict, List


def _top(counter: Counter, n: int = 5) -> List[Dict]:
    total = sum(counter.values()) or 1
    return [{"name": name, "count": count, "share": count / total}
            for name, count in counter.most_common(n)]


def compute_stats(chats: List[Dict]) -> Dict:
    moods: Counter = Counter()
    genres: Counter = Counter()
    liked_genres: Counter = Counter()
    liked_total = requests = used_chats = 0
    energies: List[float] = []
    acoustic: List[bool] = []

    for chat in chats:
        agent = chat.get("agent", {})
        snaps = agent.get("requests", [])
        liked = agent.get("liked", [])
        liked_total += len(liked)
        liked_genres.update(s["genre"] for s in liked)
        if not snaps:
            continue
        used_chats += 1
        requests += len(snaps)
        prev_mood = prev_genre = None
        for snap in snaps:
            if snap["mood"] != prev_mood:
                moods[snap["mood"]] += 1
            if snap["genre"] not in ("any", prev_genre):
                genres[snap["genre"]] += 1
            prev_mood, prev_genre = snap["mood"], snap["genre"]
        energies.append(snaps[-1]["energy"])      # the taste the chat settled on
        acoustic.append(bool(snaps[-1]["likes_acoustic"]))

    return {
        "has_data": requests > 0,
        "chats": used_chats,
        "requests": requests,
        "liked_total": liked_total,
        "top_moods": _top(moods),
        "top_genres": _top(genres),
        "top_liked_genres": _top(liked_genres, 3),
        "avg_energy": sum(energies) / len(energies) if energies else None,
        "acoustic_share": sum(acoustic) / len(acoustic) if acoustic else None,
    }
