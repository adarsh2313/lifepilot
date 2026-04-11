# LifePilot — Technical Build Document

> **Approach:** Notebooks first. Each phase is a self-contained Jupyter notebook you can run and test end-to-end before any code moves into the app. Once a phase is validated, Claude Code uses the notebook as the reference implementation to build the corresponding app module.

---

## 1. Environment

### Conda Environment: `lifepilot`

**Already installed (confirmed):**
```
fastapi 0.135.2        ← backend API
uvicorn 0.42.0         ← ASGI server
starlette 1.0.0        ← FastAPI dependency
sqlalchemy 2.0.48      ← ORM / SQLite
pydantic 2.12.5        ← data validation
google-genai 1.68.0    ← Gemini LLM
pyaudio 0.2.14         ← mic capture
websockets 16.0        ← real-time audio streaming
httpx 0.28.1           ← async HTTP client
tenacity 9.1.4         ← retry logic for LLM calls
ipython 9.11.0         ← notebook kernel
jupyter_client 8.8.0   ← notebook support
python-dateutil 2.9.0  ← date parsing
```

**Still needs to be installed:**
```bash
conda run -n lifepilot pip install \
  nemo_toolkit[asr]           # Nvidia Canary STT (NeMo framework)
  soundfile                   # WAV read/write
  numpy                       # audio array handling
  openai                      # OpenAI-compatible adapter (also covers Ollama)
  anthropic                   # Claude adapter (optional)
  python-multipart            # FastAPI file uploads (WAV chunks)
  aiofiles                    # async file writes (journal markdown)
  rich                        # pretty notebook output
```

> **Note on Canary/NeMo:** `nemo_toolkit[asr]` is heavy (~2GB). Install it in the notebook phase and verify it runs on your Mac before committing to it. If it proves too slow or painful on Mac CPU, the fallback is `faster-whisper` (lighter, easier to install). I'll note this in the STT notebook.

### Activating the environment
```bash
conda activate lifepilot
jupyter notebook    # for notebook phases
uvicorn backend.main:app --reload  # for backend dev
```

---

## 2. Project Working Tree

### Directory layout — what lives where

```
/Users/adarsh/Developer/Projects/lifepilot/    ← git repo root
│
├── notebooks/                  ← Phase notebooks (run these first)
│   ├── 01_llm_abstraction.ipynb
│   ├── 02_stt_canary.ipynb
│   ├── 03_database_goals.ipynb
│   ├── 04_evening_journal_session.ipynb
│   ├── 05_calendar_applescript.ipynb
│   ├── 06_morning_session.ipynb
│   └── 07_context_assembly.ipynb
│
├── backend/                    ← Python FastAPI app (built from notebooks)
│   ├── main.py                 ← FastAPI app, mounts all routers
│   ├── config.py               ← loads ~/LifePilot/config.json
│   ├── llm/
│   │   ├── base.py             ← LLMProvider abstract class
│   │   ├── gemini.py           ← GeminiProvider
│   │   ├── openai_compat.py    ← OpenAI / Ollama / Groq / LM Studio
│   │   ├── anthropic.py        ← Claude (optional)
│   │   └── factory.py          ← reads config → returns provider instance
│   ├── stt/
│   │   ├── canary.py           ← Nvidia Canary wrapper
│   │   └── audio.py            ← WAV capture, chunking, temp file handling
│   ├── calendar/
│   │   ├── applescript.py      ← all osascript calls
│   │   ├── parser.py           ← raw AppleScript output → Python dicts
│   │   └── actions.py          ← create / move / delete with JSON schema
│   ├── coach/
│   │   ├── context.py          ← assembles system prompt from goals+calendar+threads
│   │   ├── morning.py          ← morning PA session state machine
│   │   ├── evening.py          ← evening journal session state machine
│   │   └── prompts.py          ← all raw prompt strings (no logic here)
│   └── db/
│       ├── database.py         ← SQLAlchemy engine + session factory
│       ├── models.py           ← ORM models: Goal, Session, Thread
│       ├── goals.py            ← goals CRUD (versioned)
│       ├── sessions.py         ← session CRUD
│       └── threads.py          ← threads CRUD
│
├── electron/                   ← Electron + React frontend
│   ├── package.json
│   ├── main.js                 ← menu bar, BrowserWindow, notifications, IPC
│   ├── preload.js              ← contextBridge — exposes safe IPC to renderer
│   └── renderer/               ← React app (compiled into electron/dist/)
│       ├── index.html
│       ├── index.jsx
│       ├── App.jsx
│       ├── tabs/
│       │   ├── Goals.jsx       ← Tab 1
│       │   ├── Calendar.jsx    ← Tab 2
│       │   └── Journal.jsx     ← Tab 3 (calendar grid)
│       └── components/
│           ├── SessionOverlay.jsx
│           ├── ConfirmCard.jsx
│           ├── GoalCard.jsx
│           ├── JournalEntry.jsx
│           └── EventList.jsx
│
├── ROADMAP.md                  ← product roadmap (edit freely)
├── TECHNICAL.md                ← this file
├── .gitignore
└── environment.yml             ← conda env export (for reproducibility)

~/LifePilot/                    ← USER DATA — outside repo, never committed
├── config.json                 ← LLM provider, API keys, notification times
├── lifepilot.db                ← SQLite database
└── journal/
    ├── 2026-04-11.md
    └── 2026-04-10.md
```

