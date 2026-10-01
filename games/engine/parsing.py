"""Answer parsing shared by every game."""

import re
from typing import Optional


_INT_RE = re.compile(r"[+-]?\d+(\.0*)?")


def parse_int(text: str) -> Optional[int]:
    """A whole number typed the way people write one ("12", "+5", "1,024", "12.", "12.0"), else None."""
    t = text.strip().replace(",", "")
    if t.endswith(".") and len(t) > 1:
        t = t[:-1]
    if not _INT_RE.fullmatch(t):
        return None
    return int(t.split(".")[0])


def letters_only(text: str) -> str:
    """An arrangement typed as "ABCDE", "A B C D E", "A,B,C,D,E" or "A>B>C>D>E", as "ABCDE"."""
    return re.sub(r"[^A-Za-z]", "", text).upper()


def compact_answer(text: str) -> str:
    """Answer text without spaces, commas, dashes, dots and quote marks, in one case."""
    return re.sub(r"[\s,\-.'\"`]", "", text).upper()


def normalize_symbol(text: str) -> str:
    """Answer text without spaces and quote marks, in one case, so "'b 3'" matches "B3"."""
    return re.sub(r"[\s'\"`]", "", text).upper()
