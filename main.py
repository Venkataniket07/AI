import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core.profile_manager import ProfileManager
from database.db_manager import DBManager
from games.registry import available_games
from utils.env import load_dotenv
from utils.logger import get_app_logger, init_loggers

logger = get_app_logger()

COACH_WAIT_SECONDS = 3.0     # how long to wait for the post-game coaching after the game ends
ANALYSIS_WAIT_SECONDS = 15.0  # how long the stats screen waits for the AI analysis


def _ai_enabled() -> bool:
    try:
        from ai.config import config as ai_config
        return ai_config.ai_enabled
    except Exception:
        logger.error("AI configuration could not be loaded.", exc_info=True)
        return False


def display_stats(profile: ProfileManager):
    user = profile.current_user
    logger.info("User '%s' requested statistics view.", user.username)
    print("\n================ STATISTICS ================")
    stats = profile.db.get_user_stats(user.id)
    if not stats:
        print("No games played yet. Go train your brain!")
    else:
        print(f"{'Date & Time':<16} | {'Game Type':<15} | {'Score':<5} | {'Accuracy':<8} | {'Reaction Time':<13}")
        print("-" * 68)
        for s in stats:
            print(f"{s.played_at[:16]} | {s.game_type:<15} | {s.score:<5} | {s.accuracy*100:6.1f}% | {s.reaction_time_ms:6.0f} ms")

        if _ai_enabled():
            try:
                from ai.background import result_or_none, submit
                from ai.services.stats_service import analyze_stats
                print("\nAnalysing your performance...")
                analysis = result_or_none(
                    submit(analyze_stats, user.username, user.level, stats, profile.db),
                    timeout=ANALYSIS_WAIT_SECONDS,
                )
                if analysis:
                    print(f"\n📊 AI Analysis: {analysis}")
            except Exception:
                logger.error("Failed to run AI stats analysis.", exc_info=True)

    input("\nPress Enter to return to main menu...")


class CoachingPrefetcher:
    """Starts the AI coaching request as soon as a game result is saved, so it is ready when the game ends."""

    def __init__(self, profile: ProfileManager):
        self.profile = profile
        self.pending = None
        profile.on_result = self.start

    def start(self):
        if not _ai_enabled():
            return
        from ai.background import submit
        from ai.services.summary_service import summarize_session
        user = self.profile.current_user
        sessions = self.profile.db.get_user_stats(user.id)[:5]
        self.pending = submit(summarize_session, user.username, user.level, sessions, self.profile.db)

    def show(self):
        pending, self.pending = self.pending, None
        if pending is None:
            return
        from ai.background import result_or_none
        coaching = result_or_none(pending, timeout=COACH_WAIT_SECONDS)
        if coaching:
            print(f"\n🧠 Coach: {coaching}")


def main():
    load_dotenv(os.path.join(ROOT, ".env"))  # before anything reads API keys / log levels
    init_loggers()
    logger.info("Application startup initiated.")

    db = DBManager()
    profile = ProfileManager(db)
    coach = CoachingPrefetcher(profile)

    print("========================================")
    print("        WELCOME TO BRAIN TRAINER        ")
    print("========================================")
    username = input("Enter your username: ").strip()
    if not username:
        logger.warning("Attempted login with empty username.")
        print("Username cannot be empty. Exiting.")
        return

    if not profile.login(username):
        logger.error("Failed to log in user '%s'.", username)
        print("Could not log in. Exiting.")
        return

    while True:
        user = profile.current_user
        games = available_games(user.level)

        print("\n================ MAIN MENU ================")
        print(f"User: {user.username} (Level {user.level} | XP: {user.xp})")
        print("-------------------------------------------")

        current_category = None
        for i, game in enumerate(games, 1):
            if game.category != current_category:
                current_category = game.category
                print(f"\n--- {current_category} ---")
            print(f"{i}. Play {game.title}")

        print("-" * 43)
        print(f"{len(games) + 1}. View Statistics")
        print(f"{len(games) + 2}. Exit")
        print("===========================================")

        choice = input("Select an option: ").strip()
        try:
            choice_idx = int(choice)
        except ValueError:
            logger.warning("User '%s' entered non-integer choice: %s", user.username, choice)
            print("Invalid choice. Please choose again.")
            continue

        if 1 <= choice_idx <= len(games):
            game = games[choice_idx - 1]
            logger.info("User '%s' started game: %s", user.username, game.title)
            game.play(profile)
            logger.info("User '%s' finished game: %s", user.username, game.title)
            profile.refresh()  # pick up new XP / level
            coach.show()       # silent if AI is unavailable or not ready
        elif choice_idx == len(games) + 1:
            display_stats(profile)
        elif choice_idx == len(games) + 2:
            logger.info("User '%s' exited the application.", user.username)
            print("Goodbye!")
            break
        else:
            logger.warning("User '%s' made an invalid menu choice: %s", user.username, choice)
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
