# LifePilot — App Build Plan

> **Philosophy:** Build in thin vertical slices. Each milestone produces something you can actually open, click, and test. No "finish everything then test" — every phase ends with a working, observable state.

---

## How to read this document

Each phase has:
- **What gets built** — exact files
- **How it looks / what you can test** — what's visible and usable at that point
- **How to run it** — exact commands
- **Gate** — what must work before moving to the next phase

---

## Development workflow (every day)

```bash
# Terminal 1 — backend (always running while developing)
conda activate lifepilot
cd /Users/adarsh/Developer/Projects/lifepilot
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend (once Phase 3 starts)
cd electron
npm run dev

# Test the API at any time
curl http://localhost:8000/health
# Or open http://localhost:8000/docs  ← Swagger UI, test every endpoint interactively
```

The **Swagger UI at `/docs`** is your primary API test tool. Every endpoint is clickable, you can send requests and see responses without writing any test code.

---

## Phase 1 — Backend foundation + Goals API

### What gets built
```
backend/
├── __init__.py
├── main.py              ← FastAPI app, /health, mounts routers
├── config.py            ← loads ~/LifePilot/config.json (auto-creates if missing)
├── db/
│   ├── __init__.py
│   ├── database.py      ← engine, WAL mode, SessionLocal, Base
│   ├── models.py        ← Goal, Session, Thread ORM models
│   ├── goals.py         ← CRUD: create, versioned update, history, progress
│   ├── sessions.py      ← save_session, get_latest_session
│   └── threads.py       ← create, resolve, get_open
└── routers/
    ├── __init__.py
    └── goals.py         ← GET/POST/PUT /goals, PATCH /goals/{id}/progress
```

One missing package to install first:
```bash
conda run -n lifepilot pip install openai aiofiles python-multipart
```

### How to run
```bash
conda activate lifepilot
uvicorn backend.main:app --reload --port 8000
```

### What you can test
- `GET  http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:8000/docs` → Swagger UI with all Goals endpoints
- Create a goal → update it → check history shows 2 rows, 1 active
- `~/LifePilot/lifepilot.db` exists and has the correct tables (open with DB Browser for SQLite or `sqlite3`)

### Gate before Phase 2
- [ ] Server starts without errors
- [ ] `/health` returns 200
- [ ] Create + update a goal via Swagger, versioning works
- [ ] DB file created at `~/LifePilot/lifepilot.db`

---

## Phase 2 — LLM layer + `/chat` endpoint

### What gets built
```
backend/
└── llm/
    ├── __init__.py
    ├── base.py          ← LLMProvider ABC
    ├── gemini.py        ← GeminiProvider (from google import genai)
    ├── openai_compat.py ← OpenAICompatibleProvider (covers Ollama, Groq)
    └── factory.py       ← get_provider(config) → correct provider
```

Also: `~/LifePilot/config.json` needs your Gemini API key:
```json
{
  "provider": "gemini",
  "api_key": "YOUR_GEMINI_KEY",
  "model": "gemini-2.0-flash",
  "morning_time": "09:00",
  "evening_time": "21:00",
  "journal_dir": "~/LifePilot/journal",
  "db_path": "~/LifePilot/lifepilot.db"
}
```

### What you can test
- `POST /chat` via Swagger with `{"message": "Hello, who are you?"}` → get a real LLM response
- Swap `provider` in config.json to `"ollama"` + add `"base_url": "http://localhost:11434/v1"` → same endpoint, different model. No code change.

### Gate before Phase 3
- [ ] `/chat` returns a real Gemini response
- [ ] Changing provider in config.json works without restart (config reloaded per request)

---

## Phase 3 — Electron shell + Goals tab (first visual milestone)

### What gets built
```
electron/
├── package.json         ← electron, electron-builder
├── main.js              ← Tray icon, BrowserWindow popup, spawns FastAPI
├── preload.js           ← contextBridge (window.lifepilot.*)
└── renderer/
    ├── package.json     ← vite, react, react-dom
    ├── vite.config.js
    ├── index.html
    ├── index.jsx
    ├── App.jsx          ← tab bar: Goals | Calendar | Journal
    ├── tabs/
    │   └── Goals.jsx    ← list of goals + add/edit form
    └── components/
        └── GoalCard.jsx ← goal text, horizon badge, progress indicator, edit button
```

### How to run
```bash
# Terminal 1 — backend must be running
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd electron
npm install
cd renderer && npm install && cd ..
npm run dev    # starts Vite dev server + Electron together
```

### What it looks like at this point

