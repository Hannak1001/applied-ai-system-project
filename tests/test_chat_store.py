import json

import pytest

from src import chat_store
from src.agent import MusicAgent


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CHATS_PATH", str(tmp_path / "chats.json"))


MSGS = [{"role": "assistant", "content": "hi"},
        {"role": "user", "content": "late night studying, something calm please, thanks a lot"}]


def test_save_load_and_title():
    chat_store.save_chat("a", MSGS, "chatting", {"known": {}})
    [chat] = chat_store.load_all()
    assert chat["id"] == "a" and chat["title"].endswith("…") and len(chat["title"]) <= 42
    assert chat["messages"] == MSGS


def test_saving_same_id_updates_instead_of_duplicating():
    chat_store.save_chat("a", MSGS, "onboarding", {})
    chat_store.save_chat("a", MSGS, "chatting", {})
    chats = chat_store.load_all()
    assert len(chats) == 1 and chats[0]["stage"] == "chatting"


def test_most_recent_first_and_delete():
    chat_store.save_chat("old", MSGS, "chatting", {})
    chat_store.save_chat("new", MSGS, "chatting", {})
    data = json.load(open(chat_store.CHATS_PATH))
    data[0]["updated"] = "2020-01-01T00:00:00"
    data[1]["updated"] = "2025-01-01T00:00:00"
    json.dump(data, open(chat_store.CHATS_PATH, "w"))
    assert [c["id"] for c in chat_store.load_all()] == [data[1]["id"], data[0]["id"]]
    chat_store.delete_chat("old")
    assert [c["id"] for c in chat_store.load_all()] == ["new"]


def test_missing_or_corrupt_file_is_empty_not_a_crash(tmp_path):
    assert chat_store.load_all() == []
    (tmp_path / "chats.json").write_text("{not json")
    assert chat_store.load_all() == []


def test_agent_state_survives_a_round_trip():
    agent = MusicAgent(use_llm=False)
    agent.known = {"mood": "chill", "energy": 0.3, "min_popularity": 50}
    song = {"id": 7, "title": "A", "artist": "x", "genre": "jazz", "mood": "chill",
            "energy": 0.3, "acousticness": 0.9}
    agent.like_song(song)
    agent.dislike_song(dict(song, id=8))
    chat_store.save_chat("a", MSGS, "chatting", agent.export_state())
    restored = MusicAgent.from_state(chat_store.get_chat("a")["agent"], use_llm=False)
    assert restored.build_profile() == agent.build_profile()
    assert [s["id"] for s in restored.liked] == [7]
    assert restored.disliked_ids == {8}
