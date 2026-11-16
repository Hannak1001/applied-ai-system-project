from src.recommender import score_song
from src.retrieval import MIN_CANDIDATES, retrieve


def make_songs(n=60, genre="pop", mood="happy", energy=0.7):
    return [
        {"id": i, "title": f"t{i}", "artist": "a", "genre": genre, "mood": mood,
         "energy": energy, "acousticness": 0.3, "valence": 0.5}
        for i in range(n)
    ]


def test_strict_tier_when_enough_matches():
    songs = make_songs()
    r = retrieve({"genre": "pop", "mood": "happy", "energy": 0.7}, songs)
    assert r.tier == "genre + mood + energy" and not r.relaxed
    assert len(r.candidates) == 60


def test_all_candidates_respect_the_energy_window():
    songs = make_songs() + make_songs(30, energy=0.1)
    r = retrieve({"genre": "pop", "mood": "happy", "energy": 0.7}, songs)
    assert all(abs(s["energy"] - 0.7) <= 0.2 for s in r.candidates)


def test_genre_relaxed_when_genre_is_rare():
    songs = make_songs(genre="rock") + make_songs(3, genre="jazz")
    r = retrieve({"genre": "jazz", "mood": "happy", "energy": 0.7}, songs)
    assert r.relaxed and "genre relaxed" in r.tier


def test_any_genre_is_not_flagged_as_relaxed():
    r = retrieve({"genre": "any", "mood": "happy", "energy": 0.7}, make_songs())
    assert not r.relaxed and len(r.candidates) >= MIN_CANDIDATES


def test_empty_match_falls_back_instead_of_returning_nothing():
    songs = make_songs(10, mood="chill", energy=0.1)
    r = retrieve({"genre": "any", "mood": "happy", "energy": 0.9}, songs)
    assert r.tier == "entire catalog" and len(r.candidates) == 10


def test_any_genre_gives_every_song_the_same_genre_credit():
    prefs = {"genre": "any", "mood": "happy", "energy": 0.7, "likes_acoustic": False}
    a = score_song(prefs, make_songs(1, genre="pop")[0])[0]
    b = score_song(prefs, make_songs(1, genre="jazz")[0])[0]
    assert a == b


def test_popularity_floor_filters_candidates():
    songs = make_songs(60)
    for i, song in enumerate(songs):
        song["popularity"] = 90.0 if i < 40 else 10.0
    profile = {"genre": "pop", "mood": "happy", "energy": 0.7, "min_popularity": 50}
    r = retrieve(profile, songs)
    assert len(r.candidates) == 40 and all(s["popularity"] >= 50 for s in r.candidates)
    assert not r.popularity_relaxed


def test_popularity_request_is_dropped_when_too_restrictive():
    songs = make_songs(60)
    for song in songs:
        song["popularity"] = 10.0
    profile = {"genre": "pop", "mood": "happy", "energy": 0.7, "min_popularity": 80}
    r = retrieve(profile, songs)
    assert r.popularity_relaxed and len(r.candidates) == 60


def test_excluded_songs_never_come_back():
    songs = make_songs(60)
    profile = {"genre": "pop", "mood": "happy", "energy": 0.7, "exclude_ids": [0, 1, 2]}
    r = retrieve(profile, songs)
    assert not {0, 1, 2} & {s["id"] for s in r.candidates}
