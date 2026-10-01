"""Family-tree model and relation derivation for Blood Relations (pure: no I/O, no game wiring).

A `Family` is people, a child -> parents map and spouse pairs. `relation` names what one person is to
another from a table of rules. `Fact` is one printable statement ("A is B's brother."); `answers_unique`
checks that a set of facts pins the relation down whatever the unstated genders turn out to be.
"""

import random
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable, Literal, Mapping, Sequence

MAX_ENUM_PEOPLE = 7  # answers_unique enumerates 2**unknown genders; more named people is refused
MAX_CHILDREN = 3
_LETTERS = "ABCDEFGHIJKL"


@dataclass(frozen=True)
class Person:
    name: str
    gender: Literal["M", "F"]


class Family:
    def __init__(
        self,
        people: Iterable[Person],
        parents: Mapping[str, Sequence[str]],
        spouses: Iterable[tuple[str, str]] = (),
    ):
        self._people = {p.name: p for p in people}
        self._parents = {child: tuple(ps) for child, ps in parents.items()}
        self._spouse: dict[str, str] = {}
        for a, b in spouses:
            self._spouse[a] = b
            self._spouse[b] = a
        self._children: dict[str, list[str]] = defaultdict(list)
        for child, ps in self._parents.items():
            for p in ps:
                self._children[p].append(child)

    @property
    def people(self) -> list[Person]:
        return list(self._people.values())

    @property
    def names(self) -> list[str]:
        """People that can be asked about (hidden placeholder parents start with '_')."""
        return [n for n in self._people if not n.startswith("_")]

    def gender(self, name: str) -> str:
        return self._people[name].gender

    def parents_of(self, name: str) -> tuple[str, ...]:
        return self._parents.get(name, ())

    def children_of(self, name: str) -> list[str]:
        return list(self._children.get(name, ()))

    def spouse_of(self, name: str) -> str | None:
        return self._spouse.get(name)

    def spouse_pairs(self) -> list[tuple[str, str]]:
        return sorted({tuple(sorted((a, b))) for a, b in self._spouse.items()})

    def siblings_of(self, name: str) -> list[str]:
        """People sharing at least one parent with `name`."""
        mine = set(self.parents_of(name))
        if not mine:
            return []
        return [n for n in self._people if n != name and mine & set(self.parents_of(n))]

    def generations(self) -> int:
        """Length of the longest line of descent, counting the oldest ancestor."""
        memo: dict[str, int] = {}

        def depth(n: str) -> int:
            if n not in memo:
                memo[n] = 1 + max((depth(p) for p in self.parents_of(n)), default=0)
            return memo[n]

        return max((depth(n) for n in self._people), default=0)

    def validate(self) -> None:
        """Raise ValueError unless the tree is well-formed."""
        for child, ps in self._parents.items():
            if child not in self._people or any(p not in self._people for p in ps):
                raise ValueError(f"unknown person in parents of {child}")
            if len(ps) > 2 or len(set(ps)) != len(ps):
                raise ValueError(f"{child} has invalid parents {ps}")
        for a, b in self._spouse.items():
            if self._spouse.get(b) != a or self.gender(a) == self.gender(b):
                raise ValueError(f"invalid marriage {a}-{b}")
        state: dict[str, int] = {}

        def visit(n: str) -> None:
            if state.get(n) == 1:
                raise ValueError(f"cycle through {n}")
            if state.get(n) == 2:
                return
            state[n] = 1
            for p in self.parents_of(n):
                visit(p)
            state[n] = 2

        for n in self._people:
            visit(n)


# ---- relation rules -------------------------------------------------------------------------


def _parents_of_all(f: Family, names: Iterable[str]) -> set[str]:
    return {p for n in names for p in f.parents_of(n)}


def _is_parent(f, a, b):
    return a in f.parents_of(b)


def _is_child(f, a, b):
    return b in f.parents_of(a)


def _is_sibling(f, a, b):
    return a in f.siblings_of(b)


def _is_spouse(f, a, b):
    return f.spouse_of(b) == a


def _is_grandparent(f, a, b):
    return a in _parents_of_all(f, f.parents_of(b))


def _is_grandchild(f, a, b):
    return b in _parents_of_all(f, f.parents_of(a))


def _uncle_like(f, a, b):
    """a is a sibling of one of b's parents, or married to one."""
    aunts_uncles = {s for p in f.parents_of(b) for s in f.siblings_of(p)}
    return a in aunts_uncles or f.spouse_of(a) in aunts_uncles


