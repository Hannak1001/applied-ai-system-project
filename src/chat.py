"""Interactive runner: agent questions -> retrieval -> scoring -> top picks.

Run:  python -m src.chat
"""

from .agent import MusicAgent
from .explain import explain_recommendations
from .recommender import load_songs, recommend_songs
from .retrieval import retrieve

CATALOG = "data/catalog.csv"


def show(profile, songs, k=5):
    result = retrieve(profile, songs)
    picks = recommend_songs(profile, result.candidates, k=k)
    note = f", relaxed to '{result.tier}'" if result.relaxed else ""
    if result.popularity_relaxed:
        note += ", popularity request dropped (too few matches)"
    print(f"\nSearched {len(songs)} songs -> {len(result.candidates)} candidates{note}\n")
    explanations = explain_recommendations(profile, picks)
    for i, ((song, score, reasons), why) in enumerate(zip(picks, explanations), start=1):
        print(f"{i}. {song['title']} - {song['artist']}  [{song['genre']}, {song['mood']}]")
        print(f"   Score {score:.1f}/100 | {reasons}")
        print(f"   Why ({why.source}): {why.text}")


def main() -> None:
    songs = load_songs(CATALOG)
    agent = MusicAgent()
    print("Hi! Let me ask a few questions to find your music.\n")
    while not agent.ready() and (question := agent.next_question()) is not None:
        agent.submit_answer(input(f"{question}\n> "))
    print(f"\n(understood via: {agent.last_source})")
    profile = agent.build_profile()
    print(f"Your profile: {profile}")
    show(profile, songs)

    print("\nRefine with feedback like 'more upbeat', 'less acoustic', 'calmer', 'more familiar', 'something new' (or 'quit').")
    while (feedback := input("> ").strip().lower()) not in ("quit", "q", "exit", ""):
        profile = agent.apply_feedback(feedback)
        print(f"Updated profile: {profile}")
        show(profile, songs)


if __name__ == "__main__":
    main()
