import random
from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

# Templates for basic syllogism logic
TEMPLATES = [
    {
        "statements": ["All {A} are {B}.", "All {B} are {C}."],
        "conclusions": [
            ("All {A} are {C}.", True),
            ("Some {A} are {C}.", True),
            ("No {A} are {C}.", False),
            ("Some {C} are not {A}.", "Cannot be determined")
        ]
    },
    {
        "statements": ["All {A} are {B}.", "Some {B} are {C}."],
        "conclusions": [
            ("Some {A} are {C}.", "Cannot be determined"),
            ("All {A} are {C}.", "Cannot be determined"),
            ("Some {B} are {A}.", True)
        ]
    },
    {
        "statements": ["Some {A} are {B}.", "No {B} are {C}."],
        "conclusions": [
            ("Some {A} are not {C}.", True),
            ("No {A} are {C}.", "Cannot be determined"),
            ("All {A} are {C}.", False)
        ]
    }
]

ENTITIES = ["cats", "dogs", "pets", "animals", "birds", "cars", "trees", "phones"]

def play_syllogisms(profile: ProfileManager):
    print("\n================ SYLLOGISMS ================")
    print("Evaluate the conclusion based ONLY on the statements.")
    print(HINT_TIP)
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score = 0
    rounds = 4
    
    for r in range(1, rounds + 1):
        template = random.choice(TEMPLATES)
        ents = random.sample(ENTITIES, 3)
        
        statements = [s.format(A=ents[0], B=ents[1], C=ents[2]) for s in template["statements"]]
        conc_raw, truth_val = random.choice(template["conclusions"])
        conclusion = conc_raw.format(A=ents[0], B=ents[1], C=ents[2])
        
        print(f"\nRound {r}/{rounds}:")
        print("Statements:")
        for s in statements:
            print(f"- {s}")
            
        print(f"\nConclusion: {conclusion}")
        print("1. True\n2. False\n3. Cannot be determined")

        if str(truth_val) == "True": ans_str, verdict = "1", "definitely follows from the statements"
        elif str(truth_val) == "False": ans_str, verdict = "2", "is contradicted by the statements"
        else: ans_str, verdict = "3", "neither follows from nor is contradicted by the statements"
        answer_label = {"1": "True", "2": "False", "3": "Cannot be determined"}[ans_str]

        helper = RoundHelper(
            "syllogisms",
            "Statements: " + " ".join(statements) + f" Conclusion: {conclusion} (True / False / Cannot be determined)",
            f"{answer_label} ({conclusion} {verdict})", profile.db,
            static_hints=[
                "Picture each group as a circle and draw how the statements make the circles overlap.",
                "Use ONLY what the statements force to be true, not what seems likely in real life.",
                f"The conclusion {verdict}.",
            ],
            ai_hints=True,
            forbidden=["cannot be determined", "is true", "is false", "answer is"],  # would give the verdict away
        )
        tracker.start_trial()

        user_ans = helper.ask("> ")
        is_correct = (user_ans == ans_str)

        tracker.end_trial(is_correct, min_plausible_ms=answer_floor_ms(ans_str, " ".join(statements) + conclusion))
        if is_correct:
            print("Correct!")
            score += helper.points(25)
        else:
            print(f"Incorrect. The correct answer was {ans_str} ({truth_val}).")
            helper.offer_explanation(user_ans)
            
    print(f"\nScore: {score}")
    finish_game(profile, "syllogisms", score, tracker, "Press Enter to return...")
