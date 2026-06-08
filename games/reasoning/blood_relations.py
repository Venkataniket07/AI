import random
from core.profile_manager import ProfileManager
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

def play_blood_relations(profile: ProfileManager):
    print("\n================ BLOOD RELATIONS ================")
    print("Deduce the family relationship based on the clues.")
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
        
        tracker.start_trial()
        
        user_ans = input("> ").strip().lower()
        is_correct = (user_ans.replace('-', '') == ans.lower().replace('-', ''))
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 25
        else:
            print(f"Incorrect. The correct answer was: {ans}")
            
    print(f"\nScore: {score}")
    profile.save_game_result("blood_relations", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
