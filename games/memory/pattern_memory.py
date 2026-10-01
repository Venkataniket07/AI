import re
import time
import random
from core.profile_manager import ProfileManager
from core.timing import answer_floor_ms, grid_size_and_xs, grid_view_seconds
from games.common import finish_game
from games.engine import ui
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen

def play_pattern_memory(profile: ProfileManager):
    print("\n================ PATTERN MEMORY ================")
    print("Memorize the coordinates (row, col) of the [X]s. 0-indexed.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 4
    level = profile.difficulty("pattern_memory")
    used = set()
    
    for r in range(1, rounds + 1):
        clear_screen()
        
        grid_size, num_xs = grid_size_and_xs(level + streak // 2)
        
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
            
        time.sleep(grid_view_seconds(num_xs, streak))
        clear_screen()
        
        print("\nWhere were the '[X]'s?")
        print("Format: row col, row col (e.g., 0 1, 2 2, 1 0)")
        tracker.start_trial()
        
        user_ans = input("Your answer: ").strip()
        
        # "0 1, 2 2", "0,1 2,2" and "(0, 1) (2, 2)" all work: the numbers are read in pairs
        numbers = [int(n) for n in re.findall(r"\d+", user_ans)]
        user_coords = set(zip(numbers[0::2], numbers[1::2])) if len(numbers) % 2 == 0 else None
        is_correct = (user_coords == coords)

        tracker.end_trial(is_correct, min_plausible_ms=answer_floor_ms("0" * (2 * num_xs)))
        ui.show_result(is_correct, user_ans, ", ".join(f"{r} {c}" for r, c in sorted(coords)))
        if is_correct:
            score += 25 + streak*5
            streak += 1
        else:
            streak = 0
            
    clear_screen()
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    finish_game(profile, "pattern_memory", score, tracker, "Press Enter to return...", difficulty=level)
