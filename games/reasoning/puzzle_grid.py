import random
import re
from itertools import permutations

from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

PERSONS = ["A", "B", "C"]
COLORS = ["Red", "Blue", "Green"]
PETS = ["Dog", "Cat", "Fish"]


def _holds(clue, colors: dict, pets: dict) -> bool:
    """`colors` / `pets` map each person to their house colour / pet."""
    kind, x, y = clue
    if kind == "owner_has":  # the <x colour> house owner has a <y pet>
        return any(colors[p] == x and pets[p] == y for p in PERSONS)
    if kind == "lives_in":  # person x lives in the <y> house
        return colors[x] == y
    if kind == "owns":  # person x owns the <y>
        return pets[x] == y
    if kind == "not_pet":  # the <x pet> owner is not person y
        return pets[y] != x
    return colors[x] != y  # "not_color": person x does not live in the <y> house


def _clue_text(clue) -> str:
    kind, x, y = clue
    return {
        "owner_has": f"The {x} house owner has a {y}.",
        "lives_in": f"{x} lives in the {y} house.",
        "owns": f"{x} owns the {y}.",
        "not_pet": f"The {x} owner is not {y}.",
        "not_color": f"{x} does not live in the {y} house.",
    }[kind]


def _count_solutions(clues: list) -> int:
    count = 0
    for color_perm in permutations(COLORS):
        colors = dict(zip(PERSONS, color_perm))
        for pet_perm in permutations(PETS):
            pets = dict(zip(PERSONS, pet_perm))
            if all(_holds(c, colors, pets) for c in clues):
                count += 1
    return count


def generate_grid_puzzle():
    """Returns (solution, clue_texts); the clues have exactly one solution."""
    colors = random.sample(COLORS, 3)
    pets = random.sample(PETS, 3)
    solution = {p: {"Color": colors[i], "Pet": pets[i]} for i, p in enumerate(PERSONS)}
    color_of = {p: solution[p]["Color"] for p in PERSONS}
    pet_of = {p: solution[p]["Pet"] for p in PERSONS}

    pool = []
    for p in PERSONS:
        pool.append(("owner_has", color_of[p], pet_of[p]))
        pool.append(("lives_in", p, color_of[p]))
        pool.append(("owns", p, pet_of[p]))
        pool += [("not_pet", pet, p) for pet in PETS if pet != pet_of[p]]
        pool += [("not_color", p, color) for color in COLORS if color != color_of[p]]
    random.shuffle(pool)

    clues = []
    for clue in pool:
        clues.append(clue)
        if _count_solutions(clues) == 1:
            break
    for clue in list(clues):  # drop clues that the others already imply
        rest = [c for c in clues if c is not clue]
        if _count_solutions(rest) == 1:
            clues = rest
    random.shuffle(clues)
    return solution, [_clue_text(c) for c in clues]


_FILLER = {
    "the",
    "a",
    "an",
    "is",
    "has",
    "in",
    "house",
    "color",
    "colour",
    "pet",
    "lives",
    "owns",
    "owner",
    "of",
    "with",
}
_ATTRIBUTE_OF = {**{c.lower(): "Color" for c in COLORS}, **{p.lower(): "Pet" for p in PETS}}


def parse_assignment(text: str):
    """Reads e.g. 'A Color Red', 'a: red', 'B-Pet-Dog.' or 'C has the fish' into (person, attribute, value), else None."""
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens or tokens[0].upper() not in PERSONS:
        return None
    rest = [t for t in tokens[1:] if t not in _FILLER]
    if len(rest) != 1 or rest[0] not in _ATTRIBUTE_OF:
        return None
    return tokens[0].upper(), _ATTRIBUTE_OF[rest[0]], rest[0].capitalize()


def _round_helper(solution: dict, clues: list[str], db) -> RoundHelper:
    facts = []
    for p in PERSONS:
        facts.append(f"{p} lives in the {solution[p]['Color']} house.")
        facts.append(f"{p} owns the {solution[p]['Pet']}.")
    a, b, c = random.sample(PERSONS, 3)
    hints = [
        "Start with a clue that names both a person and a colour or pet, then rule the others out.",
        facts[2 * PERSONS.index(a)],
        f"{b} lives in the {solution[b]['Color']} house and owns the {solution[b]['Pet']}.",
    ]
    explanation = (
        "Each clue either fixes a person's colour or pet, or rules one out. Combining them leaves exactly one table: "
        + "; ".join(f"{p}: {solution[p]['Color']}, {solution[p]['Pet']}" for p in PERSONS)
        + "."
    )
    answer = " ".join(f"{p}{solution[p]['Color']}{solution[p]['Pet']}" for p in PERSONS)
    return RoundHelper("puzzle_grid", " ".join(clues), answer, db, static_hints=hints, explanation=explanation)


def play_puzzle_grid(profile: ProfileManager):
    print("\n================ PUZZLE GRID ================")
    print("Interactive Zebra-style puzzle.")
    print(HINT_TIP)

    persons = PERSONS
    solution, clues = generate_grid_puzzle()
    helper = _round_helper(solution, clues, profile.db)

    print("\nClues:")
    for i, c in enumerate(clues, 1):
        print(f"{i}. {c}")

    print("\nFill in the table gradually.")
    table = {p: {"Color": "?", "Pet": "?"} for p in persons}

    tracker = PerformanceTracker()
    tracker.start_trial()

    while True:
        print("\nCurrent Table:")
        print("Person   Color    Pet")
        for p in persons:
            print(f"{p:<8} {table[p]['Color']:<8} {table[p]['Pet']:<8}")

        print("\nType an entry such as 'A Color Red' or 'B Pet Dog', or '2' to submit your final answer.")
        print("(Typing '1' also works and asks for the entry on the next line.)")

        choice = helper.ask("> ")
        if not choice or choice.lower() in ("2", "submit", "done"):
            break
        text = choice
        if choice == "1":
            print("Enter format: Person Attribute Value (e.g. A Pet Dog)")
            text = helper.ask(">> ")
            if not text:
                break

        entry = parse_assignment(text)
        if entry is None:
            print("Didn't understand that. Try something like: A Color Red")
            continue
        p, attr, v = entry
        table[p][attr] = v

    is_correct = all(table[p] == solution[p] for p in persons)
    typed = "".join(f"{p}{solution[p]['Color']}{solution[p]['Pet']}" for p in persons)
    tracker.end_trial(is_correct, helper.hints_used, min_plausible_ms=answer_floor_ms(typed, " ".join(clues)))

    if is_correct:
        print("Correct! Excellent deduction.")
        score = helper.points(100)
    else:
        print("Incorrect. The actual table was:")
        print("Person   Color    Pet")
        for p in persons:
            print(f"{p:<8} {solution[p]['Color']:<8} {solution[p]['Pet']:<8}")
        score = 0
        helper.offer_explanation(" ".join(f"{p}:{table[p]['Color']}/{table[p]['Pet']}" for p in persons))

    finish_game(profile, "puzzle_grid", score, tracker, "Press Enter to return...")
