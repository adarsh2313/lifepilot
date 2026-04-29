# LifePilot

A local-first personal AI coaching system — menu bar app that runs structured morning briefings and evening check-ins, integrating live calendar data, goal tracking, versioned session history, and on-device speech recognition.

Built to explore AI engineering patterns: multi-provider LLM abstraction, structured output extraction, context assembly, and local inference. Every major component is validated in Jupyter notebooks before landing in the backend.

---

## What It Does

**Morning briefing** — At session start, the backend pre-computes calendar issues (conflicts, overload, goal gaps) and injects them as structured data into the system prompt. The coach opens with an issue-aware greeting and a focused question — not a generic "how are you?". Sessions end with a dual-LLM post-processing step: one call extracts structured JSON (goal updates, open threads, summary), a second writes a first-person journal entry.

**Evening check-in** — Reviews the day against active goals and unresolved follow-up threads. Surfaces wins, blockers, and action items. Updates goal progress in the database. Journal entries are written to disk as markdown.

**Goal tracking** — Goals have horizons (weekly, monthly, custom), progress states, and immutable version history. Text edits deactivate the old row and insert a new one with `version+1` and `parent_id` — full audit trail without a separate history table.

**Follow-up threads** — Unresolved action items live as first-class database rows, optionally linked to goals. Surfaced to the LLM on every future session. Resolved explicitly, never auto-archived.

**Calendar integration** — Reads from Google Calendar (parallel per-calendar fetches) or macOS Calendar.app via AppleScript bridge. Computes free blocks (merging overlapping events, 15min minimum gap, 8am–10pm window). Can create, move, and delete events.

**On-device STT** — Voice input via Qwen3-ASR (0.6B, MLX-optimized for Apple Silicon). No cloud dependency, no API key. Loaded once on first use, kept in process memory. WAV encoded client-side from raw PCM.

---

## Architecture

```
┌────────────────────────────────────────────┐
│  Electron (menu bar tray app)              │
│  ├─ main.js                                │  window + tray lifecycle
│  └─ renderer/ (React 19 + Vite 6)         │
│     ├─ SessionOverlay.jsx                  │  audio capture + chat UI
│     ├─ Goals.jsx                           │  goal CRUD + threads
│     └─ App.jsx                             │  tab router                 │
└────────────────────┬───────────────────────┘
                     │ HTTP (localhost:8000)
┌────────────────────▼───────────────────────┐
│  FastAPI + Uvicorn (Python 3.12)           │
│  ├─ /session/*    session state machine    │
│  ├─ /goals/*      goal CRUD + threads      │
│  ├─ /calendar/*   schedule + actions       │
│  └─ /transcribe   STT endpoint             │
└──────────┬──────────────────┬──────────────┘
           │                  │
    ┌──────▼──────┐   ┌───────▼────────────────┐
    │  SQLite 3   │   │  LLM Provider Layer     │
    │  WAL mode   │   │  ├─ GeminiProvider      │
    │  3 tables   │   │  └─ OpenAICompatible    │
    └─────────────┘   │      (OpenAI, Groq,     │
                      │       Ollama, LMStudio) │
                      └────────────────────────┘
                      ┌────────────────────────┐
                      │  Calendar Layer         │
                      │  ├─ Google Calendar API │
                      │  └─ AppleScript bridge  │
                      └────────────────────────┘
                      ┌────────────────────────┐
                      │  STT: Qwen3-ASR (MLX)  │
                      └────────────────────────┘
```

---

## Engineering Details

### LLM Provider Abstraction

All coach logic calls a single abstract `LLMProvider` interface (`backend/llm/base.py`). Concrete providers:

- **`GeminiProvider`** — google-genai SDK, runs sync in thread pool executor (SDK not async-native), role translation (`assistant` → `model`)
- **`OpenAICompatibleProvider`** — async via AsyncOpenAI client, covers OpenAI, OpenRouter, Groq, Ollama, LMStudio via `base_url`

Provider is factory-selected from `config.json` at request time — **hot-swappable with no restart**. Each provider uses tenacity for 3-attempt exponential backoff on transient failures.

Adding a new provider: subclass `LLMProvider`, implement `chat()` and `provider_name()`, register one line in `factory.py`.

### Dual-LLM Post-processing

Session end triggers two sequential LLM calls with separate system prompts:

1. **Summary call** — strict JSON extraction: `{wins, blockers, goal_updates, open_threads, one_line_summary}`. Separate prompt avoids the fragility of mixing structured extraction with prose generation.
2. **Narrative call** — first-person journal entry written in the user's voice.

The JSON result drives database writes (goal progress, thread creation). The narrative goes to disk. This separation keeps each call's task well-scoped and the outputs independently useful.

