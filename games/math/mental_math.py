import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def play_mental_math(profile: ProfileManager):
    print("\n================ MENTAL ARITHMETIC ================")
    print("Solve the math problems as quickly and accurately as possible!")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    level = profile.current_user.level
    score = 0
    rounds = 10
    streak = 0
    seen_questions = set()
    
    for r in range(1, rounds + 1):
        diff = level + (streak // 2)
        
        while True:
            if diff < 2:
                ops = ['+', '-']
            elif diff < 4:
                ops = ['+', '-', '*']
            else:
                ops = ['+', '-', '*', '/', 'chained']
                
            op = random.choice(ops)
            
            if op == '+':
                a = random.randint(10 * diff, 50 * diff)
                b = random.randint(10 * diff, 50 * diff)
                ans = a + b
                q = f"{a} + {b}"
            elif op == '-':
                a = random.randint(20 * diff, 50 * diff)
                b = random.randint(10 * diff, a)
                ans = a - b
                q = f"{a} - {b}"
            elif op == '*':
                a = random.randint(2, 5 + diff)
                b = random.randint(2, 5 + diff)
                ans = a * b
                q = f"{a} * {b}"
            elif op == '/':
                b = random.randint(2, 10 + diff)
                ans = random.randint(2, 10 + diff)
                a = b * ans
                q = f"{a} / {b}"
            else:
                a = random.randint(2, 10 + diff)
                b = random.randint(2, 10 + diff)
                c = random.randint(2, 5 + diff)
                ans = (a + b) * c
                q = f"({a} + {b}) * {c}"
                
            if q not in seen_questions:
                seen_questions.add(q)
                break
            
        print(f"\nRound {r}/{rounds} [Streak: {streak}]: {q} = ?")
        tracker.start_trial()
        
        try:
            user_ans_str = input("Your answer: ").strip()
            user_ans = int(user_ans_str)
            is_correct = (user_ans == ans)
        except ValueError:
            is_correct = False
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            pts = 10 + (streak * 2)
            score += pts
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    print(f"Accuracy: {tracker.accuracy * 100:.1f}%")
    print(f"Average Speed: {tracker.avg_reaction_time_ms:.0f}ms")
    
    profile.save_game_result("mental_math", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("\nPress Enter to return to main menu...")
