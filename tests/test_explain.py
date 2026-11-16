from unittest.mock import patch

from src.explain import build_facts, explain_recommendations, template_explanation, verify

PROFILE = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}
SONG = {"id": 1, "title": "Sunrise City", "artist": "Neon Echo", "genre": "pop",
        "mood": "happy", "energy": 0.82, "tempo_bpm": 118.0, "valence": 0.84,
        "danceability": 0.79, "acousticness": 0.18, "popularity": 70.0}
FACTS = build_facts(PROFILE, SONG, 99.2, 1)
OFF_SONG = dict(SONG, title="Quiet Lake", genre="jazz", mood="chill", energy=0.3, acousticness=0.9)


def test_good_text_passes():
    text = "Its happy mood and pop genre match, and energy 0.82 is close to your 0.80 target."
    assert verify(text, PROFILE, FACTS) == []


def test_invented_number_is_rejected():
    assert verify("It runs at 140 BPM.", PROFILE, FACTS)


def test_real_tempo_is_accepted():
    assert verify("A steady 118 BPM pop track.", PROFILE, FACTS) == []


def test_wrong_mood_or_genre_is_rejected():
    assert verify("A melancholy tune.", PROFILE, FACTS)
    assert verify("A great jazz pick.", PROFILE, FACTS)


def test_mood_inside_title_is_not_flagged():
    song = dict(SONG, title="Chill Out Anthem")
    facts = build_facts(PROFILE, song, 90, 1)
    assert verify("Chill Out Anthem is a happy pop pick.", PROFILE, facts) == []


def test_wrong_descriptors_are_rejected():
    off = build_facts(PROFILE, OFF_SONG, 50, 1)
    assert verify("A high-energy banger.", PROFILE, off)
    assert verify("A calm, soft track.", PROFILE, FACTS)
    assert verify("A warm acoustic sound.", PROFILE, FACTS)


def test_template_is_honest_about_mismatch():
    off = build_facts(PROFILE, OFF_SONG, 50, 1)
    text = template_explanation(PROFILE, off)
    assert "not the happy you asked for" in text and "rather than pop" in text
    assert verify(text, PROFILE, off) == []  # templates must pass their own checks


def test_template_passes_verification_for_matching_song():
    assert verify(template_explanation(PROFILE, FACTS), PROFILE, FACTS) == []


def test_no_llm_uses_templates():
    result = explain_recommendations(PROFILE, [(SONG, 99.2, "")], use_llm=False)
    assert result[0].source == "template"


def test_bad_gemini_reply_falls_back_but_good_one_is_kept():
    picks = [(SONG, 99.2, ""), (SONG, 90.0, "")]
    reply = {"explanations": [
        {"id": 1, "text": "Its happy mood and pop genre fit your 0.80 energy target."},
        {"id": 2, "text": "The artist toured Europe in 1999."},  # invented
    ]}
    with patch("src.explain.generate_json", return_value=reply):
        a, b = explain_recommendations(PROFILE, picks)
    assert a.source == "gemini"
    assert b.source == "template" and b.issues


def test_gemini_failure_falls_back_for_everything():
    with patch("src.explain.generate_json", return_value=None):
        out = explain_recommendations(PROFILE, [(SONG, 99.2, "")])
    assert out[0].source == "template"


def test_quota_error_triggers_cooldown_and_skips_next_call():
    from unittest.mock import MagicMock
    from src import llm

    client = MagicMock()
    client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    with patch.dict("os.environ", {"GEMINI_API_KEY": "x"}), \
         patch("google.genai.Client", return_value=client):
        llm._blocked_until = 0.0
        assert llm.generate_json("hi") is None
        assert llm.last_error == "quota exceeded"
        assert llm.generate_json("hi again") is None   # skipped, no second API call
        assert client.models.generate_content.call_count == 1
    llm._blocked_until = 0.0


def test_genre_that_shares_a_name_with_a_mood_is_not_a_false_alarm():
    song = dict(SONG, genre="chill", mood="energetic")
    facts = build_facts(PROFILE, song, 80, 1)
    assert verify("It is chill rather than pop, with energy 0.82.", PROFILE, facts) == []
    # ...but claiming the *mood* is chill is still caught.
    assert verify("Its chill mood fits you.", PROFILE, facts)
    assert verify("A chill vibe throughout.", PROFILE, facts)


def test_template_does_not_present_defaults_as_the_users_preferences():
    profile = dict(PROFILE, stated=["mood"])        # user only said the mood
    text = template_explanation(profile, FACTS)
    assert "your 0.80 target" not in text and "your taste" not in text
    assert "assumed" in text
    assert verify(text, profile, FACTS) == []


def test_template_uses_target_and_taste_when_the_user_stated_them():
    profile = dict(PROFILE, stated=["mood", "energy", "likes_acoustic"])
    text = template_explanation(profile, FACTS)
    assert "your 0.80 target" in text and "produced sound" in text