```
┌─────────────────────────────────┐
│  Goals  │ Calendar │  Journal   │  ← tab bar
├─────────────────────────────────┤
│                                 │
│  Weekly                         │
│  ┌───────────────────────────┐  │
│  │ Close Acme proposal  [●]  │  │  ← on_track badge
│  │ week of Apr 7         ✏️  │  │
│  └───────────────────────────┘  │
│                                 │
│  Custom  · due Apr 20           │
│  ┌───────────────────────────┐  │
│  │ Finish pitch deck    [!]  │  │  ← at_risk badge
│  │                       ✏️  │  │
│  └───────────────────────────┘  │
│                                 │
│  + Add goal                     │
└─────────────────────────────────┘
```

Calendar and Journal tabs show "Coming soon" placeholder.

### What you can test
- Click menu bar icon → window pops up
- See real goals from SQLite (ones you added via Swagger in Phase 1)
- Click ✏️ → edit goal text → save → list refreshes
- Add a new goal → appears immediately
- Close window → reopen → data persists

### Gate before Phase 4
- [ ] Menu bar icon works, window opens/closes
- [ ] Goals list loads from real API
- [ ] Add + edit goal persists to DB
- [ ] App survives backend restart (reconnects automatically)

---

## Phase 4 — Evening journal session (first coaching milestone)

### What gets built
```
backend/
├── coach/
│   ├── __init__.py
│   ├── prompts.py       ← all system prompt strings
│   ├── context.py       ← build_evening_context(goals, threads, yesterday_summary)
│   └── evening.py       ← session state machine
└── routers/
    └── sessions.py      ← POST /session/start, POST /session/end, POST /session/chat

electron/renderer/
└── components/
    └── SessionOverlay.jsx  ← modal chat UI: message bubbles, text input, End Session button
```

Also: journal markdown writer → `~/LifePilot/journal/YYYY-MM-DD.md`

### What it looks like

```
┌─────────────────────────────────────────┐
│             Evening Check-in            │
├─────────────────────────────────────────┤
│  Coach: How was your day? Tell me       │
│         what's on your mind.            │
│                                         │
│  You:   Had a solid day. Finished the   │
│         proposal draft.                 │
│                                         │
│  Coach: Great — that's the weekly goal  │
│         almost done. What about the     │
│         pitch deck?                     │
│                                         │
│  You:   ▌  (typing...)                  │
├─────────────────────────────────────────┤
│  [  Type your message...          Send ]│
│  [        End Session                  ]│
└─────────────────────────────────────────┘
```

### What you can test
- Click "Evening Check-in" button → overlay opens
- Have a real text conversation with the coach (it knows your goals)
- Click "End Session" → summary generated → markdown file saved at `~/LifePilot/journal/`
- Open the journal file in any text editor to inspect it
- `GET /journal` in Swagger → lists saved sessions

### Gate before Phase 5
- [ ] Coach responds with goal-aware follow-ups
- [ ] Session saves to SQLite + markdown file
- [ ] Second session next day references yesterday's summary

---

## Phase 5 — STT (voice input)

### What gets built
```
backend/
├── stt/
│   ├── __init__.py
│   └── qwen_asr.py      ← Session wrapper, batch + streaming pipeline
└── routers/
    └── audio.py         ← POST /transcribe, WebSocket /ws/audio
```

Update `SessionOverlay.jsx`:
- Mic button → hold to record → release → text appears in input field
- Streaming mode: text appears word-by-word as you speak

### What you can test
- Click mic → speak → see transcription appear in the text box
- Send it as a message → coach responds
- Streaming: text updates live while speaking

### Gate before Phase 6
- [ ] Mic records, transcription appears
- [ ] Latency acceptable (< 3s for a normal sentence)
- [ ] Streaming shows text progressively

---

## Phase 6 — Calendar tab + AppleScript bridge

### What gets built
```
backend/
├── calendar/
│   ├── __init__.py
│   ├── applescript.py   ← read today/tomorrow events (with uid), create/move/delete
│   ├── parser.py        ← raw output → CalendarEvent Pydantic models
│   └── actions.py       ← CalendarAction schema, execute_action()
└── routers/
    └── calendar.py      ← GET /calendar/today, /tomorrow, POST /calendar/action

electron/renderer/
├── tabs/
│   └── Calendar.jsx     ← event list, free blocks, nudge cards
└── components/
    └── ConfirmCard.jsx  ← yes/no card for LLM-proposed changes
```

### What it looks like

```
┌─────────────────────────────────┐
│  Goals  │ Calendar │  Journal   │
├─────────────────────────────────┤
│  Monday, April 13               │
│                                 │
│  09:00  Standup (30m)           │
│  10:00  ── free 2h ──           │
│  12:00  Client call (1h)        │
│  13:00  ── free 1h ──           │
│  14:00  Design review (1h)      │
│                                 │
│  ⚠ No time blocked for          │
│    "pitch deck" today           │
└─────────────────────────────────┘
```

