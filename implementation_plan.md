# AI Integration Plan — Brain Trainer CLI

## Goal

Add a hybrid AI layer to the existing deterministic Brain Trainer CLI. AI is **optional** — every game must work without it. AI is used only where it measurably improves the experience: richer narrative, step-by-step tutoring, semantic input parsing, and adaptive hinting. Fast-response loops (Quick Calc, N-Back, Pattern Memory) remain 100% deterministic Python.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                     main.py                         │
│            (menu, routing, game loop)               │
└─────────────┬───────────────────────────┬───────────┘
              │                           │
  ┌───────────▼──────────┐     ┌──────────▼──────────┐
  │   games/*  (existing)│     │ core/profile_manager │
  │  deterministic logic │     │ database/db_manager  │
  └───────────┬──────────┘     └─────────────────────┘
              │
   calls (optional)
              │
  ┌───────────▼──────────────────────────────────────┐
  │              ai/  (NEW LAYER)                    │
  │                                                  │
  │  ai/config.py        – model & provider config   │
  │  ai/router.py        – picks provider per task   │
  │  ai/providers/       – thin wrappers per backend │
  │    ├── ollama.py      – local Ollama HTTP client  │
  │    ├── gemini.py      – Gemini AI Studio REST     │
  │    └── openrouter.py  – OpenRouter REST           │
  │  ai/schemas.py       – Pydantic response schemas  │
  │  ai/prompts/         – prompt templates (*.txt)   │
  │  ai/cache.py         – response caching           │
  └──────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **No LangChain. No LangGraph.** The AI layer is a plain Python service module using `httpx` (async HTTP client) and `pydantic` (schema validation). This keeps the dependency surface minimal and avoids framework overhead that adds no value for our use case (single-turn structured calls, no multi-agent orchestration).

---

## 2. Decision Matrix — When to Use What

| Capability | Deterministic Python | Local LLM (Ollama) | Gemini API | OpenRouter |
|---|---|---|---|---|
| **Puzzle generation (math, sequence, pattern)** | ✅ Primary | ✗ | ✗ | ✗ |
| **Puzzle generation (reasoning — seating, blood, syllogisms)** | ✅ Constraint solver stays | 🟡 Theme/narrative wrapper | ✗ | ✗ |
| **Puzzle generation (language — anagrams)** | ✅ Word pool + Datamuse | ✗ | ✗ | ✗ |
| **Answer verification (exact match)** | ✅ Always | ✗ | ✗ | ✗ |
| **Semantic answer interpretation** | ✗ | ✅ Preferred | 🔄 Fallback | ✗ |
| **Hint generation (progressive)** | ✅ Rule-based first hint | ✅ Richer 2nd/3rd hints | 🔄 Fallback | ✗ |
| **Explanation after wrong answer** | ✗ (just shows answer) | ✅ Preferred | 🔄 Fallback | ✗ |
| **Theme/story wrapping** | ✗ | ✅ Preferred | 🔄 Fallback | ✗ |
| **Session summary / coaching** | ✗ | ✅ Preferred | 🔄 Fallback | ✗ |
| **Timer-critical input loops** | ✅ Only | ✗ | ✗ | ✗ |
| **Scoring / XP / level-up** | ✅ Only | ✗ | ✗ | ✗ |
| **New puzzle types (riddles, reading comprehension)** | ✗ | ✅ Generate | 🔄 Fallback | 🔄 Fallback |

### Legend
- ✅ = Use this
- 🟡 = Optional enhancement
- 🔄 = Fallback if primary fails
- ✗ = Do not use

---

## 3. Module-by-Module AI Applicability

### Games That Should **NOT** Use AI

These are timing-critical, reaction-based, or mathematically verified games where AI latency would degrade the experience and AI correctness is unnecessary.

| Module | File | Reason |
|---|---|---|
| Quick Calc Duel | [quick_calc.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/math/quick_calc.py) | Real-time timer via `msvcrt`; math is deterministic |
| N-Back Memory | [n_back.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/memory/n_back.py) | Sub-second keypress loop; purely algorithmic |
| Number Recall | [number_recall.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/memory/number_recall.py) | Sequence display is instantaneous; no narrative needed |
| Pattern Memory | [pattern_memory.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/memory/pattern_memory.py) | Grid coordinates; no text interpretation needed |
| Mental Arithmetic | [mental_math.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/math/mental_math.py) | Pure math generation and verification |
| Sequence Prediction | [sequences.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/pattern/sequences.py) | Deterministic mathematical sequences |
| Pattern Completion | [sequences.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/pattern/sequences.py) | Deterministic letter/number patterns |
| Missing Number | [sequences.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/pattern/sequences.py) | Deterministic |

### Games That **Should** Use AI (Selectively)

| Module | File | AI Use Cases |
|---|---|---|
| **Blood Relations** | [blood_relations.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/blood_relations.py) | Themed scenario wrapping, step-by-step wrong-answer explanation, semantic answer validation ("uncle" vs "maternal uncle") |
| **Syllogisms** | [syllogisms.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/syllogisms.py) | Richer entity themes (instead of "cats" and "dogs"), wrong-answer explanation ("Here's why 'Cannot be determined' is correct...") |
| **Seating** | [seating.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/seating.py) | Story-wrapped clues (dinner party scenario), progressive AI hints |
| **Direction Sense** | [direction.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/direction.py) | Story-wrapped movement descriptions, step-by-step solution walkthrough on failure |
| **Coding-Decoding** | [coding.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/coding.py) | Wrong-answer explanation showing cipher analysis step-by-step |
| **Rankings** | [rankings.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/rankings.py) | Themed ranking contexts (sports tournament, exam results), explanation |
| **Puzzle Grid** | [puzzle_grid.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/puzzle_grid.py) | Story-wrapped clue presentation, progressive hint system, wrong-answer walkthrough |
| **Anagrams** | [anagrams.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/language/anagrams.py) | AI-generated contextual hint (instead of just showing first letter), semantic near-miss detection |

### New AI-Native Game Modes (Phase 4)

| Proposed Game | Description | AI Role |
|---|---|---|
| **Riddle Master** | AI generates themed riddles with difficulty scaling | Full generation (with schema validation) |
| **Reading Comprehension** | Short paragraph → questions | Full generation (with deterministic scoring) |
| **Story Deduction** | Multi-turn detective-style Q&A | Stateful conversation (AI maintains clue state) |

---

## 4. Routing Strategy — Model Selection by Task Type

The router (`ai/router.py`) selects a provider based on the task type. No round-robin or load balancing — it's a simple priority lookup with fallback.

| Task Type | Primary Provider | Why | Est. Latency | Fallback Chain |
|---|---|---|---|---|
| **Theme/story wrapping** | Ollama (`llama3.2:3b`) | Creative text, tolerates minor imperfection, runs locally | 2-4s | Gemini → static template |
| **Wrong-answer explanation** | Ollama (`llama3.2:3b`) | Reasoning about logic steps, privacy (user data stays local) | 2-4s | Gemini → "The answer was X" |
| **Progressive hint generation** | Ollama (`qwen2.5:3b`) | Good instruction-following for structured hints | 1-3s | Gemini → rule-based hint |
| **Semantic answer validation** | Ollama (`phi3.5:mini`) | Fast binary yes/no classification | 0.5-2s | Gemini → exact string match |
| **Riddle/content generation** | Gemini (`gemini-2.0-flash`) | Higher reasoning quality needed for novel puzzles | 1-2s | OpenRouter (`llama-3.2-3b-free`) → skip |
| **Session summary / coaching** | Ollama (`llama3.2:3b`) | Personalized, runs post-game (no latency pressure) | 3-5s | Gemini → stats-only summary |
| **Code/config generation** | N/A | Not applicable for this CLI game | — | — |

### Router Logic (Pseudocode)

```python
# ai/router.py

class TaskType(Enum):
    THEME_WRAP = "theme_wrap"
    EXPLAIN = "explain"
    HINT = "hint"
    SEMANTIC_VALIDATE = "semantic_validate"
    GENERATE_CONTENT = "generate_content"
    SESSION_SUMMARY = "session_summary"

ROUTING_TABLE = {
    TaskType.THEME_WRAP:        ["ollama", "gemini", "static"],
    TaskType.EXPLAIN:           ["ollama", "gemini", "static"],
    TaskType.HINT:              ["ollama", "gemini", "static"],
    TaskType.SEMANTIC_VALIDATE: ["ollama", "gemini", "exact_match"],
    TaskType.GENERATE_CONTENT:  ["gemini", "openrouter", "skip"],
    TaskType.SESSION_SUMMARY:   ["ollama", "gemini", "static"],
}

async def route(task: TaskType, prompt: str, schema: type) -> dict:
    for provider_name in ROUTING_TABLE[task]:
        if provider_name == "static":
            return None  # signal: use deterministic fallback
        provider = get_provider(provider_name)
        if not provider.is_available():
            continue
        try:
            return await provider.generate(prompt, schema, timeout=8.0)
        except (TimeoutError, ValidationError):
            continue
    return None
```

---

## 5. Fallback Policy

```
┌─────────────────────┐
│ 1. Local LLM        │  Ollama running? Model loaded?
│    (Ollama)          │  → Try with 8s timeout
└────────┬────────────┘
         │ fail / timeout / schema invalid
         ▼
┌─────────────────────┐
│ 2. Cloud API        │  API key configured? Internet available?
│    (Gemini / OR)    │  → Try with 10s timeout
└────────┬────────────┘
         │ fail / timeout / schema invalid
         ▼
┌─────────────────────┐
│ 3. Deterministic    │  Always works. No latency.
│    Fallback         │  → Use existing Python behavior
└─────────────────────┘
```

### Fallback Behavior Per Task

| Task | Deterministic Fallback |
|---|---|
| Theme wrapping | Skip theme; use raw clues (current behavior) |
| Wrong-answer explanation | Print `"The correct answer was: {ans}"` (current behavior) |
| Hint generation | Rule-based hint: first letter, then definition (current behavior in anagrams) |
| Semantic validation | Exact string match after normalization (current behavior) |
| Content generation | Skip entirely; game is not available without AI |
| Session summary | Show stats table only (current behavior) |

> [!TIP]
> The fallback must be **instant and silent**. The user should never see "AI failed, falling back..." messages. The experience just gracefully degrades to what it was before AI integration.

---

## 6. Validation Policy

### Strict JSON Output

All AI responses must conform to Pydantic schemas. No free-text parsing.

```python
# ai/schemas.py
from pydantic import BaseModel, Field

class ThemedPuzzle(BaseModel):
    scenario: str = Field(..., max_length=500,
        description="A short themed story setting for the puzzle")
    clues: list[str] = Field(..., min_length=2, max_length=8)

class Explanation(BaseModel):
    steps: list[str] = Field(..., min_length=1, max_length=6,
        description="Step-by-step logical breakdown")
    summary: str = Field(..., max_length=200)

class HintResponse(BaseModel):
    hint_text: str = Field(..., max_length=150)
    difficulty_reduction: float = Field(ge=0.0, le=0.5,
        description="How much this hint reduces difficulty (for scoring)")

class SemanticMatch(BaseModel):
    is_equivalent: bool
    confidence: float = Field(ge=0.0, le=1.0)
    canonical_answer: str
```

### Prompt Engineering for Structured Output

```python
# In every prompt template:
SYSTEM_SUFFIX = """
You MUST respond with valid JSON matching the schema below.
Do NOT include any text outside the JSON object.
Do NOT wrap it in markdown code fences.

Schema:
{schema_json}
"""
```

### Validation Pipeline

```
LLM raw output
    │
    ▼
 json.loads()  ──fail──▶  RETRY once with "Fix your JSON" prompt
    │                           │
    ▼                      fail again
 Pydantic.model_validate()      │
    │                           ▼
    ▼                    Deterministic fallback
 Schema-valid response
    │
    ▼
 Domain checks (see below)
    │
    ▼
 Return to game
```

### Domain-Level Integrity Rules

> [!CAUTION]
> **AI never verifies puzzle correctness.** These checks are always deterministic Python:

| Check | Implementation |
|---|---|
| Seating arrangement validity | Python constraint solver validates the answer |
| Math answer correctness | `eval()` / direct comparison |
| Sequence next value | Deterministic formula |
| Blood relation answer | Template lookup |
| Syllogism truth value | Template lookup |

**AI is only allowed to:**
- Add narrative flavor to clues/questions
- Explain why an answer was wrong (given the known correct answer)
- Interpret fuzzy user input (given the known correct answer to compare against)
- Generate hints (given the puzzle state)

**AI is never the source of truth for:**
- The correct answer to any puzzle
- Score calculations
- Level-up decisions
- Timer durations

---

## 7. Project Structure — Where AI Lives

```
brain_trainer/
├── main.py
├── core/
│   ├── profile_manager.py
│   └── theme_manager.py
├── database/
│   ├── db_manager.py
│   └── models.py
├── games/
│   ├── base_game.py
│   ├── math/
│   │   ├── mental_math.py           # NO AI
│   │   └── quick_calc.py            # NO AI
│   ├── memory/
│   │   ├── n_back.py                # NO AI
│   │   ├── number_recall.py         # NO AI
│   │   └── pattern_memory.py        # NO AI
│   ├── pattern/
│   │   └── sequences.py             # NO AI
│   ├── language/
│   │   └── anagrams.py              # Phase 2: hints, semantic matching
│   └── reasoning/                   # Phase 1-3: all modules get AI
│       ├── blood_relations.py
│       ├── coding.py
│       ├── direction.py
│       ├── puzzle_grid.py
│       ├── rankings.py
│       ├── seating.py
│       └── syllogisms.py
├── ai/                              # ← NEW DIRECTORY
│   ├── __init__.py
│   ├── config.py                    # Provider config, API keys, model names
│   ├── router.py                    # Task → provider routing + fallback
│   ├── schemas.py                   # Pydantic response models
│   ├── cache.py                     # In-memory LRU + optional disk cache
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                  # Abstract provider interface
│   │   ├── ollama.py                # httpx POST to localhost:11434
│   │   ├── gemini.py                # httpx POST to generativelanguage.googleapis.com
│   │   └── openrouter.py            # httpx POST to openrouter.ai/api/v1
│   └── prompts/
│       ├── theme_wrap.txt           # "Wrap these clues in a {theme} scenario..."
│       ├── explain.txt              # "The user answered {user_ans}. Correct was {correct}..."
│       ├── hint.txt                 # "Give a progressive hint for: {puzzle_state}..."
│       ├── semantic_match.txt       # "Is '{user_input}' semantically equivalent to '{target}'..."
│       └── session_summary.txt      # "Summarize this game session: {stats}..."
│   └── services/
│       ├── __init__.py
│       ├── theme_service.py         # wrap_puzzle_in_theme(puzzle_data, theme) -> ThemedPuzzle
│       ├── explain_service.py       # explain_wrong_answer(question, user_ans, correct) -> Explanation
│       ├── hint_service.py          # generate_hint(puzzle_state, hints_used) -> HintResponse
│       ├── semantic_service.py      # is_answer_equivalent(user_input, target) -> SemanticMatch
│       └── summary_service.py       # summarize_session(stats) -> str
├── ui/
│   └── app.py
└── utils/
    ├── cli_tools.py
    └── performance_tracker.py
```

### Key Design Decisions

1. **`ai/providers/`** — Each provider is a thin wrapper around a single HTTP endpoint. ~50 lines each. No SDK dependencies.
2. **`ai/services/`** — Domain-specific services that compose a prompt + schema + router call. Game modules call these, not the raw providers.
3. **`ai/prompts/`** — Plain text files loaded at startup. Easy to iterate without code changes.
4. **`ai/config.py`** — Reads from `ai_config.json` in the project root. User can toggle AI on/off, set API keys, and choose default models.

### Config File Format (`ai_config.json`)

```json
{
  "ai_enabled": true,
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "default_model": "llama3.2:3b",
      "models": {
        "theme_wrap": "llama3.2:3b",
        "explain": "llama3.2:3b",
        "hint": "qwen2.5:3b",
        "semantic_validate": "phi3.5:mini"
      }
    },
    "gemini": {
      "enabled": false,
      "api_key": "",
      "model": "gemini-2.0-flash"
    },
    "openrouter": {
      "enabled": false,
      "api_key": "",
      "model": "meta-llama/llama-3.2-3b-instruct:free"
    }
  },
  "cache": {
    "enabled": true,
    "max_entries": 200,
    "ttl_seconds": 3600
  }
}
```

---

## 8. Phased Rollout

### Phase 1 — Infrastructure + No-Risk AI (Week 1-2)

**Goal:** Build the AI layer and integrate it where failure has zero user impact.

| Task | Details |
|---|---|
| Create `ai/` module structure | `config.py`, `router.py`, `schemas.py`, `cache.py` |
| Implement Ollama provider | HTTP POST to `/api/generate`, JSON mode, timeout handling |
| Implement Gemini provider | REST API with API key auth, structured output |
| Implement OpenRouter provider | OpenAI-compatible API format |
| Build `ai_config.json` loader | With validation and sensible defaults |
| Add health check | `GET /api/tags` for Ollama, test prompt for cloud APIs |
| **Integration: Session Summary** | After any game ends, optionally call `summary_service.summarize_session()` to print a 2-3 sentence coaching summary below the score. If AI fails → just show score (current behavior). |
| **Integration: Theme wrapping for Seating** | Before presenting clues in [seating.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/seating.py), call `theme_service.wrap_puzzle_in_theme()`. If AI fails → show raw clues (current behavior). |

**Risk Level:** Zero. Both features are post-answer or pre-display decoration. No game logic is affected.

---

### Phase 2 — Explanation + Hint Layer (Week 3-4)

**Goal:** After a wrong answer, the game can now teach. Hints become smarter.

| Task | Details |
|---|---|
| Build `explain_service.py` | Takes `(question, user_answer, correct_answer)` → returns step-by-step breakdown |
| Build `hint_service.py` | Takes `(puzzle_state, hints_used_count)` → returns progressive hint |
| **Integration: Wrong-Answer Explanations** | Apply to all 7 reasoning games. After printing "Incorrect", offer `"Press 'e' for explanation, Enter to continue"`. If user presses 'e', call explain service. If AI fails → skip. |
| **Integration: Smarter Anagram Hints** | Replace hint #2 in [anagrams.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/language/anagrams.py) with AI-generated contextual clue. Hint #1 (first letter) stays deterministic. |
| **Integration: Puzzle Grid Hints** | In [puzzle_grid.py](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/puzzle_grid.py), add `"3. Ask for a hint"` option that calls the hint service with current table state. |
| Extend theme wrapping | Apply to Blood Relations, Direction Sense, Rankings, Puzzle Grid, Syllogisms |

**Risk Level:** Low. All explanations/hints are post-answer or user-initiated. Puzzle logic is untouched.

---

### Phase 3 — Semantic Assistant Layer (Week 5-6)

**Goal:** The game understands natural language answers.

| Task | Details |
|---|---|
| Build `semantic_service.py` | Takes `(user_input, target_answer)` → returns `SemanticMatch` |
| **Integration: Blood Relations** | Replace exact string match in [blood_relations.py L58](file:///c:/Users/aniket.nd/Downloads/Angular/Temp/games/reasoning/blood_relations.py#L58) with semantic check. Accept "uncle" for "Uncle", "mama's brother" for "Uncle", "he's the uncle" for "Uncle". |
| **Integration: Anagrams near-miss** | If exact match fails, check if user's word is a valid English word that uses the same letters (a valid alternative anagram). |
| **Integration: Rankings** | Accept free-text ranking descriptions ("B is first, then E, then A...") |
| Confidence threshold | Only accept semantic matches with `confidence >= 0.85`. Below that → treat as incorrect but show "Did you mean {canonical}?" |

**Risk Level:** Medium. Semantic validation affects scoring. Requires careful threshold tuning and a deterministic fallback (exact match) if AI is unavailable.

### Safeguard for Phase 3

```python
async def check_answer(user_input: str, correct: str, game_type: str) -> bool:
    # 1. Always try exact match first (fast, free, reliable)
    if normalize(user_input) == normalize(correct):
        return True

    # 2. Try semantic match only if AI is available
    match = await semantic_service.is_answer_equivalent(user_input, correct)
    if match and match.is_equivalent and match.confidence >= 0.85:
        return True

    # 3. Default: incorrect
    return False
```

---

### Phase 4 — Adaptive & Personalized Layer (Week 7-8)

**Goal:** AI-native optional game modes and personalized coaching.

| Task | Details |
|---|---|
| **New Game: Riddle Master** | AI generates a riddle with a known answer. Schema: `{riddle: str, answer: str, hints: list[str]}`. Deterministic scoring + exact/semantic answer check. |
| **New Game: Reading Comprehension** | AI generates a 100-word paragraph + 3 MCQ questions. Schema: `{passage: str, questions: [{q: str, options: [str], correct_idx: int}]}`. Deterministic scoring via `correct_idx`. |
| **Adaptive difficulty hints** | After 3 consecutive wrong answers in any reasoning game, automatically offer an AI explanation without the user asking. |
| **Personalized session intro** | On login, if AI is available, generate a 1-line motivational greeting based on the user's recent stats. If AI unavailable → skip. |
| **Preference learning** | Track which themes the user enjoys (sci-fi, mystery, sports) and pass to the theme service. |

**Risk Level:** Medium. New game modes depend on AI availability. They should be clearly marked as `[AI]` in the menu and hidden if AI is fully offline.

---

## 9. Testing & Acceptance Criteria

### Phase 1

| Test | Pass Criteria |
|---|---|
| Ollama provider unit test | Sends prompt, receives valid JSON, parses to schema. Handles timeout gracefully (returns `None`). |
| Gemini provider unit test | Same as above with API key auth. |
| OpenRouter provider unit test | Same as above with Bearer token auth. |
| Router fallback test | Kill Ollama → router falls through to Gemini → kill Gemini → returns `None`. No exceptions raised. |
| Config loader test | Missing `ai_config.json` → AI disabled silently. Malformed JSON → AI disabled with warning. |
| Session summary integration | Play a full game → summary appears after score. Kill Ollama mid-game → score appears alone (no crash, no error message). |
| Theme wrap integration | Play Seating → clues appear with narrative wrapper. Kill Ollama → clues appear raw (identical to current behavior). |
| **Latency gate** | Theme wrapping must complete in <5s (local) or <3s (cloud). If exceeded, timeout and use fallback. |

### Phase 2

| Test | Pass Criteria |
|---|---|
| Explanation service test | Given a wrong answer, returns 1-6 step explanation that mentions the correct answer. |
| Hint service test | Given puzzle state and `hints_used=0`, returns a non-revealing hint. With `hints_used=2`, returns a near-giveaway hint. |
| Explanation UX test | After wrong answer, pressing 'e' shows explanation in <5s. Pressing Enter skips it. |
| Hint scoring test | Using a hint reduces the score for that round by `difficulty_reduction * base_score`. |
| Fallback silence test | All AI features degrade silently. Run full game suite with `ai_enabled: false` → identical behavior to pre-AI codebase. |

### Phase 3

| Test | Pass Criteria |
|---|---|
| Semantic match accuracy | Test with 30 known equivalent pairs (e.g., "uncle" ↔ "Uncle", "brother-in-law" ↔ "Brother In Law", "he is the cousin" ↔ "Cousin") → ≥90% correct classification. |
| Semantic match rejection | Test with 20 known non-equivalent pairs → ≥95% correctly rejected. |
| Fallback to exact match | With AI disabled, semantic check is skipped entirely, exact match is used. No scoring regression. |
| Confidence threshold | Answers with confidence 0.5-0.84 → marked incorrect but show "Did you mean...?" |
| No score inflation | Run 100 rounds with AI vs without AI → average score difference <10%. |

### Phase 4

| Test | Pass Criteria |
|---|---|
| Riddle generation | Generate 20 riddles → all have non-empty riddle text, answer, and ≥2 hints. Manual review: ≥80% are solvable and make sense. |
| Reading comprehension | Generate 10 passages → all have 100±30 words, 3 MCQ with valid `correct_idx` in range. Manual review: ≥80% questions are answerable from the passage. |
| Menu visibility | With AI fully offline, `[AI]` games are hidden from the menu. No dead options. |
| Full regression | Run the entire game suite (all 15+ games) with AI enabled and disabled. No crashes, no hangs, no score corruption. |

---

## 10. Non-Goals

> [!WARNING]
> The following are explicitly out of scope:

| Non-Goal | Reason |
|---|---|
| AI in timing-critical loops (Quick Calc, N-Back) | 2-5s latency destroys the experience |
| AI for exact math verification | Python is faster and correct; LLMs hallucinate arithmetic |
| AI as the final truth source for any puzzle | Constraint solvers and templates are deterministic and provably correct |
| LangChain / LangGraph | Unnecessary abstraction for single-turn structured calls. A plain `httpx` + `pydantic` service layer is simpler, faster to debug, and has zero transitive dependencies |
| Multi-agent orchestration | No game mode requires agents talking to each other |
| Fine-tuning or training custom models | Out of scope; use off-the-shelf models with prompt engineering |
| GPU-only models | Default local models must run on CPU. GTX 1650 (4GB VRAM) is a bonus, not a requirement |
| Always-online requirement | Every game must work with AI fully disabled |

---

## 11. Prioritized Build Order

```
Priority  Task                                     Phase  Est. Effort  Dependencies
───────── ──────────────────────────────────────── ────── ──────────── ────────────
1         ai/config.py + ai_config.json            P1     2h           None
2         ai/providers/base.py (abstract)           P1     1h           None
3         ai/providers/ollama.py                    P1     3h           #2
4         ai/providers/gemini.py                    P1     2h           #2
5         ai/providers/openrouter.py                P1     2h           #2
6         ai/router.py (with fallback chain)        P1     3h           #3,#4,#5
7         ai/schemas.py (all Pydantic models)       P1     2h           None
8         ai/cache.py (SQLite disk cache)           P1     2h           None
9         Migrate JSON user data → SQLite           P1     2h           None
9b        ai/services/summary_service.py            P1     2h           #6,#7
10        ai/services/theme_service.py              P1     2h           #6,#7
11        Integrate session summary into game loop  P1     1h           #9
12        Integrate theme wrap into seating.py      P1     1h           #10
──────── ─ Phase 1 Complete ─────────────────────────────────────────────────────
13        ai/prompts/ (all prompt templates)        P2     3h           None
14        ai/services/explain_service.py            P2     3h           #6,#7,#13
15        ai/services/hint_service.py               P2     3h           #6,#7,#13
16        Integrate explanations into 7 reasoning   P2     4h           #14
17        Integrate smarter hints into anagrams     P2     2h           #15
18        Integrate hints into puzzle_grid          P2     2h           #15
19        Extend theme wrap to remaining reasoning  P2     3h           #10,#12
──────── ─ Phase 2 Complete ─────────────────────────────────────────────────────
20        ai/services/semantic_service.py           P3     4h           #6,#7
21        Integrate semantic check: blood_relations P3     2h           #20
22        Integrate semantic check: anagrams        P3     2h           #20
23        Integrate semantic check: rankings        P3     2h           #20
24        Confidence threshold + "Did you mean?"    P3     2h           #20
──────── ─ Phase 3 Complete ─────────────────────────────────────────────────────
25        New game: Riddle Master                   P4     5h           #6,#7
26        New game: Reading Comprehension           P4     5h           #6,#7
27        Adaptive auto-explanations                P4     2h           #14
28        Personalized login greeting               P4     1h           #9
29        Menu [AI] badges + conditional visibility P4     2h           #1
──────── ─ Phase 4 Complete ─────────────────────────────────────────────────────
```

## Design Decisions (Locked)

| # | Decision | Choice |
|---|---|---|
| 1 | **Theme selection** | Fixed set: `mystery`, `sci-fi`, `sports`, `fantasy` — randomly selected per puzzle; no user prompt |
| 2 | **Explanation opt-in** | Show `"See explanation? (y/n):"` after wrong answer — AI only called on `y` |
| 3 | **Cache + user data** | Disk-based SQLite for AI cache (`ai_cache` table). Migrate all user data from `brain_trainer_data.json` → `brain_trainer.db` |
| 4 | **Semantic score** | Fuzzy semantic match awards **75% of base score** (rewards effort, preserves precision incentive) |
| 5 | **Dependencies** | Add `httpx` and `pydantic`. Gemini is primary provider in Phase 1. Ollama deferred to later phase. |
