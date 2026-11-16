"""Offline evaluation of the whole pipeline. Run:  python -m src.evaluate

No network and no API key needed, so the numbers are reproducible.

1. Pipeline check: 8 moods x 8 genre choices = 64 profiles. For each, retrieve
   and score the top 6 and measure relevance, diversity and bias.
2. Verifier check: does the grounding verifier reject explanations that make
   claims the song data doesn't support? Includes cases it is *expected* to
   miss, so the report shows its real limits.
"""

import statistics as st
from collections import Counter

from .explain import build_facts, template_explanation, verify
from .playlists import diverse_top
from .recommender import load_songs

MOOD_ENERGY = {"happy": 0.7, "energetic": 0.85, "intense": 0.85, "chill": 0.3,
               "focused": 0.35, "melancholy": 0.35, "romantic": 0.45, "moody": 0.55}
GENRES = ["any", "pop", "rock", "hip-hop", "jazz", "classical", "edm", "country"]

# (text, should_be_rejected). Facts: Sunrise City, pop, happy, energy 0.82,
# acousticness 0.18, 118 BPM. User asked for happy pop at energy 0.80.
ADVERSARIAL = [
    ("It runs at 140 BPM.", True),
    ("A melancholy ballad.", True),
    ("A great jazz pick.", True),
    ("A calm, soft track.", True),
    ("Its warm acoustic sound is perfect.", True),
    ("Released in 2019, it topped the charts.", True),
    ("A classic rock anthem.", True),
    ("The sad lyrics will resonate with you.", True),            # 'sad' is not a catalog mood
    ("The singer's powerful voice really shines.", True),        # outside knowledge, no number
    ("It features a prominent piano melody.", True),             # outside knowledge, no number
    ("Its happy mood and pop genre match your request.", False),
    ("Energy of 0.82 is very close to your 0.80 target at 118 BPM.", False),
    ("Low acousticness of 0.18 suits your taste for produced sound.", False),
]
SONG = {"id": 1, "title": "Sunrise City", "artist": "Neon Echo", "genre": "pop", "mood": "happy",
        "energy": 0.82, "tempo_bpm": 118.0, "valence": 0.84, "danceability": 0.79,
        "acousticness": 0.18, "popularity": 70.0}
PROFILE = {"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}


def pipeline_check(songs):
    rows, picks_all, any_genre_picks, template_ok = [], [], [], 0
    template_total = 0
    for mood, energy in MOOD_ENERGY.items():
        for genre in GENRES:
            profile = {"genre": genre, "mood": mood, "energy": energy,
                       "likes_acoustic": energy < 0.5}
            picks, result = diverse_top(profile, songs, k=6)
            songs_only = [p[0] for p in picks]
            picks_all += songs_only
            if genre == "any":
                any_genre_picks += songs_only
            for i, (song, score, _) in enumerate(picks, 1):
                facts = build_facts(profile, song, score, i)
                template_total += 1
                template_ok += not verify(template_explanation(profile, facts), profile, facts)
            rows.append({
                "full": len(picks) == 6,
                "strict": not result.relaxed,
                "cands": len(result.candidates),
                "artists": len({s["artist"].split(",")[0].lower() for s in songs_only}),
                "mood_match": sum(s["mood"] == mood for s in songs_only) / max(1, len(songs_only)),
                "genre_match": (sum(s["genre"] == genre for s in songs_only) / max(1, len(songs_only))
                                if genre != "any" else None),
                "gap": st.mean(abs(s["energy"] - energy) for s in songs_only) if songs_only else 1,
            })
    n = len(rows)
    gm = [r["genre_match"] for r in rows if r["genre_match"] is not None]
    genre_counts = Counter(s["genre"] for s in any_genre_picks)
    top5 = sum(c for _, c in genre_counts.most_common(5)) / max(1, len(any_genre_picks))
    return {
        "profiles": n,
        "returned_six": sum(r["full"] for r in rows) / n,
        "strict_retrieval": sum(r["strict"] for r in rows) / n,
        "avg_candidates": st.mean(r["cands"] for r in rows),
        "avg_unique_artists": st.mean(r["artists"] for r in rows),
        "mood_match": st.mean(r["mood_match"] for r in rows),
        "genre_match_when_asked": st.mean(gm),
        "avg_energy_gap": st.mean(r["gap"] for r in rows),
        "top5_genre_share_when_any": top5,
        "distinct_genres_when_any": len(genre_counts),
        "avg_popularity_recommended": st.mean(s["popularity"] for s in picks_all),
        "avg_popularity_catalog": st.mean(s["popularity"] for s in songs),
        "template_explanations_grounded": template_ok / template_total,
    }


def verifier_check():
    facts = build_facts(PROFILE, SONG, 99.2, 1)
    results = [(text, expect, bool(verify(text, PROFILE, facts))) for text, expect in ADVERSARIAL]
    bad = [r for r in results if r[1]]
    good = [r for r in results if not r[1]]
    return {
        "bad_total": len(bad),
        "bad_caught": sum(r[2] for r in bad),
        "good_total": len(good),
        "good_wrongly_rejected": sum(r[2] for r in good),
        "missed": [r[0] for r in bad if not r[2]],
    }


def main():
    songs = load_songs("data/catalog.csv")
    p = pipeline_check(songs)
    print(f"\n## Pipeline check ({p['profiles']} profiles, top 6 each)\n")
    print(f"- Returned a full set of 6 picks:           {p['returned_six']:.0%}")
    print(f"- Strict retrieval (no filter relaxed):     {p['strict_retrieval']:.0%}")
    print(f"- Avg candidates retrieved:                 {p['avg_candidates']:.0f}")
    print(f"- Avg distinct artists in the 6 picks:      {p['avg_unique_artists']:.2f}")
    print(f"- Picks matching the requested mood:        {p['mood_match']:.0%}")
    print(f"- Picks matching requested genre (if any):  {p['genre_match_when_asked']:.0%}")
    print(f"- Avg |energy - target|:                    {p['avg_energy_gap']:.3f}")
    print(f"- Genre variety when no genre chosen:       {p['distinct_genres_when_any']} genres, "
          f"top 5 = {p['top5_genre_share_when_any']:.0%} of picks")
    print(f"- Avg popularity, recommended vs catalog:   {p['avg_popularity_recommended']:.1f} "
          f"vs {p['avg_popularity_catalog']:.1f}")
    print(f"- Template explanations that pass grounding: {p['template_explanations_grounded']:.0%}")
    v = verifier_check()
    print("\n## Grounding verifier vs. adversarial explanations\n")
    print(f"- Bad explanations rejected:   {v['bad_caught']}/{v['bad_total']}")
    print(f"- Good explanations rejected:  {v['good_wrongly_rejected']}/{v['good_total']} (false alarms)")
    for text in v["missed"]:
        print(f"  - MISSED: {text}")


if __name__ == "__main__":
    main()
