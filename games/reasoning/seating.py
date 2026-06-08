import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def generate_seating_puzzle(is_circular=False):
    items = ["A", "B", "C", "D", "E"]
    if is_circular:
        items.append("F")
        
    random.shuffle(items)
    clues = []
    
    if not is_circular: # Linear
        for i in range(len(items) - 1):
            clues.append(f"{items[i]} sits immediately left of {items[i+1]}.")
        clues.append(f"{items[0]} sits at the extreme left end.")
    else: # Circular
        for i in range(len(items)):
            nxt = (i + 1) % len(items)
            clues.append(f"{items[i]} sits immediately to the left of {items[nxt]}.")
        
        # Add opposite clues for even length
        for i in range(len(items) // 2):
            opp = (i + len(items)//2) % len(items)
            clues.append(f"{items[i]} sits opposite to {items[opp]}.")
            
    random.shuffle(clues)
    return clues[:4], "".join(items)

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
    
    for r in range(1, rounds + 1):
        clues, ans = generate_seating_puzzle(is_circular)
        
        print(f"\nRound {r}/{rounds}:")
        print("Clues:")
        for c in clues:
            print(f"- {c}")
            
        tracker.start_trial()
        
        user_ans = input("\nEnter arrangement: ").strip().upper()
        
        # Verify circular correctness
        is_correct = False
        if is_circular and len(user_ans) == 6:
            # Check if it's a valid cyclic permutation
            if user_ans in ans * 2:
                is_correct = True
        elif not is_circular and user_ans == ans:
            is_correct = True
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 33
        else:
            print(f"Incorrect. A valid arrangement was: {ans}")
            
    print(f"\nScore: {score}")
    profile.save_game_result("circular_seating" if is_circular else "linear_seating", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")

def play_linear_seating(profile: ProfileManager):
    play_seating(profile, is_circular=False)

def play_circular_seating(profile: ProfileManager):
    play_seating(profile, is_circular=True)
