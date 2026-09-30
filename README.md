# Command-line Brain Games (Brain Trainer)

An interactive, text-based cognitive training suite featuring games across multiple cognitive domains, built with Python. Tracks player progression, accuracy and reaction time, adapts difficulty per game, and unlocks advanced categories as the player levels up. AI features (coaching, hints, explanations, themed puzzles) are optional.

## Features

- **Games**:
  - **Math**: Mental Arithmetic, Quick Calculation Duel
  - **Language**: Word Anagrams (online word service, with a built-in offline word list as a fallback). Difficulty follows how common a word is, not only its length: low levels use everyday words, high levels use longer, rarer ones. Each game starts a little easier and ramps up, and any real word made from the letters is accepted.
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
GEMINI_MODEL=gemini-3.1-flash-lite,gemini-3.6-flash,gemini-2.5-flash

OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

- `.env` is git-ignored, so your keys are never committed. Keys are read **only** from the environment, never from `ai_config.json`.
- `.env` is read when the program starts. **After changing it, restart the game** (a running game keeps the old values).
- Set `AI_ENABLED=false` to turn all AI features off.
- A variable already set in your operating-system environment takes priority over the same name in `.env`.
- `GEMINI_MODEL` can list several models separated by commas (see [Choosing models](#choosing-models)).

### 3. Check that it works: `python -m ai.check`

```bash
python -m ai.check              # 1 request per provider, using the game's real coaching prompt
python -m ai.check --all-models # test every model in GEMINI_MODEL, not just until one passes
python -m ai.check --full       # also test the stats, hint and explanation prompts
```

Example output:

```text
AI provider check  (coaching prompt)
  PASS  gemini      model=gemini-3.1-flash-lite  [session_summary]  OK in 2.1s (finish=STOP, thinking=0, output=68 tokens)
  ----  gemini      model=gemini-3.6-flash  not tested (an earlier model passed; use --all-models)
  ----  gemini      model=gemini-2.5-flash  not tested (an earlier model passed; use --all-models)
  FAIL  openrouter  model=nvidia/nemotron-3-super-120b-a12b:free  [session_summary]  FAILED: HTTP 401: User not found.
        -> The API key was rejected. Create a new key and set OPENROUTER_API_KEY in .env.
Result: at least one provider works.
```

- It uses the game's own prompt, so it can catch problems a tiny test would miss (for example a model that spends its whole reply on hidden "thinking" and returns a cut-off answer). The line shows the finish reason and how many tokens went on thinking.
- The exit code is `0` if at least one provider works and `1` if none do, so it can be used in scripts.
- A provider with no key is reported as `skipped (no API key set)`.
- For a retired or misspelled model it lists models your key can use; for a used-up daily quota it tells you what to do.
- Your key is never printed.
- Run it after any change to `.env` or `ai_config.json`. **Free tiers have small daily quotas** (see below), so by default it sends only one request per provider; use `--all-models` and `--full` sparingly.

While you play, a provider that is misconfigured (bad key, retired model) or whose free daily quota is used up is reported **once per session** as `[AI] gemini isn't working (...)`. Other temporary problems (rate limits, timeouts, provider outages) are not announced; the game just falls back. Details are always in `.log/ai.log`.

### Choosing models

Model names come from `.env` (`GEMINI_MODEL`, `OPENROUTER_MODEL`); if a variable is not set, the value in `ai_config.json` is used:

```json
{
  "ai_enabled": true,
  "providers": {
    "gemini": { "enabled": true, "model": "gemini-3.1-flash-lite,gemini-3.6-flash,gemini-2.5-flash" },
    "openrouter": { "enabled": true, "model": "nvidia/nemotron-3-super-120b-a12b:free" }
  }
}
```

Set a provider's `"enabled"` to `false` to skip it. Free-tier models change often, so treat the tables below as a snapshot and run `python -m ai.check` to confirm a model works for your key.

**Several Gemini models:** `GEMINI_MODEL` accepts a comma-separated list, tried in order. Each free-tier model has its **own daily request quota**, so when one is used up the next one keeps the game working. A model whose daily quota is used up is skipped for an hour instead of being asked again on every call. If every model is used up, the game falls back to OpenRouter and then to its built-in hints and explanations.

**What the game needs from a model:** it must reply with JSON matching a schema, and finish within the time limit (10 s for the whole Gemini attempt, 20 s for OpenRouter). Each reply may use up to 2048 tokens. "Thinking" models spend part of that on hidden reasoning; the game switches thinking off for Gemini Flash models, and asks OpenRouter models not to reason, but a model that uses its whole budget is reported as `reply cut off`.

#### Google Gemini

Tested with a real free-tier key on 2026-09-30, through this project's own provider:

| Model | Result | Notes |
| :--- | :--- | :--- |
| `gemini-3.1-flash-lite` _(default, first)_ | Works, about 2-3 s | Does not "think", so replies are short and fast. Its daily quota was not exhausted in testing (the limit is not published). |
| `gemini-3.6-flash` _(default, second)_ | Works, about 3 s with thinking off | With thinking left on it took about 6.5 s and used 850+ thinking tokens. Returned a temporary "high demand" 503 once. |
| `gemini-2.5-flash` _(default, last)_ | Works, about 2.5 s | **Only 20 requests per day** on the free tier (per project). That is why it is last: a few games use it up. |
| `gemini-2.5-flash-lite` | **404** | "No longer available to new users", even though Google's pricing page still lists it. |
| `gemini-2.0-flash` | **404** | Retired. If your `.env` still says this, change it. |
| `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemma-4-26b-a4b-it` | Slow or invalid JSON in earlier testing | Not retested since the reply budget was raised; not recommended. |

The 20-per-day figure is what the API itself reported when the quota ran out (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20). Google's docs do not publish free-tier limits; your current limits are shown in [AI Studio](https://aistudio.google.com/rate-limit). The daily quota resets around midnight Pacific time.

> **Privacy:** on Google's free tier, prompts and responses may be used to improve Google's products. This game sends your username and game statistics in its prompts. Use a paid key, or turn AI off with `AI_ENABLED=false`, if that matters to you.

#### OpenRouter

OpenRouter lists roughly 20 free models (ids ending in `:free`); the list changes constantly, and free models are sometimes rate-limited or overloaded upstream. OpenRouter sometimes reports an upstream problem as an HTTP 200 reply containing an error message; the game detects this, retries once, and otherwise shows the real reason.

| Model | Result (2026-09-30) | Notes |
| :--- | :--- | :--- |
| `nvidia/nemotron-3-super-120b-a12b:free` _(default)_ | Works, about 1-6 s (was 4-11 s) | A reasoning model; the game turns reasoning off (`reasoning: {enabled: false}`), which cut replies from 5-20 s to about 1-6 s. If a model refuses to run without reasoning, the game retries with it on. Occasionally returns "Service temporarily overloaded". |
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
| `HTTP 429: daily free quota used up for ...` | Every configured Gemini model has used today's free requests. | Add more models to `GEMINI_MODEL` (comma-separated), or wait for the reset (about midnight Pacific). The game falls back to OpenRouter meanwhile. |
| `HTTP 429` (other) | A per-minute limit, or OpenRouter's upstream limit (usually temporary). | Wait a moment, or switch model. The game falls back automatically. |
| `HTTP 503` / "temporarily overloaded" | The provider is busy. The game retries once. | Usually nothing; try again shortly. |
| `reply cut off (MAX_TOKENS ...)` / `finish_reason=length` | The model used its whole reply budget, usually on hidden reasoning. | Use a model that does not think at length (see the tables above). |
| `request timed out` | The model was too slow for the time limit. | Use a lighter model. |
| `response was not valid JSON ...` | The model ignored the JSON format. | Use a different model. |
| `skipped (no API key set)` | That provider has no key. | Add the key, or ignore it if you only use the other provider. |
| Check passes but no AI text appears in the game | AI is off, or the game was started before `.env` changed. | Make sure `AI_ENABLED` is not `false`, and restart the game. |
| Coaching appears above the *next* menu instead of right after a game | The model took longer than the short wait after the game. | Normal; it is shown as soon as it is ready. |
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