### What goes in git vs what doesn't

**Tracked (in repo):**
- All source code (`backend/`, `electron/`, `notebooks/`)
- `ROADMAP.md`, `TECHNICAL.md`
- `environment.yml`
- `.gitignore`
- `electron/package.json`, `electron/package-lock.json`

**Not tracked (in `.gitignore`):**
```
# User data — never commit
~/LifePilot/
*.db
config.json

# Python
__pycache__/
*.pyc
.ipynb_checkpoints/
*.egg-info/

# Node
node_modules/
electron/dist/
electron/renderer/dist/

# Model weights (downloaded on first run)
models/

# OS
.DS_Store
```

### Git setup
```bash
cd /Users/adarsh/Developer/Projects/lifepilot
git init
git add .gitignore ROADMAP.md TECHNICAL.md
git commit -m "init: project skeleton and docs"
```

**Branch strategy (simple — solo project):**
- `main` — always working, notebook-validated code
- `phase/N-name` — feature branch per phase (e.g. `phase/1-llm`, `phase/3-goals`)
- Merge to main when notebook passes end-to-end test

---

## 3. Notebook Phases — Run Order & What Each Tests

Notebooks live in `notebooks/`. Each is self-contained — run cells top to bottom. At the end of each notebook, there is an **"End-to-End Test"** cell that exercises the full flow for that phase.

### Phase 1: `01_llm_abstraction.ipynb`

**Goal:** Prove the LLM abstraction layer works with Gemini (and mock-test the OpenAI adapter).

**Cells:**
1. Install check — verify `google-genai` is importable
2. Define `LLMProvider` abstract base class
3. Implement `GeminiProvider` — `async def chat(messages, system) -> str`
4. Load config from a test dict (no file I/O yet)
5. Test: single-turn chat — send "Hello, are you working?" → print response
6. Test: multi-turn chat — 3 messages, verify context maintained
7. Test: system prompt injection — pass a coach persona, verify it affects response
8. Retry logic with `tenacity` — simulate a 429 rate limit error, verify retry works
9. `OpenAICompatibleProvider` stub — shows the interface, real test in later phase
10. **End-to-end test:** Factory function reads a config dict → returns correct provider → sends a coaching-style message → prints response

**What you're validating:** The abstraction works. Swapping providers is one config line.

---

### Phase 2: `02_stt_canary.ipynb`

**Goal:** Prove Nvidia Canary transcribes audio locally on your Mac.

**Cells:**
1. Install check — `nemo_toolkit`, `soundfile`, `numpy`
2. Download and load Canary model (first run: downloads weights, subsequent runs: loads from cache)
3. Record 5 seconds of audio from mic using `pyaudio` → save as temp WAV
4. Transcribe the WAV → print transcript
5. Measure transcription latency (target: <3 seconds for 30-second audio on Mac CPU)
6. Test with a pre-recorded WAV file (include a sample in `notebooks/fixtures/`)
7. Fallback test: if NeMo fails on Mac, try `faster-whisper` as drop-in replacement
8. **End-to-end test:** Record yourself saying a sentence → transcribe → verify accuracy

**What you're validating:** Canary runs locally. Latency is acceptable. If not, you have a fallback path.

> **Decision gate:** If Canary latency is >5 seconds on your Mac for 30s of speech, switch to `faster-whisper`. Note the decision in the notebook and update `TECHNICAL.md`.

