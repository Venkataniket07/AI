"""One relation vocabulary for Blood Relations, derived from the family rule table, and answer matching words."""

import re

from games.reasoning.family import VOCABULARY


def normalize(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


# Accepted variants per answer, beyond the term itself (compared after normalising).
_EXTRA_ALIASES = {
    "uncle": {"maternaluncle"},
    "aunt": {"auntie", "maternalaunt", "paternalaunt"},
    "cousin": {"cousinbrother", "firstcousin"},
    "father": {"dad"},
    "mother": {"mom", "mum"},
}

# Relation words outside the rule table. A recognised but different relation is never sent to the AI.
OTHER_RELATIONS = {
    "parent", "child", "sibling", "stepfather", "stepmother", "stepson", "stepdaughter",
    "paternaluncle", "cousinsister",
}  # fmt: skip

ALIASES: dict[str, set[str]] = {normalize(t): set(_EXTRA_ALIASES.get(normalize(t), ())) for t in VOCABULARY}
KNOWN_RELATIONS = set(ALIASES) | {a for v in ALIASES.values() for a in v} | OTHER_RELATIONS

# What a player may type -> the vocabulary term it names.
TERM_OF = {normalize(t): t for t in VOCABULARY} | {a: t for t in VOCABULARY for a in ALIASES[normalize(t)]}


def aliases_of(term: str) -> tuple[str, ...]:
    return tuple(sorted(ALIASES.get(normalize(term), ())))
