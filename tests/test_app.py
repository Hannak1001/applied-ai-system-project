"""Smoke tests: drive the real Streamlit app headlessly (no browser)."""
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from src import chat_store


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CHATS_PATH", str(tmp_path / "chats.json"))


@contextmanager
def offline():
    # Keep tests fast and deterministic: no Deezer, no Gemini.
    with patch("src.preview.requests.get", side_effect=Exception("offline")), \
         patch("src.llm.generate_json", return_value=None):
        yield


def start():
    with offline():
        at = AppTest.from_file("../app.py", default_timeout=30)
        at.run()
    return at


def say(at, text):
    with offline():
        at.chat_input[0].set_value(text).run()
    return at


def finished_onboarding():
    at = start()
    say(at, "I'm studying")
    say(at, "jazz")
    return at


def test_home_renders_and_chat_bar_is_there():
    at = start()
    assert not at.exception
    assert at.session_state["mode"] == "home"
    assert len(at.chat_input) == 1
    assert any("Playlists" in s.value for s in at.subheader)


def test_typing_on_home_morphs_into_recommender():
    at = start()
    say(at, "I'm studying")
    assert not at.exception
    assert at.session_state["mode"] == "rec"
    assert len(at.chat_input) == 1  # chat bar stays on the new screen


def test_onboarding_leads_to_six_recommendations():
    at = finished_onboarding()
    assert not at.exception
    assert at.session_state["stage"] == "chatting"
    assert len(at.session_state["recs"]["picks"]) == 6


def test_home_button_goes_back_without_losing_the_chat():
    at = finished_onboarding()
    with offline():
        at.button(key="nav_home").click().run()
    assert not at.exception
    assert at.session_state["mode"] == "home"
    assert at.session_state["stage"] == "chatting"
    assert len(at.chat_input) == 1
    say(at, "gym energetic music")  # chatting from Home morphs back
    assert at.session_state["mode"] == "rec"
    assert at.session_state["recs"]["profile"]["mood"] == "energetic"


def test_thumbs_update_the_agent_but_not_the_grid_until_update_picks():
    at = finished_onboarding()
    picks = [p[0] for p in at.session_state["recs"]["picks"]]
    first, second = picks[0], picks[1]
    with offline():
        at.button(key=f"up_rec_{first['id']}").click().run()
    assert not at.exception
    assert [s["id"] for s in at.session_state["agent"].liked] == [first["id"]]
    with offline():
        at.button(key=f"down_rec_{second['id']}").click().run()
    assert not at.exception
    # The grid stays put (no reshuffle, no flash)...
    assert [p[0]["id"] for p in at.session_state["recs"]["picks"]] == [p["id"] for p in picks]
    assert at.session_state["recs_stale"] is True
    # ...and the disliked card is marked so CSS can grey it out.
    assert any("vm-dim" in m.value for m in at.markdown)
    # "Update picks" applies the feedback: the disliked song is gone.
    with offline():
        at.button(key="refresh_picks").click().run()
    assert not at.exception
    shown = [p[0]["id"] for p in at.session_state["recs"]["picks"]]
    assert second["id"] not in shown
    assert at.session_state["recs_stale"] is False


def test_liked_button_turns_primary_and_dislike_marks_card():
    at = finished_onboarding()
    song = at.session_state["recs"]["picks"][0][0]
    assert at.button(key=f"up_rec_{song['id']}").proto.type == "secondary"
    with offline():
        at.button(key=f"up_rec_{song['id']}").click().run()
    assert at.button(key=f"up_rec_{song['id']}").proto.type == "primary"
    with offline():
        at.button(key=f"down_rec_{song['id']}").click().run()
    assert at.button(key=f"down_rec_{song['id']}").proto.type == "primary"
    assert at.button(key=f"up_rec_{song['id']}").proto.type == "secondary"  # undone by the dislike


def test_playlist_page_opens_from_home():
    at = start()
    with offline():
        at.button(key="open_gym").click().run()
    assert not at.exception
    assert any("Gym Hype" in t.value for t in at.title)


def test_chat_is_saved_only_once_there_is_activity():
    at = start()
    assert chat_store.load_all() == []          # opening the app alone saves nothing
    say(at, "I'm studying")
    [saved] = chat_store.load_all()
    assert saved["title"] == "I'm studying"
    assert saved["id"] == at.session_state["chat_id"]


def test_saved_chat_can_be_reopened_in_a_fresh_session():
    at = finished_onboarding()
    saved = chat_store.get_chat(at.session_state["chat_id"])
    assert saved["stage"] == "chatting"
    fresh = start()
    fresh.session_state["agent"] = fresh.session_state["agent"].from_state(saved["agent"])
    assert fresh.session_state["agent"].build_profile()["mood"] == "focused"


def test_stats_panel_empty_then_filled_after_chatting():
    at = start()
    assert any("favorite moods" in m.value for m in at.markdown)   # empty state
    finished = finished_onboarding()
    with offline():
        finished.button(key="nav_home").click().run()
    assert not finished.exception
    assert any("Top moods" in m.value and "focused" in m.value for m in finished.markdown)


def test_one_message_is_enough_to_get_recommendations():
    at = start()
    say(at, "recommend me some romantic music")
    assert not at.exception
    assert at.session_state["stage"] == "chatting"
    assert len(at.session_state["recs"]["picks"]) == 6
    assert at.session_state["recs"]["profile"]["mood"] == "romantic"


def test_a_vague_message_gets_one_follow_up_before_recommendations():
    at = start()
    say(at, "hmm not sure")
    assert at.session_state["stage"] == "onboarding" and at.session_state["recs"] is None
    assert "Tell me a bit more" in at.session_state["messages"][-1]["content"]
    say(at, "I'm working out")
    assert at.session_state["stage"] == "chatting" and at.session_state["recs"]


def test_chat_stuck_waiting_on_optional_questions_is_promoted():
    """The exact state from the bug report: mood known, still 'onboarding'."""
    at = start()
    at.session_state["agent"].known = {"mood": "romantic", "genre": "jazz"}
    at.session_state["messages"].append({"role": "user", "content": "romantic music"})
    with offline():
        at.run()
    assert not at.exception
    assert at.session_state["stage"] == "chatting"
    assert at.session_state["recs"] and at.session_state["recs"]["profile"]["genre"] == "jazz"
