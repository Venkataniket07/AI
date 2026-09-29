import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.env import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from utils.logger import init_loggers, get_app_logger
init_loggers()

logger = get_app_logger()
logger.info("Application startup initiated.")

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
    logger.info("User '%s' requested statistics view.", profile.current_user.username)
    print("\n================ STATISTICS ================")
    stats = profile.db.get_user_stats(profile.current_user.id)
    if not stats:
        print("No games played yet. Go train your brain!")
    else:
        print(f"{'Date & Time':<16} | {'Game Type':<15} | {'Score':<5} | {'Accuracy':<8} | {'Reaction Time':<13}")
        print("-" * 68)
        for s in stats:
            print(f"{s.played_at[:16]} | {s.game_type:<15} | {s.score:<5} | {s.accuracy*100:6.1f}% | {s.reaction_time_ms:6.0f} ms")
            
        try:
            from ai.services.stats_service import analyze_stats
            analysis = asyncio.run(analyze_stats(
                profile.current_user.username,
                profile.current_user.level,
                stats,
                profile.db
            ))
            if analysis:
                print(f"\n📊 AI Analysis: {analysis}")
        except Exception:
            logger.error("Failed to run AI stats analysis.", exc_info=True)

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
        logger.error("Failed to run AI coaching session.", exc_info=True)


def main():
    db = DBManager()
    profile = ProfileManager(db)
    
    print("========================================")
    print("        WELCOME TO BRAIN TRAINER        ")
    print("========================================")
    username = input("Enter your username: ").strip()
    if not username:
        logger.warning("Attempted login with empty username.")
        print("Username cannot be empty. Exiting.")
        return
    
    profile.login(username)
    user = profile.current_user
    if user:
        logger.info("User '%s' logged in successfully (Level: %d, XP: %d).", user.username, user.level, user.xp)
    else:
        logger.error("Failed to log in user '%s'.", username)
        return
    
    while True:
        profile.login(username)
        user = profile.current_user
        
        # Complete list of games with required minimum levels and categories
        all_games = [
            ("Mental Arithmetic", play_mental_math, 1, "CORE COGNITIVE TRAINING"),
            ("Word Anagrams", play_anagrams, 1, "CORE COGNITIVE TRAINING"),
            ("Sequence Prediction", play_sequence_prediction, 1, "CORE COGNITIVE TRAINING"),
            ("Matrix Reasoning", play_matrix_reasoning, 1, "CORE COGNITIVE TRAINING"),
            ("Pattern Completion", play_pattern_completion, 1, "CORE COGNITIVE TRAINING"),
            ("Missing Number", play_missing_number, 1, "CORE COGNITIVE TRAINING"),
            ("Quick Calculation Duel", play_quick_calc, 1, "CORE COGNITIVE TRAINING"),
            ("Number Recall", play_number_recall, 1, "CORE COGNITIVE TRAINING"),
            ("N-Back Memory", play_n_back, 1, "CORE COGNITIVE TRAINING"),
            ("Pattern Memory", play_pattern_memory, 1, "CORE COGNITIVE TRAINING"),
            
            # Beginner Reasoning (Level 1+)
            ("Blood Relations", play_blood_relations, 1, "REASONING MASTER: Beginner (Req. Level 1)"),
            ("Direction Sense", play_direction_sense, 1, "REASONING MASTER: Beginner (Req. Level 1)"),
            ("Coding-Decoding", play_coding_decoding, 1, "REASONING MASTER: Beginner (Req. Level 1)"),
            
            # Intermediate Reasoning (Level 3+)
            ("Ranking Puzzles", play_rankings, 3, "REASONING MASTER: Intermediate (Req. Level 3)"),
            ("Syllogisms", play_syllogisms, 3, "REASONING MASTER: Intermediate (Req. Level 3)"),
            ("Linear Seating", play_linear_seating, 3, "REASONING MASTER: Intermediate (Req. Level 3)"),
            
            # Advanced Reasoning (Level 6+)
            ("Circular Seating", play_circular_seating, 6, "REASONING MASTER: Advanced (Req. Level 6)"),
            ("Puzzle Grids (Zebra)", play_puzzle_grid, 6, "REASONING MASTER: Advanced (Req. Level 6)"),
        ]
        
        # Filter games to only show those that the user meets the level requirement for
        available_games = [g for g in all_games if user.level >= g[2]]
        
        print("\n================ MAIN MENU ================")
        print(f"User: {user.username} (Level {user.level} | XP: {user.xp})")
        print("-------------------------------------------")
        
        current_category = None
        for i, (title, _, _, category) in enumerate(available_games, 1):
            if category != current_category:
                current_category = category
                print(f"\n--- {current_category} ---")
            print(f"{i}. Play {title}")
            
        print("-" * 43)
        print(f"{len(available_games) + 1}. View Statistics")
        print(f"{len(available_games) + 2}. Exit")
        print("===========================================")
        
        choice = input("Select an option: ").strip()
        try:
            choice_idx = int(choice)
            if 1 <= choice_idx <= len(available_games):
                title, func, _, _ = available_games[choice_idx - 1]
                logger.info("User '%s' started game: %s", user.username, title)
                func(profile)
                logger.info("User '%s' finished game: %s", user.username, title)
                _show_ai_coaching(profile)  # post-game coaching (silent if AI unavailable)
            elif choice_idx == len(available_games) + 1:
                display_stats(profile)
            elif choice_idx == len(available_games) + 2:
                logger.info("User '%s' exited the application.", user.username)
                print("Goodbye!")
                break
            else:
                logger.warning("User '%s' made an invalid menu choice: %s", user.username, choice)
                print("Invalid choice. Please choose again.")
        except ValueError:
            logger.warning("User '%s' entered non-integer choice: %s", user.username, choice)
            print("Invalid choice. Please choose again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Application interrupted via KeyboardInterrupt.")
        print("\n\nGame terminated. Exiting...")
        sys.exit(0)
    except Exception:
        logger.critical("Uncaught exception at application root level.", exc_info=True)
        sys.exit(1)
