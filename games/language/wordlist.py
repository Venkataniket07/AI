"""
Word selection for Word Anagrams.

How hard an anagram is depends mostly on how well the player knows the word, so difficulty is a band
of word frequency (occurrences per million words) plus a word length, not just a length. The built-in
list lets the game work offline.
"""

import math
import random
from typing import Callable, Optional

from .wordlist_data import WORDS

# difficulty -> (shortest, longest, least frequent, most frequent). Higher = longer and rarer words.
BANDS: dict[int, tuple[int, int, float, float]] = {
    1: (4, 5, 30.0, float("inf")),
    2: (4, 6, 10.0, 60.0),
    3: (5, 6, 5.0, 30.0),
    4: (5, 7, 3.0, 15.0),
    5: (6, 7, 2.0, 10.0),
    6: (6, 8, 1.0, 5.0),
    7: (7, 8, 0.6, 3.0),
    8: (7, 9, 0.4, 2.0),
    9: (8, 10, 0.3, 1.5),
    10: (8, 10, 0.15, 1.0),
}
MAX_BAND = max(BANDS)
# Each game starts a little below the player's difficulty and ramps up to it.
RAMP = (-2, -1, 0, 0, 0)


def band_for(difficulty: int) -> tuple[int, int, float, float]:
    return BANDS[max(1, min(difficulty, MAX_BAND))]


def in_band(item: dict, difficulty: int) -> bool:
    lo_len, hi_len, lo_freq, hi_freq = band_for(difficulty)
    return lo_len <= len(item["word"]) <= hi_len and lo_freq <= item.get("freq", lo_freq) < hi_freq


def lengths_for(difficulty: int) -> list[int]:
    lo_len, hi_len, _, _ = band_for(difficulty)
    return list(range(lo_len, hi_len + 1))


def round_difficulties(difficulty: int, rounds: int) -> list[int]:
    """The difficulty of each round: easier first, reaching `difficulty` by the middle of the game."""
    ramp = list(RAMP[:rounds]) + [0] * max(0, rounds - len(RAMP))
    return [max(1, min(difficulty + step, MAX_BAND)) for step in ramp]


def offline_words(length: Optional[int] = None) -> list[dict]:
    """Built-in words (of exactly `length` letters if given), in the same shape the word service returns."""
    return [{"word": w, "freq": f, "clue": c} for w, f, c in WORDS if length is None or len(w) == length]


def pick_words(pool: list[dict], difficulty: int, rounds: int, rng: Optional[random.Random] = None) -> list[dict]:
    """
    One word per round from `pool`, matched to that round's difficulty. If a band has no unused word,
    the closest-frequency unused word of an allowed length is used so the game always has enough.
    """
    rng = rng or random.Random()
    used: set[str] = set()
    chosen = []
    for level in round_difficulties(difficulty, rounds):
        candidates = [w for w in pool if w["word"] not in used and in_band(w, level)]
        if not candidates:
            candidates = _nearest(pool, used, level)
        if not candidates:
            break
        pick = rng.choice(candidates)
        used.add(pick["word"])
        chosen.append(pick)
    return chosen


def _nearest(pool: list[dict], used: set, level: int) -> list[dict]:
    """Unused words closest to the band, preferring the right length."""
    lo_len, hi_len, lo_freq, hi_freq = band_for(level)
    target = lo_freq if hi_freq == float("inf") else (lo_freq * hi_freq) ** 0.5
    free = [w for w in pool if w["word"] not in used]
    right_length = [w for w in free if lo_len <= len(w["word"]) <= hi_len] or free
    right_length.sort(key=lambda w: abs(_log(w.get("freq", target)) - _log(target)))
    return right_length[:5]


def _log(x: float) -> float:
    return math.log10(max(x, 1e-6))


def is_valid_anagram(guess: str, word: str, known: Callable[[str], bool]) -> bool:
    """
    True if `guess` uses exactly the letters of `word` and is a real word. Any real word counts
    (`art`/`rat`/`tar` style alternatives), not only the one the game picked.
    """
    if guess == word:
        return True
    if len(guess) != len(word) or sorted(guess) != sorted(word):
        return False
    return known(guess)
