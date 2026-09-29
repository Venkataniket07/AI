import random
from itertools import permutations

from core.profile_manager import ProfileManager
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

PERSONS = ["A", "B", "C"]
COLORS = ["Red", "Blue", "Green"]
PETS = ["Dog", "Cat", "Fish"]


def _holds(clue, colors: dict, pets: dict) -> bool:
    """`colors` / `pets` map each person to their house colour / pet."""
    kind, x, y = clue
    if kind == "owner_has":      # the <x colour> house owner has a <y pet>
        return any(colors[p] == x and pets[p] == y for p in PERSONS)
    if kind == "lives_in":       # person x lives in the <y> house
        return colors[x] == y
    if kind == "owns":           # person x owns the <y>
        return pets[x] == y
    if kind == "not_pet":        # the <x pet> owner is not person y
        return pets[y] != x
    return colors[x] != y        # "not_color": person x does not live in the <y> house


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


def play_puzzle_grid(profile: ProfileManager):
    print("\n================ PUZZLE GRID ================")
    print("Interactive Zebra-style puzzle.")

    persons = PERSONS
    solution, clues = generate_grid_puzzle()


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
            
        print("\nChoose:")
        print("1. Set a value (e.g., A Color Red)")
        print("2. Submit final answer")
        
        choice = input("> ").strip().lower()
        
        if choice == '2':
            break
        elif choice.startswith('1'):
            print("Enter format: Person Attribute Value (e.g. A Pet Dog)")
            val = input(">> ").strip().split()
            if len(val) == 3:
                p, attr, v = val[0].upper(), val[1].capitalize(), val[2].capitalize()
                if p in persons and attr in ["Color", "Pet"]:
                    table[p][attr] = v
                    
    # Verification
    is_correct = True
    for p in persons:
        if table[p]["Color"] != solution[p]["Color"] or table[p]["Pet"] != solution[p]["Pet"]:
            is_correct = False
            
    tracker.end_trial(is_correct)
    
    if is_correct:
        print("Correct! Excellent deduction.")
        score = 100
    else:
        print("Incorrect. The actual table was:")
        print("Person   Color    Pet")
        for p in persons:
            print(f"{p:<8} {solution[p]['Color']:<8} {solution[p]['Pet']:<8}")
        score = 0
        
    finish_game(profile, "puzzle_grid", score, tracker, "Press Enter to return...")
