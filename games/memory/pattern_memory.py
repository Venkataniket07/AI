import time
import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen

def play_pattern_memory(profile: ProfileManager):
    print("\n================ PATTERN MEMORY ================")
    print("Memorize the coordinates (row, col) of the [X]s. 0-indexed.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 4
    used = set()
    
    for r in range(1, rounds + 1):
        clear_screen()
        
        grid_size = min(5, 3 + (streak // 2))
        num_xs = grid_size + (streak // 2)
        
        grid = [['[ ]' for _ in range(grid_size)] for _ in range(grid_size)]
        
        while True:
            coords = set()
            while len(coords) < num_xs:
                coords.add((random.randint(0, grid_size-1), random.randint(0, grid_size-1)))
            
            frozen = frozenset(coords)
            if frozen not in used:
                used.add(frozen)
                break
            
        for (row, col) in coords:
            grid[row][col] = '[X]'
            
        print("\nMemorize the pattern:\n")
        header = "    " + "   ".join(str(i) for i in range(grid_size))
        print(header)
        for i, row in enumerate(grid):
            print(f"  {i} " + " ".join(row))
            
        time.sleep(max(2.0, 4.0 - streak*0.5))
        clear_screen()
        
        print("\nWhere were the '[X]'s?")
        print("Format: row col, row col (e.g., 0 1, 2 2, 1 0)")
        tracker.start_trial()
        
        user_ans = input("Your answer: ").strip()
        
        try:
            pairs = user_ans.replace(';', ',').split(',')
            user_coords = set()
            for pair in pairs:
                parts = pair.strip().split()
                if len(parts) >= 2:
                    user_coords.add((int(parts[0]), int(parts[1])))
                
            is_correct = (user_coords == coords)
        except (ValueError, IndexError):
            is_correct = False
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 25 + streak*5
            streak += 1
        else:
            print("Incorrect.")
            print("Correct coordinates were:", ", ".join([f"{r} {c}" for r, c in coords]))
            streak = 0
            
        time.sleep(2)
            
    clear_screen()
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    profile.save_game_result("pattern_memory", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
