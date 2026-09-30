import random
import time
from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.common import finish_game, parse_int
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import get_input_with_timeout

MIN_TIMEOUT = 2.5  # seconds; below this even a perfect typist cannot read, work out and type a two-digit answer


def play_quick_calc(profile: ProfileManager):
    print("\n================ QUICK CALCULATION DUEL ================")
    print("Solve the math problems before the timer expires!")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    level = profile.difficulty("quick_calc")
    score = 0
    rounds = 10
    streak = 0
    seen_questions = set()
    
    for r in range(1, rounds + 1):
        diff = level + (streak // 2)
        timeout = max(MIN_TIMEOUT, 6.0 - (diff * 0.5))
        
        while True:
            if diff < 3:
                ops = ['+', '-']
            else:
                ops = ['+', '-', '*']
                
            op = random.choice(ops)
            if op == '+':
                a = random.randint(5, 20 + diff*5)
                b = random.randint(5, 20 + diff*5)
                ans = a + b
                q = f"{a} + {b}"
            elif op == '-':
                a = random.randint(10, 30 + diff*5)
                b = random.randint(5, a)
                ans = a - b
                q = f"{a} - {b}"
            else:
                a = random.randint(2, 4 + diff)
                b = random.randint(2, 4 + diff)
                ans = a * b
                q = f"{a} * {b}"
                
            if q not in seen_questions:
                seen_questions.add(q)
                break
        
        print(f"\nRound {r}/{rounds} [Streak: {streak}] (You have {timeout:.1f} seconds!)")
        print(f"Solve: {q}")
        
        tracker.start_trial()
        user_ans_str = get_input_with_timeout("Your answer: ", timeout)
        
        is_correct = False
        if user_ans_str is None:
            print(f"Too slow! The correct answer was {ans}.")
        else:
            is_correct = parse_int(user_ans_str) == ans
            
            if is_correct:
                print("Correct!")
                elapsed_sec = time.perf_counter() - tracker.start_time
                speed_bonus = max(0, int(5 - elapsed_sec))
                pts = 10 + (streak * 2) + speed_bonus
                score += pts
                streak += 1
            else:
                print(f"Incorrect. The correct answer was {ans}.")
                streak = 0
                
        tracker.end_trial(is_correct, min_plausible_ms=answer_floor_ms(str(ans), q))
            
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    finish_game(profile, "quick_calc", score, tracker, "Press Enter to return...", difficulty=level)