def _nephew_like(f, a, b):
    return _uncle_like(f, b, a)


def _is_cousin(f, a, b):
    return any(pb in f.siblings_of(pa) for pa in f.parents_of(a) for pb in f.parents_of(b))


def _sibling_in_law(f, a, b):
    """a is the spouse's sibling, or the spouse of b's sibling."""
    spouse = f.spouse_of(b)
    if spouse is not None and a in f.siblings_of(spouse):
        return True
    return any(f.spouse_of(s) == a for s in f.siblings_of(b))


def _parent_in_law(f, a, b):
    spouse = f.spouse_of(b)
    return spouse is not None and a in f.parents_of(spouse)


def _child_in_law(f, a, b):
    spouse = f.spouse_of(a)
    return spouse is not None and b in f.parents_of(spouse)


@dataclass(frozen=True)
class Rule:
    male: str
    female: str
    holds: Callable[[Family, str, str], bool]  # holds(f, a, b): a is <term> to b

    def term(self, gender: str) -> str:
        return self.male if gender == "M" else self.female


# Checked in order; the first rule that holds names the relation.
RELATION_RULES: dict[str, Rule] = {
    "parent": Rule("Father", "Mother", _is_parent),
    "child": Rule("Son", "Daughter", _is_child),
    "sibling": Rule("Brother", "Sister", _is_sibling),
    "spouse": Rule("Husband", "Wife", _is_spouse),
    "grandparent": Rule("Grandfather", "Grandmother", _is_grandparent),
    "grandchild": Rule("Grandson", "Granddaughter", _is_grandchild),
    "uncle": Rule("Uncle", "Aunt", _uncle_like),
    "nephew": Rule("Nephew", "Niece", _nephew_like),
    "cousin": Rule("Cousin", "Cousin", _is_cousin),
    "sibling_in_law": Rule("Brother-in-law", "Sister-in-law", _sibling_in_law),
    "parent_in_law": Rule("Father-in-law", "Mother-in-law", _parent_in_law),
    "child_in_law": Rule("Son-in-law", "Daughter-in-law", _child_in_law),
}

VOCABULARY = tuple(t for r in RELATION_RULES.values() for t in dict.fromkeys((r.male, r.female)))


def relation(family: Family, a: str, b: str) -> str | None:
    """What `a` is to `b` ("Uncle" means a is b's uncle); None if outside the vocabulary."""
    if a == b:
        return None
    for rule in RELATION_RULES.values():
        if rule.holds(family, a, b):
            return rule.term(family.gender(a))
    return None


# ---- random families ------------------------------------------------------------------------


def random_family(rng: random.Random, generations: int, people: int) -> Family:
    """A family with exactly `people` members across `generations` generations.

    Built as a founding couple, a line of descent that reaches the last generation (each member of
    it marrying in a spouse), then random extra children and married-in spouses.
    """
    min_people = 2 * generations - 1
    if generations < 2 or people < min_people or people > len(_LETTERS):
        raise ValueError(f"cannot build {people} people over {generations} generations")
    labels = list(_LETTERS[:people])
    rng.shuffle(labels)
    gender: dict[str, str] = {}
    gen: dict[str, int] = {}
    parents: dict[str, tuple[str, ...]] = {}
    couples: list[tuple[str, str]] = []

    def add(g: int, sex: str, ps: tuple[str, ...] = ()) -> str:
        name = labels.pop()
        gender[name], gen[name] = sex, g
        if ps:
            parents[name] = ps
        return name

    def marry(name: str) -> str:
        spouse = add(gen[name], "F" if gender[name] == "M" else "M")
        couples.append((name, spouse) if gender[name] == "M" else (spouse, name))
        return spouse

    def child_of(couple: tuple[str, str]) -> str:
        return add(gen[couple[0]] + 1, rng.choice("MF"), couple)

    father = add(0, "M")
    mother = add(0, "F")
    couples.append((father, mother))
    line = child_of(couples[0])
    for _ in range(generations - 2):
        marry(line)
        line = child_of(couples[-1])

    married = {n for c in couples for n in c}
    while labels:
        options: list[tuple[str, str | tuple[str, str]]] = [
            ("child", c)
            for c in couples
            if gen[c[0]] <= generations - 2 and sum(1 for p in parents.values() if p == c) < MAX_CHILDREN
        ]
        options += [("spouse", n) for n in gender if n not in married and gen[n] >= 1]
        if not options:
            raise ValueError("no room for more people")
        kind, target = rng.choice(options)
        if kind == "child":
            child_of(target)
        else:
            married |= {target, marry(target)}

    return Family(
        [Person(n, gender[n]) for n in sorted(gender)],
        parents,
        [tuple(c) for c in couples],
    )


