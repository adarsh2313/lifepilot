# LifePilot — Full Build Roadmap

> **How to use this file:** Edit freely. Cross out sections, add notes, reorder phases.
> Share back with Claude Code when you're ready to build a phase.

---

## 1. What Is LifePilot?

A native Mac menu bar app that acts as a personal AI coach. Three core loops:

- **Goals tab:** Your intentions — weekly targets, monthly goals, custom deadlines. The source of truth for everything else.
- **Calendar tab:** Morning PA session — reads your day, cross-references your goals, nudges you back on track, and can edit your calendar by voice.
- **Journal tab:** Evening reflection — free-talk first, then personalised follow-up questions driven by your goals and calendar. Saves raw transcript + first-person AI summary, browsable in a calendar view.

Everything is local. Nothing leaves your machine except LLM API calls (text only, no audio).

---

## 2. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| App shell | Electron (Mac menu bar) | System tray, native notifications, IPC to backend |
| Backend | FastAPI (Python) | Async, lightweight, easy IPC with Electron |
| Speech-to-Text | Nvidia Canary (Qwen 2.5B, HuggingFace) | Local, no API cost, high quality |
| LLM (default) | Gemini API (gemini-1.5-flash) | Fast, cheap, great instruction following |
| LLM (user options) | OpenAI / Ollama / any OpenAI-compatible | Provider abstraction — zero code changes to swap |
| Calendar | Apple Calendar via AppleScript | No OAuth, works with synced Google Calendar |
| Database | SQLite (via SQLAlchemy) | Goals history, sessions, threads — all local |
| Journal Files | Markdown (.md) per day | Human-readable, no lock-in |
| Notifications | Mac UNNotification via Python | Triggers morning/evening sessions |
| UI | Electron + React | Tabs, session overlay, calendar grid |

---

## 3. LLM Abstraction Layer

All coach prompts go through `llm.chat()` — never touch a provider directly. Swapping Gemini for Ollama or Claude requires zero code changes.

```python
class LLMProvider:
    async def chat(self, messages: list[dict], system: str) -> str
```

**Adapters:**
- `GeminiProvider` — google-generativeai SDK
- `OpenAICompatibleProvider` — covers OpenAI, Ollama, LM Studio, Groq
- `AnthropicProvider` — Claude (optional, add if needed)

**User config (`~/LifePilot/config.json`):**
```json
{ "provider": "gemini", "api_key": "YOUR_KEY", "model": "gemini-1.5-flash" }
{ "provider": "ollama", "api_key": "", "model": "llama3", "base_url": "http://localhost:11434" }
{ "provider": "openai", "api_key": "YOUR_KEY", "model": "gpt-4o" }
```

---

## 4. Speech-to-Text — Nvidia Canary

**Model:** `nvidia/canary-1b` from HuggingFace (or Qwen 2.5B variant)
**Runs:** Fully locally on Mac. No audio ever leaves the machine.

**Pipeline:**
1. Electron captures mic via Web Audio API
2. Audio streamed to FastAPI as WAV chunks
3. Canary transcribes in near-real-time
4. Transcript passed to LLM with session context
5. Response returned as text, displayed in UI

**Text fallback:** Every session has a text input box. Voice is primary, text is always available.

> First run downloads model weights (~500MB–1GB). Show a progress bar. Cached locally forever after.

---

## 5. Context Architecture — How Context Is Shared

Goals, calendar, and threads are **assembled once at session start** — not re-sent on every message turn.

**Session-level system prompt (assembled once):**
```
{
  active_goals: [all current goals across all horizons],
  goal_history_hint: "Last week: aimed to close 2 proposals, partially achieved",
  today_calendar: [event list with times],           ← morning session only
  yesterday_summary: "...",                           ← from last session
  active_threads: [unresolved items < 7 days],
  session_type: "morning" | "evening" | "dropin"
}
```

**Turn-level messages (grows as session progresses):**
```
[
  {role: "assistant", content: "Tell me about your day..."},
  {role: "user",      content: "Had a busy one, the client call ran long..."},
  ...
]
```

**Per LLM call:** system prompt (once, cached by provider) + rolling transcript of current session only.
Goals and calendar are in the system prompt — not duplicated in message history.

**Why this is efficient:** Gemini, OpenAI, and most providers support prompt caching. The system prompt is stable across turns and gets cached. Marginal cost per turn is just the new message tokens — a few hundred at most.

