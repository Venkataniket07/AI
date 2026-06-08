import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def generate_ranking_puzzle():
    items = ["A", "B", "C", "D", "E"]
    random.shuffle(items)
    
    # Generate true statements about the ordering
    clues = []
    # Guarantee solvability by providing full chain or exact absolute positions
    # We will build a set of relative constraints
    for i in range(len(items) - 1):
        clues.append(f"{items[i]} ranks above {items[i+1]}.")
        
    # Maybe add an absolute clue
    clues.append(f"{items[-1]} ranks at the bottom.")
    clues.append(f"{items[0]} ranks at the top.")
    
    random.shuffle(clues)
    return clues[:4], "".join(items)

def play_rankings(profile: ProfileManager):
    print("\n================ RANKING PUZZLES ================")
    print("Arrange the items from highest to lowest rank based on the clues.")
    print("Example Answer: ABCDE")
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
            
        tracker.start_trial()
        
        user_ans = input("\nArrange from highest to lowest: ").strip().upper()
        is_correct = (user_ans == ans)
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 25
        else:
            print(f"Incorrect. The correct arrangement was: {ans}")
            
    print(f"\nScore: {score}")
    profile.save_game_result("rankings", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
