import random
import re

from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

# Template-based generation for simplicity and perfect solvability
TEMPLATES = [
    {
        "setup": "{P1} is {P2}'s brother. {P2} is {P3}'s mother. {P4} is {P3}'s father.",
        "questions": [
            ("Who is {P1} to {P4}?", "Brother-in-law"),
            ("Who is {P4} to {P1}?", "Brother-in-law"),
            ("Who is {P1} to {P3}?", "Uncle")
        ]
    },
    {
        "setup": "{P1} is the son of {P2}. {P3}, {P2}'s sister, has a son {P4} and a daughter {P5}.",
        "questions": [
            ("How is {P1} related to {P4}?", "Cousin"),
            ("How is {P3} related to {P1}?", "Aunt"),
            ("How is {P5} related to {P2}?", "Niece")
        ]
    },
    {
        "setup": "Pointing to {P1}, {P2} said, 'He is the son of my father's only son.'",
        "questions": [
            ("How is {P1} related to {P2}?", "Son"),
            ("How is {P2} related to {P1}?", "Father")
        ]
    }
]

# Answers are compared after normalising (lowercase, letters only). Accepted variants per answer:
ALIASES = {
    "brotherinlaw": set(),
    "uncle": {"maternaluncle", "paternaluncle"},
    "aunt": {"auntie", "maternalaunt", "paternalaunt"},
    "cousin": {"cousinbrother", "cousinsister", "firstcousin"},
    "niece": set(),
    "son": set(),
    "father": {"dad"},
}

# Other relation words a player might type. If the input is one of these (and not an accepted
# variant of the right answer) it is a different relation and is never sent to the AI.
OTHER_RELATIONS = {
    "brother", "sister", "mother", "mom", "daughter", "nephew", "grandfather", "grandmother",
    "grandson", "granddaughter", "husband", "wife", "sisterinlaw", "fatherinlaw", "motherinlaw",
    "soninlaw", "daughterinlaw", "stepfather", "stepmother", "stepson", "stepdaughter", "parent",
    "child", "sibling",
}
KNOWN_RELATIONS = set(ALIASES) | {a for v in ALIASES.values() for a in v} | OTHER_RELATIONS


def normalize(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def is_correct_relation(user_ans: str, target: str, db=None, ask_ai=None) -> bool:
    """
    Exact / known-variant match first. Only unrecognised phrasings (e.g. "mother's brother") are
    passed to the AI equivalence check, and only when AI is enabled.
    """
    got, want = normalize(user_ans), normalize(target)
    if not got:
        return False
    if got == want or got in ALIASES.get(want, set()):
        return True
    if got in KNOWN_RELATIONS:
        return False  # a recognised but different relation
    if ask_ai is None:
        ask_ai = _ask_ai
    return ask_ai(target, user_ans, db)


def _ask_ai(target: str, user_ans: str, db) -> bool:
    from games.assist import _ai_enabled
    if not _ai_enabled():
        return False
    try:
        from ai.background import result_or_none, submit
        from ai.services.assist_service import semantically_equivalent
        print("Checking your answer...")
        return bool(result_or_none(
            submit(semantically_equivalent, target, user_ans, "blood_relations", db), timeout=8.0
        ))
    except Exception:
        return False


def play_blood_relations(profile: ProfileManager):
    print("\n================ BLOOD RELATIONS ================")
    print("Deduce the family relationship based on the clues.")
    print(HINT_TIP)
    input("Press Enter to start...")

    tracker = PerformanceTracker()
    score = 0
    rounds = 4
    names = ["A", "B", "C", "D", "E"]

    for r in range(1, rounds + 1):
        random.shuffle(names)
        template = random.choice(TEMPLATES)

        setup = template["setup"].format(P1=names[0], P2=names[1], P3=names[2], P4=names[3], P5=names[4])
        q_raw, ans = random.choice(template["questions"])
        q = q_raw.format(P1=names[0], P2=names[1], P3=names[2], P4=names[3], P5=names[4])

        print(f"\nRound {r}/{rounds}:")
        print(setup)
        print(f"Question: {q}")
        print("(Options: Uncle, Aunt, Cousin, Niece, Nephew, Son, Father, Brother-in-law, etc.)")

        helper = RoundHelper(
            "blood_relations", f"{setup} {q}", ans, profile.db,
            static_hints=[
                "Sketch a small family tree from the statements.",
                "Work out each person's generation and gender before naming the relation.",
                f"The relationship starts with the letter '{ans[0]}'.",
            ],
            ai_hints=True,
        )
        tracker.start_trial()

        user_ans = helper.ask("> ")
        is_correct = is_correct_relation(user_ans, ans, profile.db)

        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += helper.points(25)
        else:
            print(f"Incorrect. The correct answer was: {ans}")
            helper.offer_explanation(user_ans)

    print(f"\nScore: {score}")
    finish_game(profile, "blood_relations", score, tracker, "Press Enter to return...")
