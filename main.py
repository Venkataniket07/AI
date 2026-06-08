import sys
import os
import asyncio

# Load .env for API keys before any other imports
def load_dotenv():
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if len(val) >= 2 and (
                            (val.startswith('"') and val.endswith('"')) or
                            (val.startswith("'") and val.endswith("'"))
                        ):
                            val = val[1:-1]
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DBManager
from core.profile_manager import ProfileManager

# Import all math/memory/pattern games
from games.math.mental_math import play_mental_math
from games.math.quick_calc import play_quick_calc
from games.language.anagrams import play_anagrams
from games.pattern.sequences import play_sequence_prediction, play_pattern_completion, play_missing_number
from games.logic.matrix import play_matrix_reasoning
from games.memory.number_recall import play_number_recall
from games.memory.n_back import play_n_back
from games.memory.pattern_memory import play_pattern_memory

# Import Career Mode Reasoning Games
from games.reasoning.direction import play_direction_sense
from games.reasoning.blood_relations import play_blood_relations
from games.reasoning.coding import play_coding_decoding
from games.reasoning.rankings import play_rankings
from games.reasoning.syllogisms import play_syllogisms
from games.reasoning.seating import play_linear_seating, play_circular_seating
from games.reasoning.puzzle_grid import play_puzzle_grid

def display_stats(profile: ProfileManager):
    print("\n================ STATISTICS ================")
    stats = profile.db.get_user_stats(profile.current_user.id)
    if not stats:
        print("No games played yet. Go train your brain!")
    else:
        print(f"{'Date & Time':<16} | {'Game Type':<15} | {'Score':<5} | {'Accuracy':<8} | {'Reaction Time':<13}")
        print("-" * 68)
        for s in stats:
            print(f"{s.played_at[:16]} | {s.game_type:<15} | {s.score:<5} | {s.accuracy*100:6.1f}% | {s.reaction_time_ms:6.0f} ms")
    input("\nPress Enter to return to main menu...")


def _show_ai_coaching(profile: ProfileManager):
    """Post-game: silently request and print an AI coaching summary."""
    try:
        from ai.services.summary_service import summarize_session
        user = profile.current_user
        stats = profile.db.get_user_stats(user.id)
        coaching = asyncio.run(summarize_session(
            username=user.username,
            level=user.level,
            sessions=stats[:5],
            db_manager=profile.db,
        ))
        if coaching:
            print(f"\n🧠 Coach: {coaching}")
    except Exception:
        pass  # Never crash; AI coaching is purely decorative

def main():
    db = DBManager()
    profile = ProfileManager(db)
    
    print("========================================")
    print("        WELCOME TO BRAIN TRAINER        ")
    print("========================================")
    username = input("Enter your username: ").strip()
    if not username:
        print("Username cannot be empty. Exiting.")
        return
    
    profile.login(username)
    
    while True:
        profile.login(username)
        user = profile.current_user
        
        # Complete list of games with required minimum levels
        all_games = [
            ("Mental Arithmetic", play_mental_math, 1),
            ("Word Anagrams", play_anagrams, 1),
            ("Sequence Prediction", play_sequence_prediction, 1),
            ("Matrix Reasoning", play_matrix_reasoning, 1),
            ("Pattern Completion", play_pattern_completion, 1),
            ("Missing Number", play_missing_number, 1),
            ("Quick Calculation Duel", play_quick_calc, 1),
            ("Number Recall", play_number_recall, 1),
            ("N-Back Memory", play_n_back, 1),
            ("Pattern Memory", play_pattern_memory, 1),
            
            # Beginner Reasoning (Level 1+)
            ("Blood Relations", play_blood_relations, 1),
            ("Direction Sense", play_direction_sense, 1),
            ("Coding-Decoding", play_coding_decoding, 1),
            
            # Intermediate Reasoning (Level 3+)
            ("Ranking Puzzles", play_rankings, 3),
            ("Syllogisms", play_syllogisms, 3),
            ("Linear Seating", play_linear_seating, 3),
            
            # Advanced Reasoning (Level 6+)
            ("Circular Seating", play_circular_seating, 6),
            ("Puzzle Grids (Zebra)", play_puzzle_grid, 6),
        ]
        
        print("\n================ MAIN MENU ================")
        print(f"User: {user.username} (Level {user.level} | XP: {user.xp})")
        print("-------------------------------------------")
        
        for i, (title, _, req_level) in enumerate(all_games, 1):
            if i == 11:
                print("\n--- REASONING MASTER: Beginner (Req. Level 1) ---")
            elif i == 14:
                print("\n--- REASONING MASTER: Intermediate (Req. Level 3) ---")
            elif i == 17:
                print("\n--- REASONING MASTER: Advanced (Req. Level 6) ---")
                
            if user.level >= req_level:
                print(f"{i}. Play {title}")
            else:
                print(f"{i}. [LOCKED] Play {title} (Requires Level {req_level})")
            
        print("-" * 43)
        print(f"{len(all_games) + 1}. View Statistics")
        print(f"{len(all_games) + 2}. Exit")
        print("===========================================")
        
        choice = input("Select an option: ").strip()
        try:
            choice_idx = int(choice)
            if 1 <= choice_idx <= len(all_games):
                title, func, req_level = all_games[choice_idx - 1]
                if user.level >= req_level:
                    func(profile)
                    _show_ai_coaching(profile)  # post-game coaching (silent if AI unavailable)
                else:
                    print(f"\n❌ [LOCKED] '{title}' requires Level {req_level}. You are currently Level {user.level}.")
                    input("Press Enter to return...")
            elif choice_idx == len(all_games) + 1:
                display_stats(profile)
            elif choice_idx == len(all_games) + 2:
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please choose again.")
        except ValueError:
            print("Invalid choice. Please choose again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGame terminated. Exiting...")
        sys.exit(0)
