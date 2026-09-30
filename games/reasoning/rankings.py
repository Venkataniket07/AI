import random
from itertools import permutations

from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game, letters_only
from utils.performance_tracker import PerformanceTracker


def _clue_text(clue) -> str:
    kind, x, y = clue
    return {
        "above": f"{x} ranks above {y}.",
        "top": f"{x} ranks at the top.",
        "bottom": f"{x} ranks at the bottom.",
    }[kind]


def _satisfies(order: str, clue) -> bool:
    kind, x, y = clue
    if kind == "top":
        return order[0] == x
    if kind == "bottom":
        return order[-1] == x
    return order.index(x) < order.index(y)


def _count_solutions(items: list[str], clues: list) -> int:
    return sum(1 for p in permutations(items) if all(_satisfies("".join(p), c) for c in clues))


def generate_ranking_puzzle():
    """Returns (clue_texts, answer); the clues have exactly one solution."""
    items = ["A", "B", "C", "D", "E"]
    random.shuffle(items)  # items[0] is the true top, items[-1] the true bottom

    pool = [("above", items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]
    pool += [("top", items[0], None), ("bottom", items[-1], None)]
    random.shuffle(pool)

    clues = []
    for clue in pool:
        clues.append(clue)
        if _count_solutions(items, clues) == 1:
            break
    for clue in list(clues):  # drop clues that the others already imply
        rest = [c for c in clues if c is not clue]
        if _count_solutions(items, rest) == 1:
            clues = rest
    random.shuffle(clues)
    return [_clue_text(c) for c in clues], "".join(items)


def play_rankings(profile: ProfileManager):
    print("\n================ RANKING PUZZLES ================")
    print("Arrange the items from highest to lowest rank based on the clues.")
    print("Example Answer: ABCDE")
    print(HINT_TIP)
    input("Press Enter to start...")

    tracker = PerformanceTracker()
    score = 0
    rounds = 4

    for r in range(1, rounds + 1):
        clues, ans = generate_ranking_puzzle()

        print(f"\nRound {r}/{rounds}:")
        print("Among A, B, C, D, E:")
        for c in clues:
            print(f"- {c}")

        helper = RoundHelper(
            "rankings", "Rank A-E from highest to lowest.\n" + "\n".join(clues), ans, profile.db,
            static_hints=[
                "Look for the clue that names the top or the bottom item, then build outwards.",
                f"The top-ranked item is {ans[0]}.",
                f"The top is {ans[0]} and the bottom is {ans[-1]}.",
            ],
            explanation=f"Chaining the clues gives {' > '.join(ans)}, so highest to lowest is {ans}.",
        )

        tracker.start_trial()

        user_ans = letters_only(helper.ask("\nArrange from highest to lowest: "))
        is_correct = (user_ans == ans)

        tracker.end_trial(is_correct, helper.hints_used, min_plausible_ms=answer_floor_ms(ans, " ".join(clues)))
        if is_correct:
            print("Correct!")
            score += helper.points(25)
        else:
            print(f"Incorrect. The correct arrangement was: {ans}")
            helper.offer_explanation(user_ans)

    print(f"\nScore: {score}")
    finish_game(profile, "rankings", score, tracker, "Press Enter to return...")
