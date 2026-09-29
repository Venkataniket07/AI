# Command-line Brain Games (Brain Trainer)

An interactive, text-based cognitive training suite featuring games across multiple cognitive domains, built with Python. Tracks player progression, accuracy and reaction time, adapts difficulty per game, and unlocks advanced categories as the player levels up. AI features (coaching, hints, explanations, themed puzzles) are optional.

## Features

- **Games**:
  - **Math**: Mental Arithmetic, Quick Calculation Duel
  - **Language**: Word Anagrams (online word service, with a built-in offline word list as a fallback)
  - **Memory**: Number Recall, N-Back Memory, Pattern Memory
  - **Logic & Pattern**: Matrix Reasoning, Sequence Prediction, Pattern Completion, Missing Number
  - **Reasoning**: Blood Relations, Direction Sense, Coding-Decoding (Level 1+); Ranking Puzzles, Syllogisms, Linear Seating (Level 3+); Circular Seating, Puzzle Grids (Zebra) (Level 6+)
  - Every generated reasoning puzzle (rankings, seating, grid) is checked to have exactly one solution.
- **Progression**:
  - XP is normalised: a perfect run of any game is worth 100 XP, so games are comparable. 100 XP = one level.
  - Difficulty adapts per game: it starts at your level and moves up to two steps depending on your recent accuracy in that game.
- **Help while playing** (reasoning games): type `hint` at a prompt for up to 3 progressive hints (they cost 15% / 30% / 50% of the round's points). After a wrong answer you can ask for an explanation.
- **Statistics**: per-game summary (plays, best score, average accuracy and speed, trend), daily streak, and a paged play history.
- **Terminal input**: timed input and single-key detection work on Windows and Linux/macOS. Ctrl+C during a game returns to the menu without saving a partial result.

## AI features (optional)

Set `GEMINI_API_KEY` and/or `OPENROUTER_API_KEY` in `.env` (see `.env.example`). Keys are only read from the environment, never from `ai_config.json`. Without keys everything still works; the AI parts are simply skipped.

- Post-game coaching and a stats analysis.
- Themed rewrites of seating clues (rejected automatically if they change which people a clue mentions).
- AI-written hints and explanations for Syllogisms and Blood Relations, and a check that accepts differently-worded relation answers (e.g. "mother's brother"). The AI never decides whether a numeric or logical answer is correct, and a hint that contains the answer is thrown away.
- AI calls run in the background with retries on transient errors (429/5xx), so the game does not wait on the network.

## Directory Structure

```
AI/
├── ai/
│   ├── providers/             # Gemini and OpenRouter clients (sync, with retries)
│   ├── services/              # coaching, stats analysis, themes, hints/explanations/matching
│   ├── prompts/               # prompt templates
│   ├── router.py              # provider fallback chain per task
│   ├── background.py          # run AI calls on a background thread
│   └── config.py              # loads ai_config.json + environment
├── core/
│   ├── profile_manager.py     # user, XP, level, difficulty lookups
│   ├── difficulty.py          # per-game adaptive difficulty
│   ├── progression.py         # XP normalisation
│   └── stats.py               # streaks, trends and stats formatting
├── database/
│   ├── db_manager.py          # SQLite access + versioned migrations
│   └── models.py              # User, GameSession, GameSummary
├── games/
│   ├── registry.py            # the list of games (drives the menu)
│   ├── common.py              # shared end-of-game handling
│   ├── assist.py              # hints, penalties and explanations
│   └── language/ logic/ math/ memory/ pattern/ reasoning/
├── utils/                     # terminal input, logging, .env loader, performance tracker
├── tests/                     # pytest suite
└── main.py                    # entry point
```

To add a game, write a `play_<name>(profile)` function that ends with `finish_game(...)`, add a `Game(...)` entry to `games/registry.py`, and give its save id a reference score in `core/progression.py` (a test fails if you forget).

## Setup & Running

### Prerequisites
- Python 3.10+

### Installation & Execution
1. Clone or navigate to the repository directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Copy `.env.example` to `.env` and add your API keys (see above).
4. Run the game:
   ```bash
   python main.py
   ```

Data is stored in `brain_trainer.db` (SQLite) and logs in `.log/` (rotating `app.log` and `ai.log`, about 1 MB each, 5 backups).

### Development
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check .
```
CI runs both on Python 3.10 and 3.12.
