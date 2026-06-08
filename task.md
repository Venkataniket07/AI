# AI Integration Tasks

### Design Decisions (Locked)
| # | Decision |
|---|---|
| 1 | **Themes**: Fixed set — `mystery`, `sci-fi`, `sports`, `fantasy` (random per puzzle) |
| 2 | **Explanation**: `y/n` prompt after wrong answer; AI only called on `y` |
| 3 | **Storage**: Single `brain_trainer.db` SQLite. Migrate JSON user data. AI cache in same DB. |
| 4 | **Semantic score**: Fuzzy match = 75% of base score |
| 5 | **Deps**: `httpx` + `pydantic`. Gemini as Phase 1 primary. Ollama deferred. |

---

## Phase 1: Infrastructure + No-Risk AI (Week 1-2)

### 1A — Database Migration
- [x] Rewrite `database/db_manager.py` to use SQLite (`brain_trainer.db`) via `sqlite3`
- [x] Migrate schema: `users` and `game_sessions` tables with same fields
- [x] Add `ai_cache` table to `brain_trainer.db` (key, value, created_at, ttl)
- [x] Migrate existing data from `brain_trainer_data.json` → SQLite on first run
- [x] Remove `brain_trainer_data.json` dependency

### 1B — AI Module Skeleton
- [x] Create `ai/__init__.py`, `ai/providers/__init__.py`, `ai/services/__init__.py`, `ai/prompts/`
- [x] Create `ai_config.json` with Gemini + Ollama stubs (Ollama disabled)
- [x] Implement `ai/config.py` (reads `ai_config.json`, validates, exposes typed config)
- [x] Implement `ai/schemas.py` (Pydantic: `ThemedPuzzle`, `Explanation`, `HintResponse`, `SemanticMatch`)
- [x] Implement `ai/cache.py` (SQLite-backed, TTL-aware, key = hash of prompt+schema)

### 1C — Providers
- [x] Implement `ai/providers/base.py` (abstract `BaseProvider`)
- [x] Implement `ai/providers/gemini.py` (httpx POST, structured JSON output, API key from config)
- [x] Implement `ai/providers/openrouter.py` (OpenAI-compatible format, fallback)
- [ ] Implement `ai/providers/ollama.py` — **deferred to later phase**

### 1D — Router + Services
- [x] Implement `ai/router.py` (priority routing table, fallback chain, 8s/10s timeouts)
- [x] Add prompt templates: `ai/prompts/theme_wrap.txt`, `ai/prompts/session_summary.txt`
- [x] Implement `ai/services/theme_service.py` (`wrap_puzzle_in_theme`, fixed themes)
- [x] Implement `ai/services/summary_service.py` (`summarize_session`)

### 1E — Integration
- [x] Integrate theme wrapping into `games/reasoning/seating.py`
- [x] Integrate session summary into `main.py` (post-game, silent fallback)

### 1F — Dependencies & Testing
- [x] Add `httpx` and `pydantic` to `requirements.txt`
- [ ] Unit tests: Gemini provider, router fallback, config loader
- [ ] Verify: AI failure is silent; game behaves identically with `ai_enabled: false`

---

## Phase 2: Explanation + Hint Layer (Week 3-4)
- [ ] Create prompt templates: `explain.txt`, `hint.txt`
- [ ] Implement `ai/services/explain_service.py`
- [ ] Implement `ai/services/hint_service.py`
- [ ] Integrate `y/n` explanation prompt into all 7 reasoning games after wrong answer
- [ ] Replace Anagram hint #2 with AI contextual hint (hint #1 stays deterministic)
- [ ] Add hint option to Puzzle Grid game
- [ ] Extend theme wrapping to: Blood Relations, Direction, Rankings, Puzzle Grid, Syllogisms

---

## Phase 3: Semantic Assistant Layer (Week 5-6)
- [ ] Create prompt template: `semantic_match.txt`
- [ ] Implement `ai/services/semantic_service.py`
- [ ] Integrate semantic check into Blood Relations (replace exact match)
- [ ] Integrate semantic near-miss into Anagrams
- [ ] Integrate free-text ranking into Rankings
- [ ] Implement confidence threshold (≥0.85 = accept at 75% score; 0.5–0.84 = "Did you mean?")

---

## Phase 4: Adaptive & Personalized Layer (Week 7-8)
- [ ] New game: **Riddle Master** (AI-generated riddle + hints + schema validation)
- [ ] New game: **Reading Comprehension** (AI passage + 3 MCQ, deterministic scoring)
- [ ] Adaptive auto-explanation after 3 consecutive wrong answers
- [ ] Personalized login greeting from recent stats
- [ ] Theme preference learning (track user's played themes)
- [ ] Menu `[AI]` badge + hide AI games if AI fully offline
