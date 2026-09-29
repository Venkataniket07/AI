import random
from itertools import permutations
from core.profile_manager import ProfileManager
from games.common import finish_game
from utils.logger import get_app_logger
from utils.performance_tracker import PerformanceTracker

_FIRST_ROUND_WAIT = 4.0  # seconds to wait for the themed version of the first puzzle


def _clue_text(clue) -> str:
    kind, x, y = clue
    return {
        "left_of": f"{x} sits immediately left of {y}.",
        "left_end": f"{x} sits at the extreme left end.",
        "right_end": f"{x} sits at the extreme right end.",
        "opposite": f"{x} sits opposite to {y}.",
    }[kind]


def _satisfies(arrangement: str, clue, is_circular: bool) -> bool:
    kind, x, y = clue
    n = len(arrangement)
    i = arrangement.index(x)
    if kind == "left_end":
        return i == 0
    if kind == "right_end":
        return i == n - 1
    j = arrangement.index(y)
    if kind == "opposite":
        return (i - j) % n == n // 2
    if is_circular:
        return (i + 1) % n == j
    return i + 1 == j


def _count_solutions(items: list[str], clues: list, is_circular: bool) -> int:
    # Circular tables: fix the first person's seat so rotations count as one arrangement.
    first, rest = items[0], items[1:]
    perms = ((first,) + p for p in permutations(rest)) if is_circular else permutations(items)
    return sum(1 for p in perms if all(_satisfies("".join(p), c, is_circular) for c in clues))


def generate_seating_puzzle(is_circular=False):
    """Returns (clue_texts, clue_tuples, canonical_answer); the clues have exactly one solution."""
    items = ["A", "B", "C", "D", "E"]
    if is_circular:
        items.append("F")
    random.shuffle(items)
    n = len(items)

    if is_circular:
        pool = [("left_of", items[i], items[(i + 1) % n]) for i in range(n)]
        pool += [("opposite", items[i], items[i + n // 2]) for i in range(n // 2)]
    else:
        pool = [("left_of", items[i], items[i + 1]) for i in range(n - 1)]
        pool += [("left_end", items[0], None), ("right_end", items[-1], None)]

    random.shuffle(pool)
    clues = []
    for clue in pool:
        clues.append(clue)
        if _count_solutions(items, clues, is_circular) == 1:
            break
    random.shuffle(clues)
    return [_clue_text(c) for c in clues], clues, "".join(items)


def _is_valid_answer(user_ans: str, clues: list, is_circular: bool) -> bool:
    expected = 6 if is_circular else 5
    letters = "ABCDEF"[:expected]
    if len(user_ans) != expected or sorted(user_ans) != list(letters):
        return False
    return all(_satisfies(user_ans, c, is_circular) for c in clues)


def _start_theme_wrap(clues: list[str], db_manager):
    """Kick off AI theme wrapping in the background; returns a Future (or None if unavailable)."""
    try:
        from ai.background import submit
        from ai.services.theme_service import wrap_puzzle_in_theme
        return submit(wrap_puzzle_in_theme, clues, db_manager=db_manager)
    except Exception:
        get_app_logger().warning("Could not start AI theme wrap; showing raw clues.", exc_info=True)
        return None


def _new_round(is_circular: bool, db_manager) -> dict:
    """Generate a puzzle and start wrapping it in a theme while the player is busy."""
    clues, clue_defs, ans = generate_seating_puzzle(is_circular)
    return {"clues": clues, "defs": clue_defs, "ans": ans,
            "themed": _start_theme_wrap(clues, db_manager)}


def _themed_view(rnd: dict, wait: float) -> tuple[str | None, list[str]]:
    """Return (scenario, clues) for display, using the themed version only if it is ready in time."""
    from ai.background import result_or_none
    themed = result_or_none(rnd["themed"], timeout=wait)
    if themed and len(themed.clues) == len(rnd["clues"]):
        return themed.scenario, themed.clues
    return None, rnd["clues"]


def play_seating(profile: ProfileManager, is_circular: bool = False):
    print("\n================ SEATING ARRANGEMENTS ================")

    if is_circular:
        print("Advanced Circular Seating: 6 friends sit around a circular table facing the center.")
        print("Example Answer (starting from any person and going clockwise): ABCDEF")
    else:
        print("Linear Seating: 5 friends sit in a row facing North.")
        print("Example Answer (Left to Right): ABCDE")

    input("Press Enter to start...")

    tracker = PerformanceTracker()
    score = 0
    rounds = 3

    current = _new_round(is_circular, profile.db)
    for r in range(1, rounds + 1):
        clue_defs, ans = current["defs"], current["ans"]

        # Theme wrap is fetched in the background: the first round waits briefly, later rounds
        # were requested during the previous round. Falls back to the raw clues if not ready.
        scenario, display_clues = _themed_view(current, wait=_FIRST_ROUND_WAIT if r == 1 else 0.5)
        if r < rounds:
            upcoming = _new_round(is_circular, profile.db)

        print(f"\nRound {r}/{rounds}:")
        if scenario:
            print(f"\n✨ {scenario}")
        print("Clues:")
        for c in display_clues:
            print(f"  - {c}")

        tracker.start_trial()

        user_ans = input("\nEnter arrangement: ").strip().upper()

        is_correct = _is_valid_answer(user_ans, clue_defs, is_circular)

        tracker.end_trial(is_correct)
        if is_correct:
            print("✅ Correct!")
            score += 33
        else:
            print(f"❌ Incorrect. The arrangement was: {ans}")

        if r < rounds:
            current = upcoming

    print(f"\nScore: {score}")
    finish_game(profile, "circular_seating" if is_circular else "linear_seating", score, tracker)


def play_linear_seating(profile: ProfileManager):
    play_seating(profile, is_circular=False)


def play_circular_seating(profile: ProfileManager):
    play_seating(profile, is_circular=True)
