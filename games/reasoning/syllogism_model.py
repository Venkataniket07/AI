"""Set-model checker for syllogisms. Pure: no I/O, no randomness.

A model says which regions of a Venn diagram hold at least one thing. With n sets there are 2**n - 1 regions
that matter (the region outside every set never affects a statement, so it is left out). A region is a bitmask
over the sets: bit i set means "inside sets[i]". A model is a bitmask over regions: bit r set means region r is
occupied.

`verdict` is True when the conclusion holds in every model of the premises, False when its negation does, and
"Cannot be determined" otherwise.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

SETS_NONEMPTY = True  # every set in a model has at least one member

ALL, SOME, NO, SOME_NOT = "All", "Some", "No", "SomeNot"
KINDS = (ALL, SOME, NO, SOME_NOT)
TRUE, FALSE, CANNOT = "True", "False", "Cannot be determined"

_NEGATION = {ALL: SOME_NOT, SOME_NOT: ALL, SOME: NO, NO: SOME}


class UnsatisfiablePremises(ValueError):
    """No model satisfies the premises, so nothing can be concluded from them."""


@dataclass(frozen=True)
class Stmt:
    kind: str  # one of KINDS
    x: str
    y: str

    def negation(self) -> "Stmt":
        return Stmt(_NEGATION[self.kind], self.x, self.y)

    def restates(self, other: "Stmt") -> bool:
        """The same claim as `other`, allowing for "Some" and "No" being symmetric."""
        if self == other:
            return True
        return self.kind == other.kind and self.kind in (SOME, NO) and (self.x, self.y) == (other.y, other.x)


@dataclass(frozen=True)
class Model:
    sets: tuple[str, ...]
    regions: int  # bit r set: region r (a membership bitmask over `sets`) holds something

    def occupied(self) -> list[int]:
        return [r for r in range(1, 1 << len(self.sets)) if self.regions >> r & 1]


def sets_of(statements: Iterable[Stmt]) -> tuple[str, ...]:
    """Set names in order of first appearance."""
    names: dict[str, None] = {}
    for stmt in statements:
        names.setdefault(stmt.x)
        names.setdefault(stmt.y)
    return tuple(names)


@lru_cache(maxsize=None)
def _inside(n: int) -> tuple[int, ...]:
    """For each set i, the bitmask of regions inside it."""
    return tuple(sum(1 << r for r in range(1, 1 << n) if r >> i & 1) for i in range(n))


def _mask(stmt: Stmt, sets: Sequence[str]) -> int:
    """The regions that a statement is about: those whose occupation decides it."""
    inside = _inside(len(sets))
    x, y = inside[sets.index(stmt.x)], inside[sets.index(stmt.y)]
    return x & y if stmt.kind in (SOME, NO) else x & ~y


def _regions_ok(stmt: Stmt, regions: int, sets: Sequence[str]) -> bool:
    hit = regions & _mask(stmt, sets) != 0
    return hit if stmt.kind in (SOME, SOME_NOT) else not hit


def holds(stmt: Stmt, model: Model) -> bool:
    return _regions_ok(stmt, model.regions, model.sets)


@lru_cache(maxsize=512)
def _satisfying(premises: tuple[Stmt, ...], sets: tuple[str, ...], nonempty: bool) -> tuple[int, ...]:
    inside = _inside(len(sets))
    allowed = (1 << (1 << len(sets))) - 2  # every region except 0
    required = list(inside) if nonempty else []
    for stmt in premises:
        if stmt.kind in (ALL, NO):
            allowed &= ~_mask(stmt, sets)
        else:
            required.append(_mask(stmt, sets))
    found, sub = [], allowed
    while True:  # every subset of the allowed regions
        if all(sub & need for need in required):
            found.append(sub)
        if sub == 0:
            return tuple(found)
        sub = (sub - 1) & allowed


def models(premises: Sequence[Stmt], sets: Sequence[str] = (), nonempty: bool = SETS_NONEMPTY) -> list[Model]:
    """Every model of `premises` over `sets` (default: the sets the premises mention)."""
    names = tuple(sets) or sets_of(premises)
    return [Model(names, r) for r in _satisfying(tuple(premises), names, nonempty)]


def verdict(premises: Sequence[Stmt], conclusion: Stmt, nonempty: bool = SETS_NONEMPTY) -> str:
    """The verdict: "True", "False" or "Cannot be determined". Raises UnsatisfiablePremises if the premises cannot all hold."""
    names = sets_of((*premises, conclusion))
    regions = _satisfying(tuple(premises), names, nonempty)
    if not regions:
        raise UnsatisfiablePremises(f"no model satisfies {list(premises)}")
    holding = failing = False
    for r in regions:
        if _regions_ok(conclusion, r, names):
            holding = True
        else:
            failing = True
        if holding and failing:
            return CANNOT
    return TRUE if holding else FALSE


def witness(
    premises: Sequence[Stmt], conclusion: Stmt, nonempty: bool = SETS_NONEMPTY
) -> tuple[Model | None, Model | None]:
    """The smallest model of the premises where the conclusion holds, and the smallest where it fails (None if no such model)."""
    names = sets_of((*premises, conclusion))
    holding, failing = [], []
    for r in _satisfying(tuple(premises), names, nonempty):
        (holding if _regions_ok(conclusion, r, names) else failing).append(r)

    def smallest(regions: list[int]) -> Model | None:
        return Model(names, min(regions, key=lambda r: (bin(r).count("1"), r))) if regions else None

    return smallest(holding), smallest(failing)
