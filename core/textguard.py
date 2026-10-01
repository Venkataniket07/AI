"""Pure text checks for AI-written text: answer leaks and themed-clue consistency.

Nothing here imports from ai/ or games/.
"""

import re
from typing import Iterable, Sequence

_LABEL_RE = re.compile(r"\b[A-F]\b")  # person labels A-F
_MIN_PHRASE_LEN = 4  # shorter answers are matched as whole tokens only
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _NON_ALNUM.split(text.lower()) if t]


def _term_leaks(text: str, term: str) -> bool:
    term_tokens = _tokens(term)
    if not term_tokens:
        return False
    if len("".join(term_tokens)) < _MIN_PHRASE_LEN:
        words, n = _tokens(text), len(term_tokens)
        return any(words[i : i + n] == term_tokens for i in range(len(words) - n + 1))
    # Characters in order with any separators between them, so "ABCDE" matches "A-B-C-D-E".
    pattern = "[^a-z0-9]*".join(re.escape(c) for c in "".join(term_tokens))
    return re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.lower()) is not None


def leaks(text: str, answer: str, forbidden: Iterable[str] = ()) -> bool:
    """True if `text` contains the answer or any forbidden phrase.

    Case-insensitive; punctuation and spacing are ignored, so "ABCDE" is caught as "A-B-C-D-E" and
    "12345" as "1, 2, 3, 4, 5". Terms under 4 characters match whole tokens only ("son" is not
    found in "person").

    NOT applied to AI explanations: those must state the answer.
    """
    return any(_term_leaks(text, term) for term in (answer, *forbidden))


def _labels(clue: str) -> list[str]:
    return _LABEL_RE.findall(clue)


def themed_consistent(original: Sequence[str], themed: Sequence[str]) -> bool:
    """
    Cheap guard against the model changing a puzzle's logic.

    Each themed clue must mention exactly the same person labels as its original. Unless "A" is a
    label in the original clue, the order must also match (this catches swapped "X left of Y" /
    "Y left of X" rewrites). "A" is ambiguous with the English article, so when it is a label only
    the set of labels is compared and a swap involving A is not detected.
    """
    if len(original) != len(themed):
        return False
    for orig, new in zip(original, themed):
        want, got = _labels(orig), _labels(new)
        if "A" in want:
            if set(want) != set(got):
                return False
        elif want != [g for g in got if g != "A"]:  # a stray "A" is the English article
            return False
    return True
