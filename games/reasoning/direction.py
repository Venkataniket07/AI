import random
import math
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def play_direction_sense(profile: ProfileManager):
    print("\n================ DIRECTION SENSE ================")
    print("Calculate the shortest distance from the starting point.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score = 0
    rounds = 5
    
    # Pre-calculated pythagorean triples for clean answers
    triples = [(3, 4, 5), (5, 12, 13), (6, 8, 10), (8, 15, 17), (9, 12, 15), (12, 16, 20)]
    
    for r in range(1, rounds + 1):
        dx_target, dy_target, ans = random.choice(triples)
        if random.choice([True, False]):
            dx_target, dy_target = dy_target, dx_target
            
        dx_target *= random.choice([1, -1])
        dy_target *= random.choice([1, -1])
        
        # Break down into 3-4 moves
        moves = []
        cx, cy = 0, 0
        
        # We need to end at dx_target, dy_target.
        # Let's do random intermediate moves.
        m1_x = random.randint(0, abs(dx_target)) * (1 if dx_target > 0 else -1)
        m1_y = random.randint(0, abs(dy_target)) * (1 if dy_target > 0 else -1)
        
        if m1_x != 0:
            moves.append(("East" if m1_x > 0 else "West", abs(m1_x)))
        if m1_y != 0:
            moves.append(("North" if m1_y > 0 else "South", abs(m1_y)))
            
        rem_x = dx_target - m1_x
        rem_y = dy_target - m1_y
        
        if rem_x != 0:
            moves.append(("East" if rem_x > 0 else "West", abs(rem_x)))
        if rem_y != 0:
            moves.append(("North" if rem_y > 0 else "South", abs(rem_y)))
            
        random.shuffle(moves)
        
        name = random.choice(["John", "Alice", "Bob", "Emma", "David"])
        
        print(f"\nRound {r}/{rounds}:")
        print(f"{name} walks:")
        for direction, dist in moves:
            print(f"  {dist}m {direction}")
            
        print("\nQuestion: How far is he/she from the starting point? (in meters)")
        tracker.start_trial()
        
        try:
            user_ans = int(input("> ").strip())
            is_correct = (user_ans == ans)
        except ValueError:
            is_correct = False
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20
        else:
            print(f"Incorrect. The correct answer was {ans}m.")
            
    print(f"\nScore: {score}")
    profile.save_game_result("direction_sense", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
