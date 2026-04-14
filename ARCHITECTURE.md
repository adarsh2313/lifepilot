# LifePilot — Technical Architecture Reference

> Deep-dive into every layer of the system as built through Phase 4.
> Written for a 30-minute manual review session.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Goals: Data Model & Structure](#2-goals-data-model--structure)
3. [LLM Layer: Providers, Context, Prompts](#3-llm-layer-providers-context-prompts)
4. [Evening Session: State Machine & Turn Handling](#4-evening-session-state-machine--turn-handling)
5. [Post-Processing: What Gets Saved, How, Where](#5-post-processing-what-gets-saved-how-where)
6. [Goal Updates from a Session](#6-goal-updates-from-a-session)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Config & Multi-Provider](#8-config--multi-provider)
9. [What's Missing / Deferred](#9-whats-missing--deferred)

---

## 1. System Overview

```
┌─────────────────────────────────────┐
│  Electron (menu bar popup)          │
│  React/Vite renderer                │
│  localhost — no internet exposure   │
│                                     │
│  App.jsx                            │
│  ├── tabs/Goals.jsx                 │
│  ├── tabs/Calendar.jsx  (stub)      │
│  ├── tabs/Journal.jsx   (stub)      │
│  └── components/                    │
│      ├── GoalCard.jsx               │
│      └── SessionOverlay.jsx         │
└────────────────┬────────────────────┘
                 │ HTTP fetch to :8000
┌────────────────▼────────────────────┐
│  FastAPI  (localhost:8000)          │
│                                     │
│  /goals        ← GoalsCRUD         │
│  /session/*    ← Evening coach     │
│  /chat         ← stateless LLM     │
│  /health                           │
│                                     │
│  backend/db/        SQLAlchemy      │
│  backend/llm/       LLM providers   │
│  backend/coach/     Session logic   │
└────────────────┬────────────────────┘
                 │
        ┌────────┴────────┐
        │  SQLite         │  lifepilot.db (project root)
        │  (WAL mode)     │
        └─────────────────┘
                 │
        ┌────────┴────────┐
        │  LLM API        │  Gemini / OpenAI / OpenRouter /
        │  (external)     │  Groq / Ollama / LM Studio
        └─────────────────┘
```

**Running in dev:**
```bash
# Terminal 1
uvicorn backend.main:app --reload --port 8000

# Terminal 2
cd electron && npm run dev   # starts Vite :5173 + Electron together
```

---

## 2. Goals: Data Model & Structure

### SQLite table: `goals`

File: `backend/db/models.py`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `text` | TEXT | the goal text |
| `horizon` | VARCHAR(20) | `weekly` \| `monthly` \| `custom` |
| `due_date` | VARCHAR(10) | YYYY-MM-DD, only for `custom` |
| `active` | BOOLEAN | only one version is active at a time |
| `progress` | VARCHAR(20) | `not_started` \| `in_progress` \| `at_risk` \| `achieved` \| `dropped` |
| `period` | VARCHAR(10) | ISO week string e.g. `"2024-W15"` or `"2024-04"` for monthly |
| `version` | INTEGER | starts at 1, increments on each edit |
| `parent_id` | INTEGER FK → goals.id | points to previous version's row |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Versioning strategy (immutable history)

`update_goal()` in `backend/db/goals.py`:
1. Fetch the active row for `goal_id`
2. Set `old.active = False` — deactivate it
3. Insert a new row with the new text, `version = old.version + 1`, `parent_id = old.id`
4. The new row is now the active version

**Result:** Every text edit creates a new row. You can always walk the `parent_id` chain to see the full history. `GET /goals/history/{id}` exposes this.

Progress updates (`PATCH /goals/{id}/progress`) are **in-place** — they mutate the existing active row because progress isn't a meaningful historical event.

### Context dict (what the LLM sees)

`build_goal_context()` in `backend/db/goals.py`:

```python
{
  "weekly":  [{"id": 1, "text": "...", "period": "2024-W15", "progress": "in_progress"}, ...],
  "monthly": [{"id": 2, "text": "...", "period": "2024-04",  "progress": "not_started"}, ...],
  "custom":  [{"id": 3, "text": "...", "due_date": "2024-04-20", "progress": "at_risk"}, ...]
}
```

Only active goals. IDs are included so the summary LLM call can reference them for goal updates.

### Goals API endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/goals` | All active goals |
| `GET` | `/goals/history/{id}` | Full version chain for a goal |
| `GET` | `/goals/context` | LLM-ready context dict |
| `POST` | `/goals` | Create new goal (`text`, `horizon`, `due_date?`) |
| `PUT` | `/goals/{id}` | Versioned text update |
| `PATCH` | `/goals/{id}/progress` | In-place progress update |

---

## 3. LLM Layer: Providers, Context, Prompts

### Provider abstraction

File: `backend/llm/base.py`

```python
class LLMProvider(ABC):
    async def chat(self, messages: list[dict], system: str) -> str: ...
    def provider_name(self) -> str: ...
```

`messages` is always `[{"role": "user"|"assistant", "content": "..."}]` — the full conversation history passed on every call. No sliding window, no truncation yet.

### Two concrete providers

**GeminiProvider** (`backend/llm/gemini.py`):
- Uses `from google import genai` + `genai.Client`
- Translates `"assistant"` → `"model"` in role field (Gemini's required naming)
- System prompt goes into `GenerateContentConfig(system_instruction=...)`
- `temperature=0.7`, `max_output_tokens=1024`
- SDK has no native async → runs in `asyncio.get_event_loop().run_in_executor(None, lambda: ...)`
- tenacity: 3 attempts, exponential backoff 1–10s

**OpenAICompatibleProvider** (`backend/llm/openai_compat.py`):
- Uses `AsyncOpenAI` — native async
- System prompt prepended as `{"role": "system", "content": system}` before messages
- `temperature=0.7`, `max_tokens=1024`
- tenacity: same 3-attempt retry

### Factory

File: `backend/llm/factory.py` — `get_provider(config: dict) → LLMProvider`

```
config["provider"]  →  which class + which base_url
  "gemini"          →  GeminiProvider
  "openai"          →  OpenAICompatibleProvider (no base_url)
  "openrouter"      →  OpenAICompatibleProvider(base_url="https://openrouter.ai/api/v1")
  "groq"            →  OpenAICompatibleProvider(base_url="https://api.groq.com/openai/v1")
  "ollama"          →  OpenAICompatibleProvider(base_url="http://localhost:11434/v1")
  "lmstudio"        →  OpenAICompatibleProvider(base_url="http://localhost:1234/v1")
  unknown           →  OpenAICompatibleProvider with explicit base_url from config
```

**Config is re-read on every request** — changing `config.json` takes effect immediately, no restart.

### What the evening LLM receives as context

File: `backend/coach/prompts.py` — `build_evening_system()`

The system prompt template (`EVENING_SYSTEM`) is:

```
You are LifePilot, a personal AI coach conducting an evening check-in session.
[coaching style instructions]

Current goals:
  [not_started] (id=1) Close Acme proposal
  [in_progress] (id=2) Finish pitch deck (due 2024-04-20)
  [not_started] (id=3) Exercise 3x this week

Open follow-up items:       ← from threads table (unresolved)
  - Follow up with Sarah about budget

Yesterday's summary:        ← one_line_summary from last evening session
  Made progress on proposal, pitch deck still blocked
```

Three dynamic blocks injected:
1. **Goals** — all active goals with their current progress and IDs
2. **Open threads** — unresolved follow-up items from previous sessions (max 5)
3. **Yesterday's summary** — extracted `one_line_summary` from the last saved session's JSON

**Calendar context (Phase 6, not yet built):** Will be added as a 4th block: today's events + free blocks, passed through `build_morning_context()` / `build_evening_context()`.

### Where prompts live

`backend/coach/prompts.py` — all three strings in one place:

| Constant | Used for |
|---|---|
| `EVENING_SYSTEM` | Template for the coaching system prompt (goals + threads + yesterday injected) |
| `SUMMARY_SYSTEM` | Short system prompt for the post-session summary call |
| `SUMMARY_PROMPT` | User-turn prompt sent to extract structured JSON from the transcript |
| `build_evening_system()` | Function that renders `EVENING_SYSTEM` with live data |

---

## 4. Evening Session: State Machine & Turn Handling

### Session lifecycle

```
POST /session/start
  └── build_evening_context(db)          ← goals + threads + yesterday
  └── build_evening_system(...)          ← renders system prompt
  └── stores {system, history, context} in _active_sessions[session_id]
  └── returns {session_id, opening_message: "Hey — how was your day?..."}

POST /session/chat  (repeated)
  └── appends {"role": "user", "content": message} to history
  └── calls provider.chat(history, system)   ← full history every time
  └── appends {"role": "assistant", "content": reply} to history
  └── returns {message: reply}

POST /session/end
  └── calls end_session(db, history, context)
  └── → generates summary (second LLM call)
  └── → applies goal updates to DB
  └── → creates open threads in DB
  └── → saves Session row to DB
  └── → writes markdown journal file
  └── pops session from _active_sessions
  └── returns {summary: {...}}
```

### Session state storage

**In-memory dict** in `backend/routers/sessions.py`:

```python
_active_sessions: dict[str, dict] = {}
# key: UUID session_id
# value: {
#   "system": "<rendered system prompt>",
#   "history": [{"role": ..., "content": ...}, ...],
#   "context": {"goals": ..., "open_threads": ..., "yesterday_summary": ...}
# }
```

This means:
- Sessions survive as long as the server is running
- Server restart loses an in-progress session (no persistence mid-session)
- One active session at a time is the expected usage — no conflict handling for multiple sessions

### Multi-turn context: how many turns?

**Unlimited turns** — the full `history` list is passed to `provider.chat()` on every call. The provider sends the entire conversation to the LLM each time.

**Current limits:**
- Gemini: `max_output_tokens=1024` per turn
- OpenAI compat: `max_tokens=1024` per turn
- No context window management — very long sessions could hit model token limits

**What will break first:** Gemini Flash has a 1M token context window, so this won't be an issue in practice for normal session lengths.

---

## 5. Post-Processing: What Gets Saved, How, Where

### When `POST /session/end` is called

File: `backend/coach/evening.py` → `end_session()`

**Step 1: Summary LLM call**

A second, separate LLM call is made with:
- System: `SUMMARY_SYSTEM` ("You are summarising a coaching session transcript...")
- User message: `SUMMARY_PROMPT` with the full transcript injected

The transcript is formatted as:
```
User: hey how was your day
Assistant: It sounds like you made progress on...
User: yeah, the proposal is done
...
```

The LLM is asked to return **strict JSON**:
```json
{
  "wins": ["Completed Acme proposal draft"],
  "blockers": ["Waiting on budget approval from Sarah"],
  "goal_updates": [
    {"goal_id": 1, "text": "Close Acme proposal", "new_progress": "achieved"}
  ],
  "open_threads": ["Follow up with Sarah about budget next week"],
  "one_line_summary": "Finished proposal draft, pitch deck still blocked on budget"
}
```

**JSON parsing:** The raw response is stripped of markdown fences (` ```json `) before `json.loads()`. If parsing fails, a fallback dict with `raw` key is used — session still saves, just without structured fields.

**Step 2: Goal progress updates**

For each item in `goal_updates` where `new_progress` is not null:
- Calls `update_goal_progress(db, goal_id, new_progress)`
- This is an **in-place mutation** of the active goal row
- Errors are silently swallowed (goal may have been versioned mid-session — non-fatal)

**Step 3: Thread creation**

For each string in `open_threads`:
- Calls `create_thread(db, ThreadCreate(text=thread_text))`
- No `goal_id` linkage — threads are free-floating at this point
- These threads will surface in the next session's system prompt

**Step 4: Session row saved to `sessions` table**

```python
SessionCreate(
  date=today,                          # "2024-04-14"
  session_type="evening",
  transcript=history,                  # full [{role, content}, ...] list → stored as JSON string
  summary=json.dumps(summary),         # the structured JSON → stored as JSON string
  goals_snapshot=context["goals"],     # the goals dict AT SESSION START → stored as JSON
  threads_snapshot=context["open_threads"]  # threads AT SESSION START → stored as JSON
)
```

The `goals_snapshot` and `threads_snapshot` are captured at session start, not end — they represent what the LLM knew going in, which is useful for later auditing.

**Step 5: Markdown journal file**

Written to: `{journal_dir}/{YYYY-MM-DD}.md`
`journal_dir` defaults to `{project_root}/journal/` (from `config.json`).

File format:
```markdown
# 2024-04-14 — Evening Check-in
*2024-04-14 21:15 UTC*

## Summary
> Finished proposal draft, pitch deck still blocked on budget

## Wins
- Completed Acme proposal draft

## Blockers
- Waiting on budget approval from Sarah

## Goal updates
- Close Acme proposal → achieved

## Follow-ups
- [ ] Follow up with Sarah about budget next week

## Transcript

**Coach**: Hey — how was your day?...
**You**: Had a good day...
```

---

## 6. Goal Updates from a Session

### The exact LLM call

In `end_session()`, the call is:

```python
summary_raw = await provider.chat(
    messages=[{"role": "user", "content": SUMMARY_PROMPT.format(transcript=transcript_text)}],
    system=SUMMARY_SYSTEM,
)
```

This is a **single-turn call** — not the coaching conversation. Fresh context, just the transcript as input.

### What triggers a goal update

The `SUMMARY_PROMPT` instructs the LLM:
> `goal_updates`: any goal whose progress changed (`new_progress` must be one of: `not_started`, `in_progress`, `at_risk`, `achieved`, `dropped` — or `null` if unchanged)

The LLM infers from the conversation whether the user indicated progress on any goal. It references goals by `goal_id` — which it knows because the goal IDs were included in the system prompt at session start.

### What actually changes in the DB

```
goal_updates[n].goal_id   → goals.id  (must be an active goal)
goal_updates[n].new_progress → goals.progress  (in-place write)
```

**This is NOT a versioned update.** Progress is a mutable signal — it's updated in place on the current active row. If you want to update the goal's *text* (e.g. user reframed the goal during conversation), that's not handled yet — it would need to go through `update_goal()` which creates a new version.

### What does NOT happen automatically

- Goal text is never changed by the LLM
- Goals are never created by the LLM
- Goals are never deactivated/dropped by the LLM (even if `new_progress = "dropped"` — that only updates the `progress` field, it doesn't set `active = False`)

---

## 7. Frontend Architecture

### Component tree

```
App.jsx
├── state: activeTab, sessionOpen
├── Tab bar (Goals / Calendar / Journal)
├── Tab content:
│   ├── Goals.jsx          (activeTab === 'Goals')
│   ├── "Coming soon"      (Calendar)
│   └── "Coming soon"      (Journal)
├── Footer: "Evening Check-in" button
└── SessionOverlay.jsx     (rendered full-screen when sessionOpen)
```

### Goals.jsx — data flow

```
mount → GET /goals → setGoals([...])
                  └── groups by horizon: weekly / monthly / custom
                  └── renders GoalCard for each

add goal → POST /goals → reload
edit goal → PUT /goals/{id} → reload
progress change → PATCH /goals/{id}/progress → optimistic local update (no reload)

backend down? → auto-retry every 3s (setInterval)
```

**API abstraction:** `getApi()` checks for `window.lifepilot` (Electron preload contextBridge) first, falls back to direct `fetch` calls. This means the Goals tab works in both Electron and plain browser.

### GoalCard.jsx — inline editing

- Click ✏️ → sets `editing=true` → shows `<input>` with current text
- Enter or Save → calls `onUpdate(id, newText)` → parent reloads from API
- Escape or ✕ → cancels, restores draft to original text
- Progress `<select>` → calls `onProgressChange(id, newValue)` → optimistic state update

### SessionOverlay.jsx — chat UI

```
mount → POST /session/start → stores session_id, renders opening message

user types → Enter (not Shift+Enter) → POST /session/chat
                                     → appends user bubble
                                     → shows "..." typing indicator
                                     → appends coach bubble on response

"End Session" button → POST /session/end
                     → replaces chat UI with summary card
                     → shows wins / blockers / follow-ups
                     → "Close" button → onClose() → back to main app
```

**Error handling:** If `/session/start` fails (backend not running), error is shown inline. Mid-session API errors show as a coach message bubble with the error text.

---

## 8. Config & Multi-Provider

File: `backend/config.py`

Config lives at `{project_root}/config.json`. Auto-created if missing.

```json
{
  "provider": "gemini",
  "api_key": "AIza...",
  "model": "gemini-2.5-flash-preview-04-17",
  "morning_time": "09:00",
  "evening_time": "21:00",
  "journal_dir": "/path/to/project/journal",
  "db_path": "/path/to/project/lifepilot.db"
}
```

To switch providers, change `config.json` only — **no code change, no restart**:

| Target | `provider` | `api_key` | `model` | `base_url` |
|---|---|---|---|---|
| Gemini | `"gemini"` | Gemini key | e.g. `gemini-2.5-flash-preview-04-17` | — |
| OpenAI | `"openai"` | OpenAI key | e.g. `gpt-4o` | — |
| OpenRouter | `"openrouter"` | OR key | any OR model slug | — |
| Groq | `"groq"` | Groq key | e.g. `llama-3.3-70b-versatile` | — |
| Ollama | `"ollama"` | `""` | local model name | `http://localhost:11434/v1` |
| LM Studio | `"lmstudio"` | `"none"` | model name | `http://localhost:1234/v1` |

---

## 9. What's Missing / Deferred

| Area | Status | Notes |
|---|---|---|
| **Calendar context in sessions** | Phase 6 | `build_evening_context()` has no calendar block yet; it will be added as a 4th injection into `build_evening_system()` |
| **Morning session** | Phase 7 | `context.py` will get `build_morning_context()` with calendar + issue detection |
| **STT (voice input)** | Phase 5 | `backend/stt/qwen_asr.py` not built; SessionOverlay has no mic button yet |
| **Goal text update via LLM** | Not planned | LLM can only update `progress`, not `text`; text changes require explicit user action via ✏️ |
| **Context window management** | Not built | Full history sent every turn; could hit limits on very long sessions |
| **Mid-session server restart** | Data lost | In-memory session store only; no persistence of in-progress sessions |
| **Thread ↔ goal linkage from sessions** | Partial | `create_thread()` called with no `goal_id`; threads are free-floating after a session |
| **Automatic goal `active=False` on drop** | Not built | `new_progress="dropped"` only updates the progress field, doesn't deactivate the goal |
| **Electron auto-spawns backend** | Not built | Dev requires two manual terminals; packaging (Phase 7+) will bundle PyInstaller |
| **`preload.js` contextBridge** | Written but untested | `window.lifepilot.*` methods exist; Goals.jsx falls back to direct fetch so it works either way |