# ---- facts, closed-world derivation, uniqueness --------------------------------------------

_GENDER_OF = {
    "father": "M", "husband": "M", "brother": "M", "son": "M", "man": "M",
    "mother": "F", "wife": "F", "sister": "F", "daughter": "F", "woman": "F",
}  # fmt: skip


@dataclass(frozen=True)
class Fact:
    """`x is y's <kind>` (kind names x), or `x is a man/woman` when kind is a gender word."""

    kind: str
    x: str
    y: str | None = None

    def __str__(self) -> str:
        if self.y is None:
            return f"{self.x} is a {self.kind}."
        return f"{self.x} is {self.y}'s {self.kind}."


@dataclass(frozen=True)
class _Structure:
    named: frozenset[str]
    fixed: dict[str, str]
    parents: dict[str, tuple[str, ...]]
    spouses: list[tuple[str, str]]
    hidden: dict[str, str]


def _structure(facts: Sequence[Fact]) -> _Structure | None:
    """Read the facts as the whole family (nothing else is related); None if they contradict.

    Siblings with no stated parents get a hidden married couple as parents.
    """
    named: set[str] = set()
    fixed: dict[str, str] = {}
    parents: dict[str, list[str]] = defaultdict(list)
    marriages: list[tuple[str, str]] = []
    uf: dict[str, str] = {}

    def find(n: str) -> str:
        uf.setdefault(n, n)
        while uf[n] != n:
            uf[n] = uf[uf[n]]
            n = uf[n]
        return n

    def add_parent(child: str, parent: str) -> None:
        if parent not in parents[child]:
            parents[child].append(parent)

    for f in facts:
        named.add(f.x)
        if f.y is not None:
            named.add(f.y)
        if fixed.setdefault(f.x, _GENDER_OF[f.kind]) != _GENDER_OF[f.kind]:
            return None
        if f.kind in ("father", "mother"):
            add_parent(f.y, f.x)
        elif f.kind in ("son", "daughter"):
            add_parent(f.x, f.y)
        elif f.kind in ("husband", "wife"):
            marriages.append((f.x, f.y))
        elif f.kind in ("brother", "sister"):
            uf[find(f.x)] = find(f.y)

    groups: dict[str, list[str]] = defaultdict(list)
    for n in list(uf):
        groups[find(n)].append(n)
    hidden: dict[str, str] = {}
    for i, members in enumerate(sorted(groups.values())):
        shared = list(dict.fromkeys(p for m in members for p in parents.get(m, ())))
        if not shared:
            h1, h2 = f"_h{i}a", f"_h{i}b"
            hidden[h1], hidden[h2] = "M", "F"
            marriages.append((h1, h2))
            shared = [h1, h2]
        for m in members:
            parents[m] = list(shared)

    for ps in list(parents.values()):
        if len(ps) > 2:
            return None
        if len(ps) == 2:
            marriages.append((ps[0], ps[1]))
    partners: dict[str, str] = {}
    pairs: dict[frozenset[str], tuple[str, str]] = {}
    for a, b in marriages:
        if partners.setdefault(a, b) != b or partners.setdefault(b, a) != a:
            return None
        pairs[frozenset((a, b))] = (a, b)
    return _Structure(
        frozenset(named),
        fixed,
        {c: tuple(ps) for c, ps in parents.items()},
        list(pairs.values()),
        hidden,
    )


def _outcomes(facts: Sequence[Fact], a: str, b: str) -> set[str | None]:
    """Relation of a to b in every family the facts allow; empty if they are inconsistent."""
    s = _structure(facts)
    if s is None or a not in s.named or b not in s.named:
        return set()
    if len(s.named) > MAX_ENUM_PEOPLE:
        raise ValueError(f"{len(s.named)} named people; at most {MAX_ENUM_PEOPLE} are enumerated")
    free = sorted(s.named - s.fixed.keys())
    outcomes: set[str | None] = set()
    for combo in product("MF", repeat=len(free)):
        genders = {**s.hidden, **s.fixed, **dict(zip(free, combo))}
        if any(genders[x] == genders[y] for x, y in s.spouses):
            continue
        fam = Family([Person(n, g) for n, g in genders.items()], s.parents, s.spouses)
        outcomes.add(relation(fam, a, b))
    return outcomes


