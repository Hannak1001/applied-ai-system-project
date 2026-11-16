import re

from src.preview import is_match
from src.ui_theme import score_color


def rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def test_score_color_is_valid_hex_everywhere():
    for score in (-10, 0, 35, 50, 62.5, 80, 99, 100, 150):
        assert re.fullmatch(r"#[0-9A-F]{6}", score_color(score))


def test_strong_matches_are_warmer_than_weak_ones():
    strong, weak = rgb(score_color(98)), rgb(score_color(40))
    assert strong[0] > strong[2]   # red channel beats blue: warm
    assert weak[2] > weak[0]       # blue beats red: cool


def test_deezer_match_accepts_variants_and_rejects_strangers():
    assert is_match("River Flows in You", "Yiruma", "River Flows In You", "Yiruma")
    assert is_match("Sunrise - Remastered 2011", "Neon Echo, Guest", "Sunrise", "Neon Echo")
    assert not is_match("River Flows in You", "Yiruma", "Baby", "Justin Bieber")
    assert not is_match("Sunrise", "Neon Echo", "Sunrise", "Someone Else")


def test_deezer_query_cleaning_strips_tails_that_break_search():
    from src.preview import _clean_title
    assert _clean_title("Você e Eu (You and Me)") == "Você e Eu"
    assert _clean_title("I've Got My Love - Remastered 1999") == "I've Got My Love"
    assert _clean_title("Plain Title") == "Plain Title"
