import time
import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen

def play_number_recall(profile: ProfileManager):
    print("\n================ NUMBER RECALL ================")
    print("Memorize the sequence. It will disappear rapidly.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    used = set()
    
    for r in range(1, rounds + 1):
        clear_screen()
        
        current_length = 4 + (streak // 2) + profile.current_user.level
        view_time = max(1.0, 3.0 - (streak * 0.3))
        
        while True:
            raw_seq = "".join([str(random.randint(0, 9)) for _ in range(current_length)])
            if raw_seq not in used:
                used.add(raw_seq)
                break
                
        chunks = [raw_seq[i:i+3] for i in range(0, len(raw_seq), 3)]
        display_seq = "-".join(chunks)
        
        print(f"\nMemorize this sequence (Disappears in {view_time:.1f}s):")
        print(f"\n      {display_seq}\n")
        
        time.sleep(view_time)
        clear_screen()
        
        print("\nWhat was the sequence? (You can type with or without dashes)")
        tracker.start_trial()
        
        user_ans = input("Your answer: ").strip().replace("-", "")
        is_correct = (user_ans == raw_seq)
        
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The sequence was {display_seq}.")
            streak = 0
            
        time.sleep(1.5)
            
    clear_screen()
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    profile.save_game_result("number_recall", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
