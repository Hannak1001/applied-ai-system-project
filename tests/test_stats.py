from src.agent import MusicAgent
from src.stats import compute_stats


def chat(requests, liked=()):
    return {"agent": {"requests": list(requests), "liked": list(liked)}}


def snap(mood, genre="any", energy=0.5, acoustic=False):
    return {"mood": mood, "genre": genre, "energy": energy, "likes_acoustic": acoustic}


def test_empty_history_has_no_data():
    s = compute_stats([])
    assert not s["has_data"] and s["top_moods"] == [] and s["avg_energy"] is None


def test_mood_counts_only_when_it_changes_within_a_chat():
    s = compute_stats([chat([snap("chill"), snap("chill", energy=0.3), snap("energetic")])])
    assert {m["name"]: m["count"] for m in s["top_moods"]} == {"chill": 1, "energetic": 1}
    assert s["requests"] == 3 and s["chats"] == 1


def test_top_lists_aggregate_across_chats_and_rank_by_count():
    chats = [chat([snap("chill", "jazz")]), chat([snap("chill", "jazz")]),
             chat([snap("happy", "pop")])]
    s = compute_stats(chats)
    assert s["top_moods"][0]["name"] == "chill" and s["top_moods"][0]["count"] == 2
    assert s["top_genres"][0]["name"] == "jazz"
    assert abs(sum(m["share"] for m in s["top_moods"]) - 1) < 1e-9


def test_any_genre_is_not_a_genre():
    assert compute_stats([chat([snap("chill", "any")])])["top_genres"] == []


def test_energy_and_sound_use_the_final_snapshot_per_chat():
    s = compute_stats([chat([snap("chill", energy=0.9), snap("chill", energy=0.3, acoustic=True)]),
                       chat([snap("happy", energy=0.7, acoustic=False)])])
    assert abs(s["avg_energy"] - 0.5) < 1e-9
    assert s["acoustic_share"] == 0.5


def test_liked_songs_counted_even_without_requests():
    s = compute_stats([chat([], liked=[{"genre": "jazz"}, {"genre": "jazz"}])])
    assert s["liked_total"] == 2 and s["top_liked_genres"][0]["name"] == "jazz"
    assert not s["has_data"]


def test_agent_logs_and_restores_requests():
    agent = MusicAgent(use_llm=False)
    agent.known = {"mood": "chill", "energy": 0.3}
    agent.log_request()
    restored = MusicAgent.from_state(agent.export_state(), use_llm=False)
    assert restored.requests == [{"mood": "chill", "genre": "any", "energy": 0.3,
                                  "likes_acoustic": False}]