ConfirmCard (appears when coach proposes a change):
```
┌──────────────────────────────────────┐
│  Move "Client call" from 12pm → 2pm? │
│                                      │
│       [Confirm]      [Cancel]        │
└──────────────────────────────────────┘
```

### What you can test
- Calendar tab shows today's real Apple Calendar events
- In a session: say "move my 12pm call to 2pm" → ConfirmCard appears
- Click Confirm → event actually moves in Apple Calendar
- Click Cancel → nothing changes

**Safety:** AppleScript writes only run after you click Confirm. Never automatic.

### Gate before Phase 7
- [ ] Real calendar events appear in tab
- [ ] LLM can propose a move → ConfirmCard appears
- [ ] Confirm executes, Cancel does nothing
- [ ] macOS grants Calendar access permission (prompted on first run)

---

## Phase 7 — Morning session + full context

### What gets built
```
backend/coach/
├── morning.py           ← issue detection: conflicts, overloaded day, goal gaps
└── context.py           ← build_morning_context(goals, calendar, threads, yesterday_summary, issues)
```

Update session router to handle morning type.
Add "Morning Briefing" button to app.

### What it looks like

Coach opens with: *"Good morning. You've got 4 events today. There's a conflict at 2pm — your design review overlaps with the client call. Also, no time blocked for the pitch deck and the deadline is in 7 days. Want to fix the conflict first?"*

---

## Deployment (local Mac app)

### Dev mode (during development)
```bash
# Two terminals, both always open
uvicorn backend.main:app --reload --port 8000
cd electron && npm run dev
```

### Packaged app (when you want a real .app)
```bash
cd electron
npm run build        # builds React → dist/
npm run package      # electron-builder → produces LifePilot.app
# Output: electron/dist/mac/LifePilot.app
# Drag to /Applications or double-click to run
```

The packaged app:
- Spawns the Python backend automatically (bundled with PyInstaller or launched via conda)
- Appears in menu bar on login
- No terminal needed

> **Note:** Packaging the Python backend cleanly is a Phase 7+ task. During development, you always run the two terminals manually.

---

## Testing strategy at each phase

| Phase | What to test with |
|---|---|
| 1 | `http://localhost:8000/docs` (Swagger UI) |
| 2 | Swagger `/chat` endpoint |
| 3 | Real Electron window — click everything |
| 4 | Have an actual evening session |
| 5 | Hold mic, speak, watch transcription |
| 6 | Check Apple Calendar after a confirmed action |
| 7 | Have a real morning session |

No formal test suite needed during this phase — the app itself is the test. If something breaks visibly, fix it before moving on.

---

## File creation order (exact sequence)

```
Phase 1:
  backend/__init__.py
  backend/db/__init__.py
  backend/db/database.py
  backend/db/models.py
  backend/db/goals.py
  backend/db/sessions.py
  backend/db/threads.py
  backend/config.py
  backend/routers/__init__.py
  backend/routers/goals.py
  backend/main.py               ← last, imports everything above

Phase 2:
  backend/llm/__init__.py
  backend/llm/base.py
  backend/llm/gemini.py
  backend/llm/openai_compat.py
  backend/llm/factory.py
  → update backend/main.py to add /chat

Phase 3:
  electron/package.json
  electron/main.js
  electron/preload.js
  electron/renderer/package.json
  electron/renderer/vite.config.js
  electron/renderer/index.html
  electron/renderer/index.jsx
  electron/renderer/App.jsx
  electron/renderer/tabs/Goals.jsx
  electron/renderer/components/GoalCard.jsx

Phase 4:
  backend/coach/__init__.py
  backend/coach/prompts.py
  backend/coach/context.py
  backend/coach/evening.py
  backend/routers/sessions.py
  → update backend/main.py
  electron/renderer/components/SessionOverlay.jsx
  → update electron/renderer/App.jsx (add session button)

Phase 5:
  backend/stt/__init__.py
  backend/stt/qwen_asr.py
  backend/routers/audio.py
  → update backend/main.py
  → update SessionOverlay.jsx (mic button)

Phase 6:
  backend/calendar/__init__.py
  backend/calendar/applescript.py
  backend/calendar/parser.py
  backend/calendar/actions.py
  backend/routers/calendar.py
  → update backend/main.py
  electron/renderer/tabs/Calendar.jsx
  electron/renderer/components/ConfirmCard.jsx
  → update App.jsx

Phase 7:
  backend/coach/morning.py
  → update backend/coach/context.py
  → update backend/routers/sessions.py
```

---

*Start with Phase 1. Each phase is a shippable slice — never more than 1 phase ahead without testing what you have.*