---

## 6. Tab Structure & Build Order

### Tab 1 — Goals & Habits *(Build First)*
### Tab 2 — Calendar & Morning PA *(Build Second)*
### Tab 3 — Journal *(Build Third)*

This order is intentional:
- Goals must exist before anything can reference them as context
- Calendar tab needs goals working to be meaningful (nudges, gap detection)
- Journal benefits from both goals and calendar context for personalised prompts

---

## 7. Tab 1 — Goals & Habits

### 7.1 Goal Horizons

| Horizon | Example | Notes |
|---|---|---|
| Weekly | Close 2 client proposals | Resets each week, previous stored |
| Monthly | Launch beta to 50 users | Resets each month, previous stored |
| Custom | Finish pitch deck before April 20 | Freeform with a target date |

> **No daily goals in this tab.** Daily intentions emerge from the morning session — the coach suggests what to prioritise based on your weekly goals and calendar gaps.

### 7.2 Goal Versioning — Full History Kept

Every goal update creates a **new record** — nothing is overwritten. The app shows the current active goal, but the full history is stored. The coach can reference: *"Last week you aimed to close 2 proposals — you got 1. This week's goal is 3."*

```
goals table
  id          INTEGER PK
  horizon     TEXT          weekly / monthly / custom
  text        TEXT          Goal description
  target_date DATE          For custom goals (nullable for weekly/monthly)
  week_start  DATE          For weekly goals — which week this belongs to
  month       TEXT          For monthly goals — YYYY-MM
  created_at  DATETIME      When this version was set
  active      BOOLEAN       Is this the current active goal for this horizon
  progress    TEXT          on_track / at_risk / achieved / carried_forward
```

When you update a weekly goal:
1. Current active goal → `active = false`, progress marked
2. New record created → `active = true`
3. Old record remains in history

### 7.3 Goals UI

```
┌──────────────────────────────────────────────────┐
│  Goals & Habits                                  │
│                                                  │
│  This Week  (Apr 7 – Apr 13)          [+ Add]   │
│  ┌────────────────────────────────────────────┐  │
│  │ ✎ Close 2 new client proposals             │  │
│  │   Set Apr 7  ·  on track  ·  [Edit]        │  │
│  └────────────────────────────────────────────┘  │
│  ▸ Previous weeks (3)                            │
│                                                  │
│  This Month  (April 2026)             [+ Add]   │
│  ┌────────────────────────────────────────────┐  │
│  │ ✎ Launch beta to 50 users                  │  │
│  │   Set Apr 1  ·  at risk  ·  [Edit]         │  │
│  └────────────────────────────────────────────┘  │
│  ▸ Previous months (2)                           │
│                                                  │
│  Custom Goals                         [+ Add]   │
│  ┌────────────────────────────────────────────┐  │
│  │ ✎ Finish pitch deck                        │  │
│  │   Due Apr 20  ·  9 days left  ·  [Edit]    │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │ ✎ Read 2 books this quarter                │  │
│  │   Due Jun 30  ·  on track  ·  [Edit]       │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

- Clicking [Edit] → text field becomes editable inline, Save/Cancel buttons appear
- Saving creates a new version (old one archived, visible in "Previous weeks")
- "Previous weeks" is a collapsible accordion — closed by default
- Progress badge (`on track` / `at risk` / `achieved`) set by coach during sessions, manually overridable

---

## 8. Tab 2 — Calendar & Morning PA

### 8.1 What It Does

Every morning the app reads your Apple Calendar and cross-references your goals. The coach:

1. **Briefs your day** — runs through today's events
2. **Detects gaps** — free blocks where you could work toward weekly goals
3. **Detects overload** — days where goal work has no room scheduled
4. **Flags unfinished items** — if yesterday had an event that ended but is marked incomplete or was cancelled, coach asks if you want to carry it forward
5. **Nudges on weekly goals** — if you're mid-week and haven't made progress, coach proactively suggests adding time to today
6. **Agentic edits** — reschedule, create, or delete events by voice, with confirmation

### 8.2 Morning Session Flow

**Context assembled before session:**
- Today's calendar events (title, time, duration)
- Tomorrow's events (for forward planning)
- Yesterday's session summary (what was planned vs what happened)
- Active goals (weekly + monthly + custom)
- Any open threads (unresolved items from past sessions)

**Session script (AI-driven, not hardcoded):**
```
Coach: "Good morning. You have 5 events today — design review at 10, client call
        at 2, and a 2-hour focus block at 4. Your weekly goal is to close 2
        proposals — I don't see time blocked for that today. Want me to add it?"

