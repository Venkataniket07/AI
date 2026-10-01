import time
import random
from core.profile_manager import ProfileManager
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker
from utils.cli_tools import clear_screen, get_single_keypress_with_timeout

def play_n_back(profile: ProfileManager):
    print("\n================ N-BACK ================")
    print("Press 'y' if the current letter matches the letter seen N steps ago.")

    level = profile.difficulty("n_back")
    n_steps = min(level + 1, 4)  # level-to-N mapping is replaced in phase 2
    print(f"\nCurrently playing: {n_steps}-Back")
    input("Press Enter to start...")

    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 10

    letters = "ABCDEF"
    sequence = []
    targets = set(random.sample(range(n_steps, rounds), min(4, rounds - n_steps)))

    clear_screen()
    print("Get ready...")
    time.sleep(1.5)

    for r in range(rounds):
        clear_screen()
        timeout = max(1.0, 2.0 - (streak * 0.1))

        rand_val = random.random()
        if r in targets:
            current = sequence[-n_steps]
        elif r >= n_steps and rand_val < 0.2:
            lure_idx = -n_steps - 1 if (r > n_steps and random.choice([True, False])) else -n_steps + 1
            current = sequence[lure_idx]
        else:
            current = random.choice(letters)

        sequence.append(current)
        is_match = (r >= n_steps and current == sequence[-n_steps - 1])

        print(f"\n\n       {current}       \n\n")

        tracker.start_trial()

        key = get_single_keypress_with_timeout(timeout)
        pressed_match = (key is not None and key.lower() == 'y')
        is_correct = (is_match == pressed_match)

        tracker.end_trial(is_correct)
        if is_correct:
            score += 10 + streak
            streak += 1
        else:
            streak = 0

    clear_screen()
    print("\n================ GAME OVER ================")
    print(f"Score: {score}")
    finish_game(profile, "n_back", score, tracker, "Press Enter to return...", difficulty=level)