def answers_unique(statements: Sequence[Fact], a: str, b: str) -> bool:
    """True if what `a` is to `b` is the same in every family the statements allow.

    Genders not stated are tried both ways, so a missing gender clue (the parent in an
    Uncle/Aunt question) makes this False.
    """
    outcomes = _outcomes(statements, a, b)
    return len(outcomes) == 1 and None not in outcomes


# ---- describing a family --------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    facts: tuple[Fact, ...]
    lines: tuple[str, ...]
    a: str  # the question asks what `a` is to `b`
    b: str
    answer: str


def _edges(f: Family) -> list[tuple[str, str, str]]:
    edges = [("parent", p, c) for c in f.names for p in f.parents_of(c)]
    edges += [("sibling", x, y) for x in f.names for y in f.siblings_of(x) if x < y]
    edges += [("spouse", x, y) for x, y in f.spouse_pairs()]
    return edges


def _edge_fact(f: Family, rng: random.Random, edge: tuple[str, str, str], style: str) -> Fact:
    kind, u, v = edge
    flip = style == "mixed" and rng.random() < 0.5
    if kind == "parent":
        if flip:
            return Fact("son" if f.gender(v) == "M" else "daughter", v, u)
        return Fact("father" if f.gender(u) == "M" else "mother", u, v)
    x, y = (v, u) if flip else (u, v)
    if kind == "sibling":
        return Fact("brother" if f.gender(x) == "M" else "sister", x, y)
    return Fact("husband" if f.gender(x) == "M" else "wife", x, y)


def _shortest_path(adj: dict[str, list[tuple[str, tuple[str, str, str]]]], a: str, b: str):
    prev: dict[str, tuple[str, tuple[str, str, str]] | None] = {a: None}
    queue = deque([a])
    while queue:
        n = queue.popleft()
        for m, edge in adj[n]:
            if m not in prev:
                prev[m] = (n, edge)
                queue.append(m)
    path = []
    while prev.get(b):
        b, edge = prev[b][0], prev[b][1]
        path.append(edge)
    return path[::-1]


def pose(family: Family, rng: random.Random, hops: int, style: str = "mixed") -> Scenario:
    """Pick two people `hops` family links apart and state just enough facts to fix their relation.

    The facts follow a shortest chain of links from one to the other; gender statements and, if the
    chain alone misreads the family, extra links are added until the answer is unique and right.
    `style` is "direct" (each link worded as walked) or "mixed" (either direction).
    """
    adj: dict[str, list[tuple[str, tuple[str, str, str]]]] = {n: [] for n in family.names}
    edges = _edges(family)
    for e in edges:
        adj[e[1]].append((e[2], e))
        adj[e[2]].append((e[1], e))
    for lst in adj.values():
        rng.shuffle(lst)
    pairs = [
        (a, b)
        for a in family.names
        for b in family.names
        if a != b and relation(family, a, b) and len(_shortest_path(adj, a, b)) == hops
    ]
    if not pairs:
        raise ValueError(f"no pair of people is {hops} links apart")
    a, b = rng.choice(pairs)
    truth = relation(family, a, b)
    path = _shortest_path(adj, a, b)
    facts = [_edge_fact(family, rng, e, style) for e in path]
    spare = [e for e in edges if e not in path]
    rng.shuffle(spare)

    for _ in range(len(edges) + family.generations() + len(family.names) + 1):
        outcomes = _outcomes(facts, a, b)
        if outcomes == {truth}:
            break
        s = _structure(facts)
        unknown = sorted(s.named - s.fixed.keys()) if s else []
        if truth in outcomes and len(outcomes) > 1 and unknown:
            helpful = [
                f
                for n in unknown
                for f in [Fact("man" if family.gender(n) == "M" else "woman", n)]
                if _outcomes(facts + [f], a, b) == {truth}
            ]
            n = rng.choice(unknown)
            facts.append(helpful[0] if helpful else Fact("man" if family.gender(n) == "M" else "woman", n))
        elif spare:
            facts.append(_edge_fact(family, rng, spare.pop(), style))
        else:
            raise RuntimeError("could not make the answer unique")
    else:
        raise RuntimeError("could not make the answer unique")
    return Scenario(tuple(facts), tuple(str(f) for f in facts), a, b, truth)


def describe(family: Family, rng: random.Random, hops: int, style: str = "mixed") -> list[str]:
    """Statements about two people `hops` links apart; see `pose` for the question they settle."""
    return list(pose(family, rng, hops, style).lines)