You:   "Yeah, move the focus block to 3pm and label it proposals work."

Coach: [shows confirmation card]
       Move "Focus Block" from 4:00pm → 3:00pm, rename to "Proposals Work"?
       [Yes] [No]

You:   "Yes."

Coach: "Done. Anything else before you start your day?"
```

**True PA behaviour — what the coach checks unprompted:**
- Overlapping events (conflicts)
- Focus block exists for weekly goal work? If not, suggests adding one
- Unfinished item from yesterday? Asks if you want to reschedule
- Mid-week with no goal progress? Nudges to block time today
- Overloaded day (6+ hours of meetings)? Flags it, suggests what to defer

### 8.3 Agentic Calendar Operations

All write operations require explicit confirmation before executing.

| Voice Command | Action | Confirmation Shows |
|---|---|---|
| Move my 2pm to Thursday | Reschedule event | "Move [Client Call] Fri 2pm → Thu 2pm?" |
| Block 2 hours for deep work tomorrow | Create focus event | "Add [Deep Work] tomorrow 10am–12pm?" |
| Cancel Friday's standup | Delete event | "Delete [Standup] Friday 9am?" |
| Push client call to next week | Move 7 days forward | "Move [Client Call] Apr 11 → Apr 18?" |
| Reschedule everything after 3pm | Move multiple events | Lists each one, confirm all or individually |

**Confirmation flow:**
```
LLM returns structured JSON action
  → FastAPI parses
  → Electron shows ConfirmCard in session overlay
  → User says "yes" / "no" (or clicks button)
  → AppleScript executes or cancels
  → Coach continues session
```

### 8.4 Calendar UI (Tab 2)

```
┌──────────────────────────────────────────────────┐
│  Calendar                    Friday, Apr 11      │
│                                                  │
│  [Start Morning Session]                         │
│                                                  │
│  Today's Schedule                                │
│  09:00  Standup               30min              │
│  10:00  Design Review         1hr    ⚑ conflict  │
│  10:30  Client Prep           1hr    ⚑ conflict  │
│  14:00  Client Call           30min              │
│  16:00  Focus Block           2hr                │
│                                                  │
│  Weekly Goal Check                               │
│  Close 2 proposals   ░░░░░░░░░░  0/2  at risk   │
│  💡 No time blocked for this today               │
│                                                  │
│  Open Threads                                    │
│  ⚑ Manager conflict — mentioned 3 days ago      │
└──────────────────────────────────────────────────┘
```

- Conflicts highlighted inline
- Goal progress bar shows mid-week status
- Nudge card appears if goal is at risk and no time is blocked
- [Start Morning Session] opens the voice session overlay

---

## 9. Tab 3 — Journal

### 9.1 Session Flow — Free-Talk First, Then Personalised Prompts

**Phase 1 — Open reflection (user leads):**
```
Coach: "How was your day? Tell me whatever's on your mind."
You:   [speak freely for 2-5 minutes]
```

**Phase 2 — Coach asks targeted follow-ups:**
Based on what you said + your goals + today's calendar events, the coach generates specific questions:
```
Coach: "You mentioned the client call — you had that at 2pm today.
        How did it go in relation to closing the proposal?"

Coach: "Your weekly goal is to close 2 proposals. Based on today,
        are you on track?"

Coach: "You didn't mention the design review — was that productive?"
```

This is better than scripted prompts — the coach only asks what's relevant to *your* day, not a generic checklist.

**Phase 3 — Close:**
```
Coach: "Anything else on your mind before we wrap up?"
You:   [optional final thoughts]
Coach: "Got it. Good night."
```

### 9.2 What Gets Saved

**Markdown file** (`~/LifePilot/journal/YYYY-MM-DD.md`):
```markdown
# April 11, 2026

## AI Summary
Today I had a productive design review where the client responded well to the
new direction. The client call at 2pm ran long but ended positively — I'm close
to closing the proposal. I didn't make as much progress on the pitch deck as
I'd hoped, and I want to block time for that tomorrow morning.

