import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def play_puzzle_grid(profile: ProfileManager):
    print("\n================ PUZZLE GRID ================")
    print("Interactive Zebra-style puzzle.")
    
    persons = ["A", "B", "C"]
    colors = ["Red", "Blue", "Green"]
    pets = ["Dog", "Cat", "Fish"]
    
    # Generate random solved state
    random.shuffle(colors)
    random.shuffle(pets)
    
    solution = {}
    for i, p in enumerate(persons):
        solution[p] = {"Color": colors[i], "Pet": pets[i]}
        
    # Generate simple deterministic clues
    clues = [
        f"The {colors[0]} house owner has a {pets[0]}.",
        f"{persons[1]} lives in the {colors[1]} house.",
        f"The {pets[2]} owner is not {persons[0]}."
    ]
    random.shuffle(clues)
    
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
        
    profile.save_game_result("puzzle_grid", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
