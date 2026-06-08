# Command-line Brain Games (Brain Trainer)

An interactive, text-based cognitive training suite featuring games across multiple cognitive domains, built with Python. Tracks player progression, accuracy, reaction time, and unlocks advanced categories as user level increases.

## Features

- **Domain-Specific Cognitive Games**:
  - **Math**: Mental Arithmetic, Quick Calculation Duel
  - **Language**: Word Anagrams (fetches random words via API)
  - **Memory**: Number Recall, N-Back Memory, Pattern Memory
  - **Logic & Pattern**: Matrix Reasoning, Sequence Prediction, Pattern Completion, Missing Number
  - **Reasoning**: Blood Relations, Direction Sense, Coding-Decoding (Level 1+); Ranking Puzzles, Syllogisms, Linear Seating (Level 3+); Circular Seating, Puzzle Grids (Zebra) (Level 6+)
- **Progress Tracking & Profiles**:
  - Auto-updates user level and XP.
  - Persistent login and local data storage (`brain_trainer_data.json`).
- **Interactive Interface**:
  - Supports dynamic keypress detection and input timeouts (via `msvcrt` on Windows).
  - Clean menus and session metrics tracking (reaction times in milliseconds, accuracy percentage).

## Directory Structure

```
AI/
├── core/
│   └── profile_manager.py     # Manages user levels, XP, and state
├── database/
│   ├── db_manager.py          # Handles local JSON database read/writes
│   └── models.py              # Data models for User and GameSession
├── games/
│   ├── language/              # Anagrams
│   ├── logic/                 # Matrix Reasoning
│   ├── math/                  # Mental Math, Quick Calc
│   ├── memory/                # Number Recall, N-Back, Pattern Memory
│   ├── pattern/               # Sequence and patterns
│   └── reasoning/             # Blood Relations, Syllogisms, Seating, Grid
├── utils/
│   ├── cli_tools.py           # Cross-platform inputs and screen clearing
│   └── performance_tracker.py # Tracks scores, accuracy, and reaction times
└── main.py                    # Entry point of the application
```

## Setup & Running

### Prerequisites
- Python 3.10+

### Installation & Execution
1. Clone or navigate to the repository directory.
2. Run the main script (no third-party dependencies required):
   ```bash
   python main.py
   ```
