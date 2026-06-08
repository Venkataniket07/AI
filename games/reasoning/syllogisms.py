import random
from core.profile_manager import ProfileManager
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
        
        tracker.start_trial()
        
        user_ans = input("> ").strip()
        
        if str(truth_val) == "True": ans_str = "1"
        elif str(truth_val) == "False": ans_str = "2"
        else: ans_str = "3"
        
        is_correct = (user_ans == ans_str)
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 25
        else:
            print(f"Incorrect. The correct answer was {ans_str} ({truth_val}).")
            
    print(f"\nScore: {score}")
    profile.save_game_result("syllogisms", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
