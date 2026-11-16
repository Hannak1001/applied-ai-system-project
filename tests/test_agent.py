from src.agent import MAX_QUESTIONS, MusicAgent, _clean, extract_rule_based


def run(answers):
    """Drive an offline agent with canned answers; returns (agent, questions)."""
    agent = MusicAgent(use_llm=False)
    questions = []
    answers = iter(answers)
    while (q := agent.next_question()) is not None:
        questions.append(q)
        agent.submit_answer(next(answers, "no idea"))
    return agent, questions


def test_activity_answer_skips_follow_up_questions():
    agent, questions = run(["I'm studying for finals", "jazz"])
    profile = agent.build_profile()
    assert profile["mood"] == "focused"
    assert profile["genre"] == "jazz"
    assert profile["likes_acoustic"] is True
    # activity filled mood/energy/acoustic, so only mood + genre were asked
    assert len(questions) == 2


def test_vague_answers_ask_more_but_never_exceed_cap():
    _, questions = run(["hmm", "dunno", "idk", "whatever"])
    assert len(questions) <= MAX_QUESTIONS


def test_short_answers_are_understood_in_context():
    agent, _ = run(["feeling sad", "surprise me", "low", "acoustic"])
    profile = agent.build_profile()
    assert profile["mood"] == "melancholy"
    assert profile["genre"] == "any"
    assert profile["energy"] == 0.3
    assert profile["likes_acoustic"] is True


def test_hip_hop_not_misread_as_pop():
    assert extract_rule_based("I want some hip hop")["genre"] == "hip-hop"


def test_profile_has_defaults_when_nothing_known():
    profile = MusicAgent(use_llm=False).build_profile()
    assert set(profile) == {"genre", "mood", "energy", "likes_acoustic", "activity",
                            "min_popularity", "max_popularity", "exclude_ids", "stated"}
    assert 0 <= profile["energy"] <= 1


def test_feedback_adjusts_profile():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    before = agent.build_profile()["energy"]
    after = agent.apply_feedback("more upbeat")
    assert after["energy"] > before
    assert agent.apply_feedback("more acoustic")["likes_acoustic"] is True


def test_llm_output_is_sanitized():
    cleaned = _clean({"mood": "ecstatic", "energy": 5, "genre": "Hip Hop",
                      "likes_acoustic": "yes", "activity": "study"})
    assert "mood" not in cleaned          # not in vocabulary
    assert cleaned["energy"] == 1.0       # clamped
    assert "likes_acoustic" not in cleaned  # not a bool
    assert cleaned["activity"] == "study"


def test_new_request_in_feedback_replaces_old_context():
    agent, _ = run(["I'm studying", "jazz"])
    assert agent.build_profile()["mood"] == "focused"
    after = agent.apply_feedback("gym energetic music")
    assert after["activity"] == "workout"
    assert after["mood"] == "energetic"
    assert after["energy"] >= 0.8             # study's 0.35 must not linger
    assert after["likes_acoustic"] is False   # nor study's acoustic preference
    assert after["genre"] == "jazz"           # genre wasn't mentioned, so it stays


def test_feedback_can_change_genre_only():
    agent, _ = run(["I'm studying", "jazz"])
    after = agent.apply_feedback("actually switch to classical")
    assert after["genre"] == "classical" and after["mood"] == "focused"


def test_more_familiar_raises_popularity_floor_each_time():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    assert agent.build_profile()["min_popularity"] is None
    assert agent.apply_feedback("more familiar")["min_popularity"] == 50
    assert agent.apply_feedback("something more familiar")["min_popularity"] == 65
    assert agent.apply_feedback("even more popular")["min_popularity"] == 80
    assert agent.apply_feedback("more popular")["min_popularity"] == 80  # capped


def test_discover_sets_ceiling_and_clears_floor():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    agent.apply_feedback("more familiar")
    after = agent.apply_feedback("show me hidden gems")
    assert after["max_popularity"] == 45 and after["min_popularity"] is None


def test_popularity_preference_survives_a_context_switch():
    agent, _ = run(["I'm studying", "jazz"])
    agent.apply_feedback("more familiar")
    after = agent.apply_feedback("gym energetic music")
    assert after["activity"] == "workout" and after["min_popularity"] == 50


SONG_A = {"id": 7, "title": "A", "artist": "x", "genre": "jazz", "mood": "chill",
          "energy": 0.3, "acousticness": 0.9}


def test_thumbs_up_steers_profile_toward_the_song():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    before = agent.build_profile()
    after = agent.like_song(SONG_A)
    assert after["mood"] == "chill" and after["likes_acoustic"] is True
    assert SONG_A["energy"] <= after["energy"] < before["energy"]
    assert agent.liked == [SONG_A]
    agent.like_song(SONG_A)
    assert len(agent.liked) == 1  # no duplicates


def test_thumbs_down_hides_song_and_nudges_energy_away():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    near = dict(SONG_A, energy=agent.build_profile()["energy"] - 0.05)
    before = agent.build_profile()["energy"]
    after = agent.dislike_song(near)
    assert near["id"] in after["exclude_ids"]
    assert after["energy"] > before  # song was lower, so move up


def test_dislike_after_like_removes_it_from_liked():
    agent, _ = run(["feeling happy", "pop", "medium", "electronic"])
    agent.like_song(SONG_A)
    agent.dislike_song(SONG_A)
    assert agent.liked == []


def test_ready_as_soon_as_mood_or_activity_is_known():
    agent = MusicAgent(use_llm=False)
    assert not agent.ready()
    agent.next_question()
    agent.submit_answer("recommend me some romantic music")
    assert agent.ready()                      # no genre/energy needed
    assert agent.build_profile()["mood"] == "romantic"


def test_vague_first_answer_gets_a_rephrased_follow_up_not_a_genre_question():
    agent = MusicAgent(use_llm=False)
    agent.next_question()
    agent.submit_answer("hmm not sure")
    assert not agent.ready()
    follow_up = agent.next_question()
    assert "Tell me a bit more" in follow_up
    agent.submit_answer("something upbeat with pop")
    assert agent.ready() and agent.build_profile()["genre"] == "pop"


def test_genre_in_a_mood_answer_is_still_picked_up():
    agent = MusicAgent(use_llm=False)
    agent.next_question()
    agent.submit_answer("sad piano music")
    assert agent.known["mood"] == "melancholy" and agent.known["genre"] == "piano"


def test_profile_tracks_what_the_user_actually_stated():
    agent = MusicAgent(use_llm=False)
    assert agent.build_profile()["stated"] == []
    agent.next_question(); agent.submit_answer("recommend me some romantic music")
    assert agent.build_profile()["stated"] == ["mood"]       # energy/sound are defaults
    agent.apply_feedback("calmer")
    assert "energy" in agent.build_profile()["stated"]
    studying = MusicAgent(use_llm=False)
    studying.next_question(); studying.submit_answer("I'm studying")
    assert set(studying.build_profile()["stated"]) == {"mood", "energy", "likes_acoustic"}