---

### Phase 3: `03_database_goals.ipynb`

**Goal:** Prove the SQLite schema, versioned goals, and all CRUD operations work correctly.

**Cells:**
1. SQLAlchemy setup — create in-memory SQLite for testing (`:memory:`)
2. Define models: `Goal`, `Session`, `Thread`
3. Create tables
4. Goals CRUD:
   - Create weekly goal — week of 2026-04-07
   - Update it (creates new record, old → `active=False`)
   - Verify history: 2 records exist, only 1 is active
   - Create monthly goal for April 2026
   - Create custom goal with `target_date = 2026-04-20`
5. Query active goals across all horizons → print as dict (this is what the coach receives)
6. Query goal history for weekly → show all versions chronologically
7. Session CRUD:
   - Insert a session (type=evening, transcript, summary, goal_signals)
   - Query yesterday's summary
8. Thread CRUD:
   - Create a thread (unresolved)
   - Mark it resolved
   - Query open threads < 7 days old
9. **End-to-end test:** Simulate a full week — create goal Monday → update Wednesday → check history → verify context dict looks right

**What you're validating:** Schema is correct. Versioning works. Goal context dict is exactly what you'd pass to the LLM.

---

### Phase 4: `04_evening_journal_session.ipynb`

**Goal:** Prove the full evening journal session works — from context assembly through to saved markdown.

**Cells:**
1. Load goals from Phase 3 DB (or create test fixtures inline)
2. Assemble evening session system prompt:
   ```python
   system = build_evening_context(
       goals=active_goals,
       threads=open_threads,
       yesterday_summary="Had a design review, client responded well...",
       today_calendar=[]   # empty for evening (no calendar yet)
   )
   print(system)   # inspect what the LLM will receive
   ```
3. Simulate Phase 1 — free-talk. Send a mock user message (or use real mic):
   - User: "Had a busy day, the client call ran long but went well."
   - Coach asks one follow-up based on what was said + goals
4. Simulate Phase 2 — coach generates 2-3 targeted follow-up questions based on:
   - What the user said in Phase 1
   - Active goals
   - (Later: calendar events)
5. Simulate full 5-turn conversation with mock inputs
6. Extract goal progress signals from transcript using LLM:
   - Prompt: "From this conversation, rate each goal: moved / stalled / not_discussed"
   - Returns structured JSON
7. Generate first-person AI summary from transcript
8. Save to markdown: `~/LifePilot/journal/YYYY-MM-DD.md`
9. Save to SQLite: sessions table
10. Update goal progress signals in goals table
11. **End-to-end test:** Run full simulated session → markdown file created → SQLite updated → re-read and print both

**What you're validating:** The two-phase journal prompt works. First-person summary reads naturally. Everything saves correctly.

---

### Phase 5: `05_calendar_applescript.ipynb`

**Goal:** Prove Apple Calendar read and write via AppleScript works reliably.

**Cells:**
1. Run a basic AppleScript from Python:
   ```python
   import subprocess
   result = subprocess.run(['osascript', '-e', 'return "hello from applescript"'],
                          capture_output=True, text=True)
   print(result.stdout)
   ```
2. Read today's events from Apple Calendar → raw AppleScript output
3. Parse raw output → list of Python dicts: `{title, start, end, duration, location}`
4. Read tomorrow's events
5. Detect conflicts: find overlapping events in the list
6. Detect gaps: find free blocks > 30 minutes
7. Serialize events to JSON string (this is what gets injected into the LLM context)
8. **Write operations** (each tested separately):
   - Create a test event: "LifePilot Test — DELETE ME" at a safe time
   - Verify it appears in Calendar
   - Move the event 1 hour later
   - Verify it moved
   - Delete the event
   - Verify it's gone
9. LLM action parsing: given a voice command, LLM returns structured JSON:
   ```json
   {
     "action": "move",
     "event_title": "Client Call",
     "current_time": "2026-04-11T14:00:00",
     "new_time": "2026-04-11T16:00:00"
   }
   ```
   Parse this JSON → call the right AppleScript function
10. **End-to-end test:** Say "move my 3pm to 4pm" → transcript → LLM action JSON → AppleScript executes → verify in Calendar

**What you're validating:** AppleScript bridge is solid. Write operations work safely. JSON action parsing is reliable.

> **Safety note:** Write operations in the notebook create/delete a clearly named test event. Never touch real events until you've confirmed the parsing is accurate.

