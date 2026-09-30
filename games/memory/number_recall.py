import time
import random
from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen

MAX_LENGTH = 12


def view_seconds(length: int, streak: int) -> float:
    """How long the digits stay up: longer numbers need longer to read, a streak shortens it a little."""
    return max(1.5, 1.5 + 0.25 * length - 0.2 * streak)


def play_number_recall(profile: ProfileManager):
    print("\n================ NUMBER RECALL ================")
    print("Memorize the sequence. It will disappear rapidly.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    base_difficulty = profile.difficulty("number_recall")
    used = set()
    
    for r in range(1, rounds + 1):
        clear_screen()
        
        current_length = min(MAX_LENGTH, 4 + (streak // 2) + base_difficulty)
        view_time = view_seconds(current_length, streak)
        
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
    finish_game(profile, "number_recall", score, tracker, "Press Enter to return...", difficulty=base_difficulty)
