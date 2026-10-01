import time
import random
from core.profile_manager import ProfileManager
from core.timing import answer_floor_ms, recall_length, recall_view_seconds
from games.common import finish_game
from games.engine import ui
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen

def play_number_recall(profile: ProfileManager):
    print("\n================ NUMBER RECALL ================")
    print("Memorize the sequence. It disappears after a few seconds.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    level = profile.difficulty("number_recall")
    used = set()
    
    for r in range(1, rounds + 1):
        clear_screen()
        
        current_length = recall_length(level, streak)
        view_time = recall_view_seconds(current_length, streak)
        
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
        
        print("\nWhat was the sequence? (dashes, commas and spaces are ignored)")
        tracker.start_trial()
        
        user_ans = input("Your answer: ").replace("-", "").replace(",", "").replace(" ", "").strip()
        is_correct = (user_ans == raw_seq)
        
        tracker.end_trial(is_correct, min_plausible_ms=answer_floor_ms(raw_seq))
        ui.show_result(is_correct, user_ans, display_seq)
        if is_correct:
            score += 20 + streak*5
            streak += 1
        else:
            streak = 0
            
    clear_screen()
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    finish_game(profile, "number_recall", score, tracker, "Press Enter to return...", difficulty=level)