---

### Phase 6: `06_morning_session.ipynb`

**Goal:** Prove the morning PA session works — calendar-aware, goal-aware, with agentic write capability.

**Cells:**
1. Load calendar (from Phase 5), goals (from Phase 3)
2. Detect issues to surface:
   - Conflicts (overlapping events)
   - Goal gaps (no time blocked for weekly goal work)
   - Unfinished items from yesterday's session (from SQLite)
   - Overloaded day (>6 hours scheduled)
3. Assemble morning system prompt:
   ```python
   system = build_morning_context(
       goals=active_goals,
       calendar=today_events,
       tomorrow_calendar=tomorrow_events,
       yesterday_summary=last_session_summary,
       threads=open_threads,
       detected_issues=issues
   )
   print(system)
   ```
4. Simulate morning session — 4 turns:
   - Coach briefs today's calendar
   - Coach flags a conflict
   - User says "move the standup to 9:30"
   - LLM returns action JSON → show confirmation card text
   - Simulate user confirming → AppleScript executes
5. Coach nudges on goal not covered by today's calendar
6. Session ends → summary saved
7. **End-to-end test:** Full simulated morning session with 2 calendar edits → both confirmed → both executed → session summary saved

**What you're validating:** Morning context is rich and accurate. Agentic loop works. Coach is genuinely useful, not just informational.

---

### Phase 7: `07_context_assembly.ipynb`

**Goal:** Stress-test the context assembler. Verify token counts, prompt caching behaviour, and edge cases.

**Cells:**
1. Generate a context with maximum realistic data:
   - 5 active goals
   - 8 calendar events
   - 3 open threads
   - 500-word yesterday summary
