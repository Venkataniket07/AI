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

The games work fully without AI. With at least one API key configured you also get:

- Post-game coaching and an AI analysis on the statistics screen.
- Themed rewrites of seating clues (rejected automatically if they change which people a clue mentions).
- AI-written hints and explanations for Syllogisms and Blood Relations, and a check that accepts differently-worded relation answers (e.g. "mother's brother"). The AI never decides whether a numeric or logical answer is correct, and a hint that contains the answer is thrown away.

AI calls run in the background and retry once on transient errors (429/5xx), so the game does not wait on the network. If a provider fails, the next one is tried, and if all fail the game silently uses its built-in hints, explanations and clues.

Two providers are supported, tried in this order: **Google Gemini**, then **OpenRouter**. You only need one.

### 1. Get an API key (free)

| Provider | Where to get a key | Free tier needs a card? |
| :--- | :--- | :--- |
| Google Gemini | [Google AI Studio](https://aistudio.google.com/apikey) | No |
| OpenRouter | [openrouter.ai/keys](https://openrouter.ai/keys) | No (models ending in `:free`) |

### 2. Add the keys to `.env`

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Then edit `.env`:

```ini
AI_ENABLED=true

GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

- `.env` is git-ignored, so your keys are never committed. Keys are read **only** from the environment, never from `ai_config.json`.
- `.env` is read when the program starts. **After changing it, restart the game** (a running game keeps the old values).
- Set `AI_ENABLED=false` to turn all AI features off.
- A variable already set in your operating-system environment takes priority over the same name in `.env`.

### 3. Check that it works: `python -m ai.check`

```bash
python -m ai.check
```

This sends one small real request to each configured provider and prints the result:

```text
AI provider check
  PASS  gemini      model=gemini-2.5-flash  OK in 2.5s
  FAIL  openrouter  model=nvidia/nemotron-3-super-120b-a12b:free  FAILED: HTTP 401: User not found.
        -> The API key was rejected. Create a new key and set OPENROUTER_API_KEY in .env.
Result: at least one provider works.
```

- The exit code is `0` if at least one provider works and `1` if none do, so it can be used in scripts.
- A provider with no key is reported as `skipped (no API key set)`.
- For a retired or misspelled model it lists models your key can use.
- Your key is never printed.
- Run it after any change to `.env` or `ai_config.json`. It costs one tiny request per provider, which counts toward the free-tier limits.

While you play, a provider that is misconfigured (bad key, retired model) is reported **once per session** as `[AI] gemini isn't working (...)`. Temporary problems (rate limits, timeouts, provider outages) are not announced; the game just falls back. Details are always in `.log/ai.log`.

### Choosing models

Model names come from `.env` (`GEMINI_MODEL`, `OPENROUTER_MODEL`); if a variable is not set, the value in `ai_config.json` is used:

```json
{
  "ai_enabled": true,
  "providers": {
    "gemini": { "enabled": true, "model": "gemini-2.5-flash" },
    "openrouter": { "enabled": true, "model": "nvidia/nemotron-3-super-120b-a12b:free" }
  }
}
```

Set a provider's `"enabled"` to `false` to skip it. Free-tier models change often, so treat the tables below as a snapshot and run `python -m ai.check` to confirm a model works for your key.

**What the game needs from a model:** it must follow instructions to reply with JSON matching a schema, and answer within the timeout (10 s for Gemini, 12 s for OpenRouter). Slow "thinking" models can miss the timeout or run out of the 512-token reply limit.

#### Google Gemini

Status below was tested with a real free-tier key on 2026-09-30, through this project's own provider:

| Model | Result | Notes |
| :--- | :--- | :--- |
| `gemini-2.5-flash` _(default)_ | Works, about 2.5-4 s | Best balance of speed and reliability here. |
| `gemini-3.1-flash-lite` | Works, about 2-4 s | Lighter alternative. |
| `gemini-3.6-flash` | Works, about 3-5 s | Newer; fine if you want it. |
| `gemini-2.5-flash-lite` | **404** | "No longer available to new users", even though Google's pricing page still lists it. |
| `gemini-2.0-flash` | **404** | Retired. If your `.env` still says this, change it. |
| `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemma-4-26b-a4b-it` | Slow or invalid JSON in testing | Not recommended. |

Free-tier request limits are not published in Google's docs; your current limits are shown in [AI Studio](https://aistudio.google.com/rate-limit). Third-party sites quote roughly 15 requests/minute and 1,000/day for lightweight models, but those numbers are unofficial.

> **Privacy:** on Google's free tier, prompts and responses may be used to improve Google's products. This game sends your username and game statistics in its prompts. Use a paid key, or turn AI off with `AI_ENABLED=false`, if that matters to you.

#### OpenRouter

OpenRouter lists roughly 20 free models (ids ending in `:free`); the list changes constantly, and free models are sometimes rate-limited by their upstream provider.

| Model | Result (2026-09-30) | Notes |
| :--- | :--- | :--- |
| `nvidia/nemotron-3-super-120b-a12b:free` _(default)_ | Works, about 1-4 s | Reliable JSON output. |
| `google/gemma-4-31b-it:free` | 429 during testing | Rate-limited upstream at that moment; supports structured output. Retry later. |
| `google/gemma-4-26b-a4b-it:free` | 429 during testing | Same. |
| `qwen/qwen3.8-27b:free` | 429 during testing | Same. |
| `openrouter/free` | Works, but **do not use** | It picks a model for you and once picked a safety-classifier model that is unsuitable for this game. |

Third-party sources report free models are limited to about 50 requests/day (20/minute) unless you have bought credits; OpenRouter's own numbers may differ. Models not listed above were not tested.

### Troubleshooting

| What you see | Meaning | Fix |
| :--- | :--- | :--- |
| `HTTP 401` / `HTTP 403` / "User not found" | The API key is missing a character, revoked, or from a deleted account. | Create a new key, update `.env`, restart, run `python -m ai.check`. |
| `HTTP 404` with a model name | The model is retired or misspelled. | Set `GEMINI_MODEL` / `OPENROUTER_MODEL` to one that works; the check lists suggestions. |
| `HTTP 429` | Free quota or rate limit reached (often temporary, and for OpenRouter often upstream). | Wait a while, or switch model. The game falls back automatically. |
| `request timed out` | The model was too slow for the 10-12 s limit. | Use a lighter model. |
| `response was not valid JSON ...` | The model ignored the JSON format (or was cut off). | Use a different model. |
| `skipped (no API key set)` | That provider has no key. | Add the key, or ignore it if you only use the other provider. |
| Check passes but no AI text appears in the game | AI is off, or the game was started before `.env` changed. | Make sure `AI_ENABLED` is not `false`, and restart the game. |
| Anything else | | See `.log/ai.log` (never contains your key). |

## Directory Structure

```
AI/
├── ai/
│   ├── providers/             # Gemini and OpenRouter clients (sync, with retries)
│   ├── services/              # coaching, stats analysis, themes, hints/explanations/matching
│   ├── prompts/               # prompt templates
│   ├── router.py              # provider fallback chain per task
│   ├── background.py          # run AI calls on a background thread
│   ├── check.py               # `python -m ai.check` provider health check
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
3. (Optional, for AI features) Copy `.env.example` to `.env`, add your API keys and run `python -m ai.check` to verify them (see [AI features](#ai-features-optional)).
4. Run the game:
   ```bash
   python main.py
   ```

Data is stored in `brain_trainer.db` (SQLite) and logs in `.log/` (rotating `app.log` and `ai.log`, about 1 MB each, 5 backups).

### Development

Install all dependencies including development and testing tools:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

#### Running Tests

```bash
# Run the full test suite
pytest

# Run tests with terminal coverage report
pytest --cov

# Run tests with HTML coverage report (generates htmlcov/index.html)
pytest --cov --cov-report=html

# Run tests in verbose mode showing passed/skipped details
pytest -rs -v
```

#### Linting & Code Quality

```bash
# Check code style and lint rules
ruff check .

# Automatically apply safe lint fixes
ruff check . --fix

# Check formatting
ruff format --check .

# Auto-format codebase
ruff format .
```

CI runs both on Python 3.10 and 3.12.
