"""Step 2a: turn the raw Kaggle Spotify CSV into the catalog the app searches.

Run once:  python -m src.data_prep

- drops duplicate tracks (Kaggle lists a track once per genre)
- renames columns to the schema the scorer uses
- derives a `mood` label from audio features (the dataset has none)
- samples an even number of tracks per genre so no genre dominates
"""

import sys
from pathlib import Path

import pandas as pd

RAW_PATH = "data/spotify_tracks_raw.csv"
OUT_PATH = "data/catalog.csv"
PER_GENRE = 70  # 114 genres * 70 ~= 8k songs
SEED = 42


def derive_mood(row) -> str:
    """Label a track's mood from valence (positivity), energy and sound.

    These are heuristics, not ground truth: valence/energy only roughly map
    to how a song feels. First matching rule wins.
    """
    energy, valence = row["energy"], row["valence"]
    if row["instrumentalness"] > 0.5 and row["speechiness"] < 0.1 and energy < 0.6:
        return "focused"
    if valence < 0.3 and energy < 0.55:
        return "melancholy"
    if energy >= 0.7:
        return "energetic" if valence >= 0.5 else "intense"
    if energy < 0.6 and 0.35 <= valence < 0.65 and row["acousticness"] >= 0.5:
        return "romantic"
    if energy < 0.45 and valence >= 0.3:
        return "chill"
    if valence >= 0.6:
        return "happy"
    if energy < 0.55:
        return "chill"
    return "moody"


def build_catalog(raw_path: str = RAW_PATH, per_genre: int = PER_GENRE) -> pd.DataFrame:
    df = pd.read_csv(raw_path)
    df = df.dropna(subset=["track_name", "artists", "track_genre"])
    df = df.drop_duplicates(subset="track_id")
    # Same song re-released under several ids: keep the most popular copy.
    df = df.sort_values("popularity", ascending=False)
    df = df.drop_duplicates(subset=["track_name", "artists"])

    df["mood"] = df.apply(derive_mood, axis=1)

    # Even sample per genre, preferring well-known tracks so results feel familiar.
    df = df.groupby("track_genre", group_keys=False).head(per_genre * 3)
    df = df.sample(frac=1, random_state=SEED).groupby("track_genre").head(per_genre)

    catalog = pd.DataFrame(
        {
            "title": df["track_name"],
            "artist": df["artists"].str.replace(";", ", "),
            "genre": df["track_genre"],
            "mood": df["mood"],
            "energy": df["energy"],
            "tempo_bpm": df["tempo"].round(1),
            "valence": df["valence"],
            "danceability": df["danceability"],
            "acousticness": df["acousticness"],
            "popularity": df["popularity"],
            "track_id": df["track_id"],
        }
    ).reset_index(drop=True)
    catalog.insert(0, "id", catalog.index + 1)
    return catalog


def main() -> None:
    if not Path(RAW_PATH).exists():
        sys.exit(f"Missing {RAW_PATH}. Download the Kaggle Spotify Tracks dataset first.")
    catalog = build_catalog()
    catalog.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(catalog)} songs to {OUT_PATH}")
    print("\nMood distribution:")
    print(catalog["mood"].value_counts(normalize=True).round(3).to_string())


if __name__ == "__main__":
    main()