2. Count tokens in the assembled system prompt (use `tiktoken` or Gemini's count_tokens API)
3. Verify it fits within model context limits with room for a 15-minute conversation
4. Test edge cases:
   - No goals set → coach handles gracefully
   - No calendar events → morning session still works
   - No yesterday summary → coach adapts opening
   - Very long previous transcript → truncation strategy
5. Prompt caching test: send same system prompt twice → verify Gemini uses cached version (check response latency + billing tokens)
6. **End-to-end test:** All edge cases pass. Token count is within budget for all session types.

**What you're validating:** Context assembly is robust. No surprises when the app is running for real.

---

## 4. Backend Architecture (FastAPI)

### API Endpoints

```
GET  /health                    ← status check, used by Electron on startup

POST /chat                      ← send a message turn during a session
     body: { session_id, message, type }
     returns: { response: str, action?: CalendarAction }

POST /transcribe                ← send WAV audio, get transcript
     body: multipart WAV file
     returns: { transcript: str }

POST /session/start             ← assemble context, create session record
     body: { type: morning|evening|dropin }
     returns: { session_id, opening_message: str }

POST /session/end               ← finalise session
     body: { session_id, transcript }
     returns: { summary: str, goal_signals: [...] }

GET  /goals                     ← all active goals
GET  /goals/history             ← full history
POST /goals                     ← create or update a goal (versioned)

GET  /calendar/today            ← today's Apple Calendar events
GET  /calendar/tomorrow         ← tomorrow's events
POST /calendar/action           ← execute a confirmed calendar action
     body: CalendarAction JSON

GET  /journal                   ← list of sessions (date + summary)
GET  /journal/:date             ← single entry (summary + transcript)

GET  /config                    ← read ~/LifePilot/config.json
POST /config                    ← update config
```

### Session State

Sessions are stateful during their lifetime. State is held **in memory** in the FastAPI process (not in SQLite) — SQLite only gets written at session end.

```python
# In-memory session store (dict keyed by session_id)
active_sessions: dict[str, SessionState] = {}

@dataclass
class SessionState:
    session_id: str
    type: Literal["morning", "evening", "dropin"]
    system_prompt: str          # assembled once at session start
    messages: list[dict]        # rolling transcript [{role, content}]
    calendar_actions: list      # actions taken this session
    started_at: datetime
```

When `POST /session/end` is called:
1. Full transcript assembled from `messages`
2. AI summary generated (first-person)
3. Goal signals extracted
4. Written to SQLite + markdown file
5. `active_sessions[session_id]` deleted

### Communication — Electron ↔ FastAPI

Electron uses `fetch()` (HTTP) for all non-audio communication and `WebSocket` for audio streaming during STT.

```
Audio path:    Electron mic → WebSocket ws://localhost:8000/ws/audio → Canary → transcript → HTTP response
All other:     Electron → HTTP fetch → FastAPI → JSON response
```

FastAPI binds to `localhost:8000` only. Not exposed to the network.

---

## 5. Frontend Architecture (Electron + React)

### Electron Process Model

```
Main process (main.js)
│
├── Creates Tray (menu bar icon)
├── Creates BrowserWindow (main app window)
├── Schedules notifications (node-cron or setTimeout)
├── IPC handlers: receives messages from renderer
│   ├── 'start-session'    → shows session overlay
│   ├── 'confirm-action'   → forwards yes/no to backend
│   └── 'open-journal'     → switches to journal tab
└── Spawns/monitors FastAPI backend process on startup

Renderer process (React app in BrowserWindow)
│
├── App.jsx             ← tab state, global context
├── Goals.jsx           ← fetches GET /goals, renders GoalCards
├── Calendar.jsx        ← fetches GET /calendar/today, renders EventList
├── Journal.jsx         ← fetches GET /journal, renders calendar grid
└── SessionOverlay.jsx  ← manages session lifecycle, mic, WebSocket
```

### IPC Bridge (`preload.js`)

```javascript
// preload.js — only expose what the renderer needs
contextBridge.exposeInMainWorld('lifepilot', {
  startSession:    (type) => ipcRenderer.invoke('start-session', type),
  endSession:      (id)   => ipcRenderer.invoke('end-session', id),
  confirmAction:   (id, action, confirmed) => ipcRenderer.invoke('confirm-action', {id, action, confirmed}),
  onNotification:  (cb)   => ipcRenderer.on('notification-fired', cb),
})
```

Renderer calls `window.lifepilot.startSession('evening')` — never touches `ipcRenderer` directly.

### React State

```
App-level state (React Context):
  - activeTab: 'goals' | 'calendar' | 'journal'
  - sessionActive: boolean
  - sessionId: string | null
  - sessionType: 'morning' | 'evening' | 'dropin' | null

Per-tab state:
  Goals.jsx    → goals list, editing state per goal
  Calendar.jsx → today's events, tomorrow's events, nudge cards
  Journal.jsx  → selected date, entry data, search query
  
SessionOverlay.jsx (modal, above everything):
  → messages: [{role, content}]
  → isRecording: boolean
  → pendingAction: CalendarAction | null  (shows ConfirmCard when set)
  → waveformData: Float32Array
```

### Frontend Build Tool

```
electron/
  package.json        ← Electron + React deps
  main.js             ← Electron main process (plain JS)
  preload.js          ← contextBridge
  renderer/
    package.json      ← Vite + React
    vite.config.js    ← bundles React → electron/renderer/dist/
    index.html
    index.jsx
    ...components
```

**Why Vite over webpack:** Faster HMR, simpler config, works well with Electron. The renderer is a Vite React app that outputs to `electron/renderer/dist/`. Electron's `main.js` loads `file:// electron/renderer/dist/index.html`.

---

## 6. Database — SQLite

**Location:** `~/LifePilot/lifepilot.db` — outside the repo, user-owned.

**ORM:** SQLAlchemy 2.0 (already installed) with the declarative base pattern.

**Connection:** Single SQLite file, WAL mode enabled for concurrent reads during sessions.

```python
# backend/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DB_PATH = os.path.expanduser("~/LifePilot/lifepilot.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
engine.execute("PRAGMA journal_mode=WAL")  # enable WAL mode

SessionLocal = sessionmaker(bind=engine)
```

**Full schema:**

```sql
-- Goals (versioned — never overwrite, always append)
CREATE TABLE goals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    horizon      TEXT NOT NULL,          -- weekly / monthly / custom
    text         TEXT NOT NULL,
    target_date  DATE,                   -- custom goals only
    week_start   DATE,                   -- weekly goals (ISO Monday)
    month        TEXT,                   -- monthly goals (YYYY-MM)
    created_at   DATETIME NOT NULL,
    active       BOOLEAN DEFAULT TRUE,
    progress     TEXT DEFAULT 'on_track' -- on_track / at_risk / achieved / carried_forward
);

-- Sessions (one per morning/evening/dropin interaction)
CREATE TABLE sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT NOT NULL,          -- YYYY-MM-DD
    type             TEXT NOT NULL,          -- morning / evening / dropin
    transcript       TEXT,                   -- full conversation verbatim
    summary          TEXT,                   -- first-person AI summary
    goal_signals     TEXT,                   -- JSON: [{goal_id, signal}]
    calendar_actions TEXT,                   -- JSON: [CalendarAction]
    created_at       DATETIME NOT NULL
);

-- Threads (unresolved topics that resurface across sessions)
CREATE TABLE threads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_date  DATE NOT NULL,
    description   TEXT NOT NULL,
    resolved      BOOLEAN DEFAULT FALSE,
    last_surfaced DATE
);
```

---

## 7. Journal Files — Markdown

**Location:** `~/LifePilot/journal/YYYY-MM-DD.md`

**Format:**
```markdown
# April 11, 2026

## Summary
Today I had a productive design review where the client responded well to the
new direction. The client call at 2pm ran long but ended positively — I'm
close to closing the proposal. I didn't make progress on the pitch deck and
want to block time for it tomorrow morning.

## Goals
- Weekly (Close 2 proposals): moved — one proposal nearly closed
- Custom (Pitch deck by Apr 20): stalled — no time spent today

## Full Transcript
Coach: How was your day? Tell me whatever's on your mind.
Me: Had a busy one. The design review went really well...
Coach: You mentioned the client call — how did that go?
Me: It ran longer than expected but in a good way...
```

Written with `aiofiles` (async) at session end. Also readable in any text editor without the app.

---

## 8. STT — Nvidia Canary

**Model source:** HuggingFace — `nvidia/canary-1b` (or Qwen 2.5B variant)
**Framework:** NVIDIA NeMo (`nemo_toolkit[asr]`)
**Runs:** Locally on Mac CPU (MPS acceleration if available)

**Model cache location:** `~/LifePilot/models/canary/` (outside repo)

**Wrapper interface:**
```python
# backend/stt/canary.py
class CanarySTT:
    def __init__(self, model_path: str):
        self.model = nemo_asr.models.EncDecMultiTaskModel.restore_from(model_path)

    def transcribe(self, wav_path: str) -> str:
        result = self.model.transcribe([wav_path])
        return result[0]
```

**FastAPI endpoint:**
```python
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    transcript = stt.transcribe(tmp_path)
    os.unlink(tmp_path)
    return {"transcript": transcript}
```

**Audio capture in Electron:**
```javascript
// renderer: SessionOverlay.jsx
const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
recorder.ondataavailable = (e) => {
  // convert chunk to WAV, POST to /transcribe
}
```

---

## 9. LLM Abstraction Layer

**Interface:**
```python
# backend/llm/base.py
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], system: str) -> str:
        """
        messages: [{"role": "user"|"assistant", "content": "..."}]
        system:   system prompt string
        returns:  assistant response string
        """
        pass
```

**Gemini adapter:**
```python
# backend/llm/gemini.py
import google.genai as genai
from .base import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def chat(self, messages: list[dict], system: str) -> str:
        config = genai.types.GenerateContentConfig(system_instruction=system)
        # convert messages format
        contents = [{"role": m["role"], "parts": [{"text": m["content"]}]}
                    for m in messages]
        response = self.client.models.generate_content(
            model=self.model, contents=contents, config=config
        )
        return response.text
```

**OpenAI-compatible adapter (covers Ollama, Groq, LM Studio):**
```python
# backend/llm/openai_compat.py
from openai import AsyncOpenAI
from .base import LLMProvider

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str = None):
        self.client = AsyncOpenAI(api_key=api_key or "none", base_url=base_url)
        self.model = model

    async def chat(self, messages: list[dict], system: str) -> str:
        all_messages = [{"role": "system", "content": system}] + messages
        response = await self.client.chat.completions.create(
            model=self.model, messages=all_messages
        )
        return response.choices[0].message.content
```

**Factory:**
```python
# backend/llm/factory.py
def get_provider(config: dict) -> LLMProvider:
    match config["provider"]:
        case "gemini":   return GeminiProvider(config["api_key"], config["model"])
        case "openai":   return OpenAICompatibleProvider(config["api_key"], config["model"])
        case "ollama":   return OpenAICompatibleProvider("none", config["model"], config["base_url"])
        case "anthropic": return AnthropicProvider(config["api_key"], config["model"])
        case _: raise ValueError(f"Unknown provider: {config['provider']}")
```

---

## 10. Calendar — AppleScript Bridge

All calendar operations go through `subprocess.run(['osascript', '-e', script])`.

**Read — today's events:**
```applescript
tell application "Calendar"
  set today to current date
  set startOfDay to today
  set time of startOfDay to 0
  set endOfDay to today
  set time of endOfDay to 86399
  set allEvents to {}
  repeat with cal in calendars
    repeat with evt in (events of cal whose start date ≥ startOfDay and start date ≤ endOfDay)
      set end of allEvents to {summary:summary of evt, startDate:start date of evt, endDate:end date of evt}
    end repeat
  end repeat
  return allEvents
end tell
```

**Write — create event:**
```applescript
tell application "Calendar"
  tell calendar "Calendar"
    make new event with properties {
      summary: "Deep Work",
      start date: date "Friday, April 11, 2026 at 3:00:00 PM",
      end date: date "Friday, April 11, 2026 at 5:00:00 PM"
    }
  end tell
end tell
```

**All write operations follow this flow:**
```
LLM response
  → extract JSON action block (regex or structured output mode)
  → validate against CalendarAction schema (pydantic)
  → FastAPI sends action to Electron via HTTP response
  → Electron renders ConfirmCard
  → User says yes/no
  → Electron POSTs /calendar/action with {action, confirmed: true|false}
  → FastAPI calls applescript.py only if confirmed=true
```

---

## 11. Config File

**Location:** `~/LifePilot/config.json`

```json
{
  "provider": "gemini",
  "api_key": "YOUR_GEMINI_KEY",
  "model": "gemini-1.5-flash",
  "morning_time": "09:00",
  "evening_time": "21:00",
  "journal_dir": "~/LifePilot/journal",
  "db_path": "~/LifePilot/lifepilot.db",
  "model_cache_dir": "~/LifePilot/models"
}
```

For Ollama:
```json
{
  "provider": "ollama",
  "api_key": "",
  "model": "llama3",
  "base_url": "http://localhost:11434/v1",
  "morning_time": "09:00",
  "evening_time": "21:00"
}
```

---

## 12. What Claude Code Does When Building Each Phase

When you tell Claude Code to build a phase from a notebook:

1. **Read the notebook** — understand the validated implementation
2. **Extract the core logic** — pull out the functions/classes that work
3. **Create the module file** — place it in the correct `backend/` location
4. **Write a FastAPI endpoint** — expose it via the right route
5. **Write a basic test** — verify the endpoint with `httpx` or `pytest`
6. **Update `main.py`** — mount the new router
7. **Do not change** — the notebook (it's the reference)

**Example: After Phase 1 notebook is validated:**
```
Claude Code creates:
  backend/llm/base.py           ← LLMProvider class from notebook
  backend/llm/gemini.py         ← GeminiProvider from notebook
  backend/llm/openai_compat.py  ← OpenAICompatibleProvider stub
  backend/llm/factory.py        ← factory function
  backend/config.py             ← config loader
  backend/main.py               ← FastAPI app with /health and /chat
```

---

## 13. Running the App (Dev Mode)

```bash
# Terminal 1 — backend
conda activate lifepilot
cd /Users/adarsh/Developer/Projects/lifepilot
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend (once Electron is set up)
cd electron
npm install
npm run dev   # starts Vite + Electron concurrently
```

**Notebook-only mode (no Electron needed):**
```bash
conda activate lifepilot
cd /Users/adarsh/Developer/Projects/lifepilot
jupyter notebook
# open notebooks/01_llm_abstraction.ipynb
```

---

## 14. Things to Verify Before Writing App Code (Decision Gates)

These are unknowns that the notebooks will resolve before any module is built:

| Question | Resolved In | What to check |
|---|---|---|
| Does Canary/NeMo install cleanly on Mac M-series? | Notebook 2 | If not, use `faster-whisper` instead |
| Is Canary transcription latency acceptable (<3s/30s audio)? | Notebook 2 | If not, use `faster-whisper` |
| Do AppleScript write operations work on your macOS version? | Notebook 5 | If blocked by permissions, investigate entitlements |
| Does Gemini `google-genai` 1.68.0 work with system prompts as expected? | Notebook 1 | API changed in 2025 — verify interface |
| Are token counts within budget for a full session context? | Notebook 7 | If over, implement context compression |

---

*Last updated: 2026-04-11*
*This document describes the technical implementation. ROADMAP.md describes the product.*