### Context Assembly (Morning Session)

Before the first LLM call, `build_morning_context()` assembles:

- Active goals + unresolved threads (formatted as goal → nested threads)
- Today's schedule with free blocks (time-sorted, interleaved)
- Pre-computed issues:
  - **Conflicts** — overlapping calendar events
  - **Overload** — >5 events or <60min total free time
  - **Goal gaps** — active goal with no corresponding calendar block
- Last 7 session summaries (oldest → newest, goal updates summarized)

Issues are structured data injected into the prompt — the LLM sees `type: conflict, description: "1:1 with PM overlaps design review (2:00–3:00)"`, not a free-text blob. The opening message is generated from detected issues, so it's always specific.

### Goal Versioning

Goal text edits use immutable versioning:

```
goals table: id | text | version | parent_id | active
update "improve sleep" →
  row 1: active=False, version=1, parent_id=NULL
  row 2: active=True,  version=2, parent_id=1, text="sleep 8hrs by 11pm"
```

Progress changes mutate the active row in place (progress is not historical data). Full text history is preserved without a separate changelog table.

### Calendar Free Block Computation

`compute_free_blocks()` in `backend/calendar/parser.py`:

1. Filters to timed events only (skips all-day)
2. Merges overlapping events (handles double-booked slots)
3. Finds gaps in configurable window (default 8am–10pm)
4. Filters gaps shorter than 15 minutes
5. Returns free blocks as `[{start, end, duration_min}]`

Passed to morning coach to suggest high-leverage work blocks.

### Voice Input Pipeline

**Client-side (React):**
1. `getUserMedia()` → `AudioContext` + `ScriptProcessor` at system sample rate
2. `onaudioprocess` appends float32 PCM chunks (4096 samples each)
3. On stop: merge chunks → quantize float32 → int16 (with clipping) → build RIFF WAV header → base64-encode
4. POST to `/transcribe`

**Server-side:**
1. Decode base64 → write temp file
2. Run `transcribe_file()` in thread pool (1 worker, avoids semaphore leak)
3. Return `{text, language, latency_sec, audio_duration_sec}`

STT model (Qwen3-ASR 0.6B via mlx-qwen3-asr) is a lazy-loaded singleton — cold start ~2s on first call, negligible thereafter.

### In-Memory Session Store

Active session state (history, system prompt, context) lives in a dict in the FastAPI process — not the database. This keeps multi-turn state simple and avoids DB round-trips per message. On session end, the full transcript + summary is persisted. The pattern assumes one active session at a time, which matches the UX.

### Concurrency Model

- FastAPI async handlers for I/O-bound paths
- Sync SDKs (google-genai, httplib2) run in `asyncio.run_in_executor` thread pool
- Google Calendar fetches: `ThreadPoolExecutor(max_workers=min(calendar_count, 8))` — one thread per calendar
- STT: dedicated `ThreadPoolExecutor(max_workers=1)` — serialised to prevent model semaphore contention
- AppleScript bridge: global `threading.Lock()` — osascript subprocess is not thread-safe

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 35, Node 22 |
| Frontend | React 19, Vite 6 |
| Backend | FastAPI 0.135, Uvicorn 0.42, Python 3.12 |
| ORM / DB | SQLAlchemy 2.0, SQLite 3 (WAL mode) |
| Validation | Pydantic 2.12 |
| LLM (default) | Google Gemini via google-genai SDK |
| LLM (alt) | Any OpenAI-compatible endpoint |
| STT | mlx-qwen3-asr 0.3.2 (Qwen3 0.6B, MLX) |
| Calendar | Google Calendar API v3, AppleScript bridge |
| Retry logic | tenacity (exponential backoff) |
| Audio processing | numpy, soundfile |

---

## Project Structure