## Goals
- Weekly (Close 2 proposals): moved — one proposal nearly closed
- Custom (Pitch deck by Apr 20): stalled — no time spent today

## Full Transcript
Coach: How was your day? Tell me whatever's on your mind.
Me: Had a busy one. The design review went really well...
Coach: You mentioned the client call — how did that go?
Me: It ran longer than expected but in a good way...
[...]
```

**Key details:**
- AI summary is written in **first person** ("Today I had...") — reads like your own diary entry, not a report
- Raw transcript is saved verbatim
- Goal progress signals saved to SQLite for coach context in future sessions
- Any new threads created (unresolved topics) saved to threads table

### 9.3 Journal UI — Calendar View

```
┌──────────────────────────────────────────────────┐
│  Journal                                         │
│  [Search entries...]                             │
│                                                  │
│  ◀  April 2026  ▶                                │
│                                                  │
│   Mo  Tu  We  Th  Fr  Sa  Su                    │
│         1   2   3  ●4   5   6                   │
│    7   8  ●9  10 ●11  12  13                    │
│   14  15  16  17  18  19  20                    │
│   21  22  23  24  25  26  27                    │
│   28  29  30                                    │
│                                                  │
│  ─────────────────────────────────────────────  │
│  April 11                                       │
│                                                  │
│  Today I had a productive design review where    │
│  the client responded well to the new direction. │
│  The client call at 2pm ran long but ended       │
│  positively — I'm close to closing the proposal. │
│                                                  │
│  Goals: Weekly ● moved  ·  Custom ○ stalled     │
│                                                  │
│  [View Full Transcript ▾]                        │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│  Coach: How was your day?...                     │
│  Me: Had a busy one...                           │
└──────────────────────────────────────────────────┘
```

- Dots on days with journal entries
- Click a day → entry panel loads below calendar (no page navigation)
- AI summary shows immediately, full transcript collapses under it
- Search filters by keyword across all entries

---

## 10. Session Overlay (All Session Types)

Shared UI component used for morning PA, evening journal, and drop-in sessions.

```
┌──────────────────────────────────────────────────┐
│                                   [End Session]  │
│                                                  │
│   ░░░░░░░▓▓▓▓▓▓▓▓░░░░░░░  ← mic waveform        │
│                                                  │
│   "You mentioned the client call — you had       │
│    that at 2pm today. How did it go in           │
│    relation to closing the proposal?"            │
│                                                  │
│   ─────────────────────────────────────          │
│   Me: It ran longer than expected but            │
│   in a good way, they seemed really              │
│   interested in the pricing...                   │
│                                                  │
│              [  Type instead  ]                  │
└──────────────────────────────────────────────────┘
```

**Confirmation card (appears inline for calendar actions):**
```
┌──────────────────────────────────────────────────┐
│  Calendar Action                                 │
│  ─────────────────────────────────────────────  │
│  Move "Focus Block"                             │
│  Friday 4:00pm  →  Friday 3:00pm               │
│  Rename to "Proposals Work"                     │
│                                                  │
│           [  Yes, do it  ]  [  Cancel  ]        │
└──────────────────────────────────────────────────┘
```

---

## 11. Database Schema (SQLite)

**goals**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto increment |
| horizon | TEXT | weekly / monthly / custom |
| text | TEXT | Goal description |
| target_date | DATE | For custom goals (nullable) |
| week_start | DATE | For weekly goals — ISO week start (Monday) |
| month | TEXT | For monthly goals — YYYY-MM |
| created_at | DATETIME | When this version was created |
| active | BOOLEAN | Is this the current active goal |
| progress | TEXT | on_track / at_risk / achieved / carried_forward |

**sessions**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto increment |
| date | TEXT | YYYY-MM-DD |
| type | TEXT | morning / evening / dropin |
| transcript | TEXT | Full conversation verbatim |
| summary | TEXT | First-person AI summary |
| goal_signals | TEXT JSON | `[{goal_id, signal: moved/stalled/achieved}]` |
| calendar_actions | TEXT JSON | List of calendar edits made |
| created_at | DATETIME | Timestamp |

**threads**
| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto increment |
| created_date | DATE | When first mentioned |
| description | TEXT | What the thread is about |
| resolved | BOOLEAN | Has it been closed |
| last_surfaced | DATE | Last time coach brought it up |

---

## 12. Folder Structure

```
lifepilot/
  electron/
    main.js                  ← menu bar, window, notifications
    preload.js               ← IPC bridge
    renderer/
      App.jsx
      tabs/
        Goals.jsx            ← Tab 1
        Calendar.jsx         ← Tab 2
        Journal.jsx          ← Tab 3 (calendar grid)
      components/
        SessionOverlay.jsx
        ConfirmCard.jsx
        GoalCard.jsx
        JournalEntry.jsx
        EventList.jsx

  backend/
    main.py                  ← FastAPI app
    llm/
      base.py                ← LLMProvider interface
      gemini.py
      openai_compat.py       ← OpenAI, Ollama, LM Studio, Groq
      anthropic.py           ← optional
      factory.py             ← reads config → returns provider
    calendar/
      applescript.py         ← all AppleScript calls
      parser.py              ← event → JSON serializer
      actions.py             ← create / move / delete with confirmation
    coach/
      morning.py             ← morning PA session logic
      evening.py             ← evening journal session logic
      prompts.py             ← all system prompts
      context.py             ← assembles goals + calendar + threads into system prompt
    stt/
      canary.py              ← Nvidia Canary wrapper
      audio.py               ← WAV capture and handling
    db/
      models.py              ← SQLAlchemy models
      sessions.py            ← session CRUD
      goals.py               ← goals CRUD (versioned)
      threads.py             ← threads CRUD