```
lifepilot/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, lifespan
│   ├── config.py                # config.json loader with hot-swap
│   ├── llm/
│   │   ├── base.py              # Abstract LLMProvider interface
│   │   ├── factory.py           # Provider factory (config-driven)
│   │   ├── gemini.py            # Google Gemini provider
│   │   └── openai_compat.py     # OpenAI-compatible provider
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models: Goal, Session, Thread
│   │   ├── database.py          # Engine, WAL mode, session factory
│   │   ├── goals.py             # Goal CRUD + versioning + context builder
│   │   ├── sessions.py          # Session persistence + history fetch
│   │   └── threads.py           # Thread CRUD + surface unresolved
│   ├── coach/
│   │   ├── context.py           # Context assemblers (morning + evening)
│   │   ├── morning.py           # Morning session state machine + issue detection
│   │   ├── evening.py           # Evening session state machine
│   │   └── prompts.py           # System prompts + injection templates
│   ├── calendar/
│   │   ├── provider.py          # Calendar backend dispatcher
│   │   ├── google_cal.py        # Google Calendar API integration
│   │   ├── applescript.py       # macOS Calendar.app bridge
│   │   ├── parser.py            # Event parsing + free block computation
│   │   ├── actions.py           # Calendar action schema + executor
│   │   └── auth.py              # One-time Google OAuth flow
│   ├── routers/
│   │   ├── sessions.py          # /session/* endpoints
│   │   ├── goals.py             # /goals/* endpoints
│   │   ├── calendar.py          # /calendar/* endpoints
│   │   └── audio.py             # /transcribe endpoint
│   └── stt/
│       ├── qwen3_asr.py         # Qwen3-ASR wrapper (lazy-load singleton)
│       └── schemas.py           # STTResult schema
├── electron/
│   ├── main.js                  # Electron main process, tray, window
│   └── renderer/                # React + Vite frontend
│       └── src/
│           ├── App.jsx
│           ├── SessionOverlay.jsx
│           └── Goals.jsx
├── notebooks/
│   ├── 01_llm_abstraction.ipynb # Provider abstraction + structured output validation
│   ├── 02_stt_qwen3_asr.ipynb   # STT latency + accuracy experiments
│   └── 03_database_goals.ipynb  # Goal versioning + query validation
└── config.json                  # Runtime config (gitignored)
```

---

## Setup

### Requirements

- macOS (Apple Silicon recommended for local STT)
- Python 3.12+
- Node 22+
- Conda or venv

### 1. Python environment

```bash
conda create -n lifepilot python=3.12
conda activate lifepilot
pip install -r requirements.txt
```

### 2. Configure

Copy the template and fill in your API key:

```bash
cp config.example.json config.json   # or create manually
```

`config.json`:

```json
{
  "provider": "gemini",
  "api_key": "YOUR_GEMINI_API_KEY",
  "model": "gemini-2.0-flash",
  "morning_time": "09:00",
  "evening_time": "21:00",
  "journal_dir": "/path/to/journal",
  "db_path": "/path/to/lifepilot.db",
  "calendar_backend": "google"
}
```

To use a different provider, set `provider` to `openai`, `groq`, `ollama`, or `lmstudio` and update `api_key`/`base_url`/`model` accordingly. No code changes required.

### 3. Google Calendar (optional)

**a. Create OAuth credentials**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create a project
2. Enable the **Google Calendar API**
3. Create credentials → **OAuth 2.0 Client ID** → Desktop app
4. Download JSON → save as `google_client_secret.json` in the project root

**b. Run the one-time auth flow**

```bash
python -m backend.calendar.auth
```

This opens a browser window, asks for calendar access, and saves `google_credentials.json` to the project root. The backend auto-refreshes the token on expiry.

**c. Set calendar backend in config**

```json
"calendar_backend": "google"
```

For macOS Calendar.app without Google, set `"calendar_backend": "applescript"` — no credentials needed.

### 4. Run the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Run the Electron app

```bash
cd electron
npm install
npm run dev         # starts renderer dev server + Electron
```

Or build for production:

```bash
npm run build       # Vite bundle
npm run electron    # run built app
```

---

## Notebooks

The `notebooks/` directory contains the experimental validation work done before each component landed in the backend:

| Notebook | What it validates |
|---|---|
| `01_llm_abstraction.ipynb` | Provider abstraction, multi-turn context, retry logic, structured JSON extraction, end-to-end session simulation |
| `02_stt_qwen3_asr.ipynb` | Qwen3-ASR model loading, transcription latency, accuracy on voice input |
| `03_database_goals.ipynb` | Goal versioning (create/update/version chain), progress mutation, goal context builder for LLM |

Run with:

```bash
jupyter notebook notebooks/
```

---

## Configuration Reference

| Key | Default | Description |
|---|---|---|
| `provider` | `gemini` | LLM backend: `gemini`, `openai`, `groq`, `ollama`, `lmstudio`, `openrouter` |
| `api_key` | `""` | API key for the selected provider |
| `model` | `gemini-2.0-flash` | Model identifier |
| `base_url` | `null` | Base URL for OpenAI-compatible providers (Ollama: `http://localhost:11434/v1`) |
| `morning_time` | `09:00` | Morning briefing time (display only, sessions triggered manually) |
| `evening_time` | `21:00` | Evening check-in time |
| `journal_dir` | `./journal` | Directory for markdown journal entries |
| `db_path` | `./lifepilot.db` | SQLite database path |
| `calendar_backend` | `google` | `google` or `applescript` |

Config is re-read on every request. Swap providers or models at runtime with no restart.