~/LifePilot/                 ← user data (outside repo)
  config.json
  lifepilot.db
  journal/
    2026-04-11.md
    2026-04-10.md
```

---

## 13. Day-by-Day Build Schedule

### Day 1 — Foundation + LLM Abstraction
- FastAPI running, `/health` endpoint
- LLM abstraction: `LLMProvider` interface + `GeminiProvider` + `OpenAICompatibleProvider`
- `config.json` loading + factory function
- Smoke test: `curl localhost:8000/chat` → Gemini response

**Done when:** curl returns a coherent LLM response.

---

### Day 2 — Electron Shell + IPC Bridge
- Electron app: menu bar icon, main window, 3 tab placeholders (Goals / Calendar / Journal)
- IPC bridge: Electron ↔ FastAPI communication established
- Basic tab navigation working
- FastAPI serves static info to Electron (version check, config read)

**Done when:** 3-tab app opens from menu bar, tabs switch, connects to FastAPI.

---

### Day 3 — Goals Tab (Data Model + UI)
- SQLite schema: goals table (versioned), sessions table, threads table
- Goals CRUD endpoints (FastAPI): create, update (versioning), list current, list history
- Goals tab UI: weekly / monthly / custom sections, add/edit inline, previous versions collapsible
- Context assembler (`context.py`): reads active goals → builds system prompt fragment
- Smoke test: add a goal → see it in SQLite → log assembled context object

**Done when:** Goals tab fully works. Add goal, edit it, see history, context object looks right.

---

### Day 4 — Voice Pipeline (Canary STT)
- Download and wrap Nvidia Canary from HuggingFace
- FastAPI endpoint: `POST /transcribe` — accepts WAV, returns transcript
- Electron captures mic via Web Audio API → streams WAV to `/transcribe`
- Session overlay UI: waveform animation, coach message display, transcript scroll, text fallback input
- End Session button, overlay opens/closes cleanly

**Done when:** Speak into mic → transcript appears in session overlay.

---

### Day 5 — Evening Journal Session
- Evening session prompt: Phase 1 free-talk, Phase 2 personalised follow-ups from goals + what user said
- Session state: rolling transcript in memory during session
- End of session: transcript saved as `~/LifePilot/journal/YYYY-MM-DD.md`
- First-person AI summary generated → saved to SQLite sessions table
- Goal progress signals extracted by LLM → saved to sessions + updates goal progress field
- Thread creation: unresolved topics → saved to threads table
- Context assembler wired in: goals passed as system prompt to session

**Done when:** Complete an evening session → markdown file exists → SQLite has summary → goals show progress update.

---

### Day 6 — Journal Tab (Calendar View)
- Journal tab: month calendar grid, dots on days with entries
- Click day → entry panel loads (AI summary + goal signals + transcript accordion)
- Search bar: keyword filter across all entries
- Yesterday's summary pulled from SQLite → injected into next session's context

**Done when:** Run evening session → open Journal tab → dot on today → click → read first-person summary and transcript.

---

### Day 7 — Calendar Read + Morning PA (Read-Only First)
- AppleScript bridge: read today's events, tomorrow's events, detect overlaps/gaps
- Event parser: serialize to JSON for LLM context
- Context assembler updated: today's calendar added to morning session context
- Morning PA session prompt: brief day, flag conflicts, detect goal gaps, nudge on weekly targets
- Unfinished-yesterday detection: if yesterday session mentions cancelled/incomplete event, surface in morning
- Calendar tab UI: today's schedule, goal progress bar, nudge cards

**Done when:** Morning session runs, coach briefs the day accurately from real Apple Calendar data, nudges on goal gaps.

---

### Day 8 — Agentic Calendar Writes
- AppleScript write operations: create event, move event, delete event, rename event
- LLM structured JSON action parsing: LLM returns action JSON → FastAPI validates → sends to Electron
- ConfirmCard component: shows proposed action → user says yes/no → AppleScript executes or cancels
- Multi-event confirmation: reschedule multiple events, confirm each
- Actions logged to sessions table (`calendar_actions` field)

**Done when:** Say "move my 2pm to Thursday" → confirmation card appears → confirm → check Apple Calendar → event moved.

---

### Day 9 — Notifications + First Launch + Polish
- Mac notifications: fire at configured morning/evening times
- First-launch setup wizard:
  1. Choose LLM provider + paste API key
  2. Grant mic permission (Mac dialog)
  3. Grant calendar access (Mac dialog)
  4. Set morning/evening notification times
  5. Download Canary model (progress bar)
  6. Set first goals (optional)
- Drop-in session: right-click menu bar → open-ended session anytime
- Edge cases: no mic, no calendar access, API error, empty journal, model not downloaded

**Done when:** First launch wizard completes in under 3 minutes. All permissions granted. Model downloaded.

---

### Day 10 — Integration + End-to-End Test
- Full loop test without intervention:
  - 9am notification → morning session → calendar briefing → nudge on goal → reschedule event → confirmed in Calendar
  - 9pm notification → evening session → free-talk → personalised follow-ups → markdown saved → first-person summary in Journal tab
  - Goals tab shows updated progress signals
  - Tomorrow: morning session pulls yesterday's summary as context
- Fix edge cases found in integration test
- Tag as v0.1

---

## 14. V2 / Future Features (Not MVP)

- Photo attachments to journal entries (link photos from day to entry)
- Weekly automated reflection report (what moved, what didn't — generated Sunday evening)
- Insights tab: goal streaks, progress charts over time
- iCloud sync / multi-device
- Obsidian / Notion export for journal entries
- Custom coach persona / tone settings
- Siri Shortcuts integration
- Watch app for quick drop-in capture

---

## 15. Privacy & Data

- All data stored in `~/LifePilot/` on your machine
- No telemetry, no analytics, no cloud sync
- LLM API calls: only transcribed text + calendar event titles sent (no raw audio ever)
- Raw audio: transcribed in memory and immediately discarded
- Ollama mode: fully offline, zero external calls
- Journal files: plain markdown, readable in any text editor, owned by you forever
- Uninstall: delete the app + `~/LifePilot/` folder — nothing else to clean up

---

## 16. Definition of Done — MVP (v0.1)

1. Open Goals tab → add a weekly goal and a custom goal with a deadline
2. 9am notification fires → open morning session → coach briefs today's calendar
3. Coach flags: "Your weekly goal has no time blocked today — want me to add it?"
4. Say "yes, add a 2-hour block at 3pm" → confirmation card → confirm → Apple Calendar updated
5. Close morning session → Calendar tab shows today's events with goal progress bar
6. 9pm notification fires → open evening session
7. Speak freely about the day for 2-3 minutes
8. Coach asks 2-3 personalised follow-up questions based on what you said + your goals + today's calendar
9. Session ends → `~/LifePilot/journal/YYYY-MM-DD.md` exists
10. Open Journal tab → dot on today's date → click → first-person AI summary reads naturally
11. Expand transcript → full conversation saved verbatim
12. Goals tab shows updated progress signals from the session
13. Tomorrow morning: coach opens with yesterday's summary as context

**That is LifePilot v0.1. Everything else is V2.**

---

*Last updated: 2026-04-11*
*Edit freely — cross things out, rewrite sections, add notes inline.*
*Share back to Claude Code when ready to build a phase.*
