LifePilot

MVP Build Document — Week 1

Local AI Personal Coach & Calendar-Aware Journal for Mac

1. Product Overview

LifePilot is a native Mac menu bar application that acts as a personal
AI coach and journal. It has full context of your calendar, conducts
voice-first morning and evening sessions, tracks your goals across
daily/weekly/monthly/quarterly horizons, and can read and write to your
calendar by voice — all locally on your machine.

The MVP is a one-week build targeting a fully working end-to-end loop:
morning debrief, evening journal, agentic calendar edits, goal tracking,
and a journal list UI.

2. Tech Stack

The stack is chosen for speed of build, Mac-native capabilities, and LLM
provider flexibility.

  ------------------------------------------------------------------------
  Layer            Technology            Reason
  ---------------- --------------------- ---------------------------------
  App Shell        Electron (Mac menu    Cross-platform base, easy system
                   bar)                  tray, IPC to backend

  Backend          FastAPI (Python)      Async, lightweight, easy to
                                         expose endpoints to Electron

  Speech-to-Text   faster-whisper        Offline, no API cost, runs on Mac
                   (local)               CPU/GPU

  LLM (dev)        Gemini API            Fast, cheap, good instruction
                   (gemini-1.5-flash)    following for coaching

  LLM (user)       Ollama (Llama 3 8B+)  Local option, OpenAI-compatible
                                         endpoint

  LLM Abstraction  Custom provider       Gemini + OpenAI-compatible
                   interface             adapters cover all providers

  Calendar         Apple Calendar via    No OAuth, works on synced Google
                   AppleScript           Calendar, read+write

  Database         SQLite (via           Goals, sessions, memory — all
                   SQLAlchemy)           local

  Journal Files    Markdown (.md) per    Human-readable, no lock-in,
                   day                   plaintext forever

  Notifications    Mac UNNotification    Triggers morning/evening sessions
                   via Python            automatically

  UI Framework     Electron + React      Component-based, easy list/tab
                                         views
  ------------------------------------------------------------------------

3. LLM Abstraction Layer

Built on Day 1 before any feature code. All coach prompts call
llm.chat() — never touch a provider directly. This means swapping Gemini
for Ollama or OpenAI requires zero code changes.

Provider Interface

  class LLMProvider:

  async def chat(self, messages: list[dict], system: str) -> str

Implemented Adapters

- GeminiProvider — uses google-generativeai SDK

- OpenAICompatibleProvider — covers OpenAI, Ollama, LM Studio, Groq, any
  OpenAI-format API

User Config (config.json)

  { "provider": "gemini", "api_key": "YOUR_KEY", "model":
  "gemini-1.5-flash" }

  { "provider": "ollama", "api_key": "", "model": "llama3", "base_url":
  "http://localhost:11434" }

  { "provider": "openai", "api_key": "YOUR_KEY", "model": "gpt-4o" }

The factory function reads config.json and returns the right provider.
First-launch setup screen lets the user choose and paste their key —
stored locally, never transmitted anywhere.

4. Calendar Integration

Apple Calendar is the integration target. Since your Google Calendar
syncs to Apple Calendar, AppleScript covers everything without OAuth,
Google credentials, or any external API dependency.

4.1 Read Operations

- Fetch today's events: title, time, duration, location

- Fetch tomorrow's events for morning preview

- Fetch weekly events for goal nudging

- Detect conflicts: overlapping events flagged and surfaced to coach

- Detect gaps: free blocks identified for scheduling suggestions

4.2 Write Operations (Agentic — always confirm first)

  ------------------------------------------------------------------------
  Voice Command         Action                     Confirmation Required
  --------------------- -------------------------- -----------------------
  Move my 2pm to        Reschedules event to       Yes — shows new time
  Thursday              Thursday same time         before writing

  Block 2 hours         Creates focus block event  Yes — confirms title,
  tomorrow for deep                                time, duration
  work                                             

  Cancel Friday's       Deletes event              Yes — names the event
  standup                                          before deleting

  Push client call to   Moves event 7 days forward Yes — shows new date
  next week                                        

  Add reminder to       Creates calendar event     Yes — confirms details
  follow up with Priya  with alert                 

  Reschedule everything Moves multiple events      Yes — lists each one
  after 3pm tomorrow                               before acting
  ------------------------------------------------------------------------

4.3 AppleScript Bridge

A Python module wraps all AppleScript calls. Events are serialized to
JSON for the LLM context. Write operations go through a confirmation
layer — the LLM proposes an action, the UI presents it, user confirms,
then AppleScript executes.

The confirmation flow: LLM returns structured JSON action → FastAPI
parses it → Electron shows confirmation card → User says 'yes' or 'no' →
AppleScript executes or cancels.

5. Voice Pipeline (STT)

Speech-to-text uses faster-whisper running fully locally. No audio is
ever sent to an external server.

5.1 Recording Flow

- Electron captures microphone via Web Audio API

- Audio streamed to FastAPI backend as WAV chunks

- faster-whisper transcribes in real-time (small model for speed)

- Transcript sent to LLM with full session context

- Response returned as text, displayed in Electron UI

5.2 Session Types

  -----------------------------------------------------------------------
  Session Type       Trigger                    Duration
  ------------------ -------------------------- -------------------------
  Morning Debrief    Mac notification at 9am    5-10 min guided

  Evening Journal    Mac notification at 9pm    10-15 min guided

  Drop-in Capture    Click menu bar icon        30 sec - open ended
                     anytime                    
  -----------------------------------------------------------------------

5.3 Coach Turn Logic

One question at a time. The LLM is prompted to ask a single focused
question, wait for a response, then proceed. Never a list of questions.
Session state maintained in memory during the conversation — full
transcript saved at end.

6. Morning Debrief Flow

Triggered by Mac push notification at a user-configured time (default
9am).

6.1 Context Assembled Before Session

- Today's calendar events (fetched from Apple Calendar)

- Tomorrow's events (for forward planning)

- Yesterday's journal summary (pulled from SQLite)

- Active goals: daily, weekly, monthly, quarterly

- Any unresolved threads from previous sessions

6.2 Session Script (AI-driven, not hardcoded)

The LLM receives all context and runs the session. Typical flow:

- Open: Good morning + today's event count

- Conflict flag: if any overlapping events detected, surface first

- Calendar confirmation: run through today's schedule, any changes
  needed?

- Goal nudge: reference today's daily goal, what's the plan to move it?

- Weekly check: if Monday, reference weekly goal and ask for weekly
  intention

- Forward plan: anything to prep or reschedule before the day starts?

- Close: brief summary of confirmed plan

6.3 Agentic Actions in Morning

- Reschedule conflict: user says 'move the focus block', coach confirms,
  writes to Calendar

- Create block: user wants to protect time, coach creates event

- Carry forward: unfinished task from yesterday — add to today's
  calendar?

7. Evening Journal Flow

Triggered by Mac push notification at user-configured time (default
9pm).

7.1 Context Assembled Before Session

- Today's completed events (title, time — no meeting notes access)

- Today's cancelled or moved events

- Morning debrief summary (what was planned)

- Active goals across all horizons

- Open threads from past 7 days flagged as unresolved

7.2 Session Script (AI-driven)

The coach goes through actual calendar events one by one — not generic
journaling prompts:

- Event debrief: 'You had a design review at 3pm — how did that go?'

- Cancelled/missed: 'The client call got moved — what happened there?'

- Goal check: 'Your weekly goal is X — did today move that forward?'

- Open thread follow-up: 'You mentioned a conflict with your manager 3
  days ago — resolved?'

- Tomorrow preview: 'You have 4 events tomorrow — anything to prep or
  reschedule?'

- Forward planning: reschedule tomorrow's events by voice if needed

7.3 Session End — What Gets Saved

- Full transcript saved as markdown: /journal/YYYY-MM-DD.md

- AI summary (3-5 sentences) saved to SQLite

- Goal progress signal saved: moved / stalled / not discussed

- Any new threads created from tonight's conversation

- Any calendar changes made during session logged

8. Goals System

Goals are the backbone of every session. They live in SQLite and are
passed as context to the LLM on every interaction.

8.1 Goal Horizons

  ------------------------------------------------------------------------
  Horizon       Example                     Reviewed In
  ------------- --------------------------- ------------------------------
  Daily         Finish the landing page     Every morning + evening
                copy                        

  Weekly        Close 2 new client          Every morning + every evening
                proposals                   

  Monthly       Launch beta to 50 users     Monday mornings + Friday
                                            evenings

  Quarterly     Hit $10k MRR                Weekly check-ins surfaced
                                            passively
  ------------------------------------------------------------------------

8.2 How Goals Are Used

- Passed as system context to LLM on every session

- Coach references them unprompted — not only when you mention them

- Progress signal tracked per session: moved / stalled / not discussed

- Unresolved goals resurface after 3+ days without progress mention

- End of week: coach gives automated reflection on what moved, what
  didn't

8.3 Goals UI (Tab 3)

- 4 sections: Daily / Weekly / Monthly / Quarterly

- Simple text input per goal, save button

- Each goal shows last-mentioned date and progress signal

- Edit anytime — changes take effect in next session

9. Journal

Every session produces a journal entry. Stored as markdown on disk,
indexed in SQLite for fast lookup.

9.1 File Structure

  ~/LifePilot/journal/

  2025-01-20.md ← full transcript + AI summary

  2025-01-21.md

  ...

  ~/LifePilot/lifepilot.db ← SQLite: sessions, goals, threads, memory

9.2 Markdown Entry Format

  # 2025-01-20

  ## Summary

  Had a productive design review. Client call cancelled due to...

  ## Goals

  - Weekly: Client proposals — moved (discussed 2 leads)

  - Daily: Landing page — stalled

  ## Full Transcript

  Coach: You had a design review at 3pm — how did that go?

  You: It went really well, the client loved the new direction...

9.3 Journal UI (Tab 2)

- Scrollable list of entries — date + one-line summary

- Click entry → expands to show full summary + transcript

- Search bar: filter by keyword across all entries

- Goal filter: show only entries where a specific goal was discussed

- Entries readable in any text editor without opening the app

10. Application UI

Electron app. Mac menu bar icon. Main window has 3 tabs. Minimal,
dark-friendly design.

10.1 Menu Bar

- Small icon in Mac menu bar (top right)

- Click → opens main window

- During active session → pulsing indicator

- Right-click → quick actions: Start Morning Brief, Start Evening
  Journal, Drop-in, Quit

10.2 Tab 1 — Today

- Today's date + greeting

- Today's events list (pulled from Apple Calendar, refreshed on open)

- Active goals snapshot: daily goal prominent, others collapsed

- Start Session button → opens voice session overlay

- Any pending threads or follow-ups surfaced as cards

10.3 Tab 2 — Journal

- Scrollable entry list: date | one-line AI summary

- Click row → expands full entry inline (summary + transcript + goals)

- Search bar at top

- Empty state with prompt to start first session

10.4 Tab 3 — Goals

- 4 accordion sections: Daily / Weekly / Monthly / Quarterly

- Each goal: text field + last-mentioned badge + save button

- Add new goal button per section

- Clear, simple form — not a project management tool

10.5 Session Overlay

- Full-screen dark overlay when session is active

- Waveform animation while mic is recording

- Coach message displayed as large text

- Transcript scrolling in smaller text below

- Confirmation cards for calendar actions — Yes / No buttons

- End Session button always visible

11. First Launch & Setup

One-time setup screen on first open. Takes under 2 minutes.

- Step 1: Choose LLM provider — Gemini / OpenAI / Ollama / Other

- Step 2: Paste API key (or skip for Ollama)

- Step 3: Grant microphone permission (Mac system dialog)

- Step 4: Grant calendar access (Mac system dialog)

- Step 5: Set morning notification time (default 9am)

- Step 6: Set evening notification time (default 9pm)

- Step 7: Set your first goals (optional, can skip and add later)

Config saved to ~/LifePilot/config.json. All data saved to ~/LifePilot/.
Nothing leaves the machine except LLM API calls (which contain only your
transcribed speech and calendar event titles — no raw audio ever sent).

12. Database Schema (SQLite)

sessions

  ----------------------------------------------------------------------------
  Column             Type          Description
  ------------------ ------------- -------------------------------------------
  id                 INTEGER PK    Auto increment

  date               TEXT          YYYY-MM-DD

  type               TEXT          morning / evening / dropin

  transcript         TEXT          Full conversation

  summary            TEXT          AI-generated 3-5 sentence summary

  calendar_actions   TEXT JSON     List of actions taken during session

  created_at         DATETIME      Timestamp
  ----------------------------------------------------------------------------

goals

  ---------------------------------------------------------------------------
  Column            Type          Description
  ----------------- ------------- -------------------------------------------
  id                INTEGER PK    Auto increment

  horizon           TEXT          daily / weekly / monthly / quarterly

  text              TEXT          Goal description

  last_mentioned    DATE          Last session it appeared

  progress_signal   TEXT          moved / stalled / not_discussed

  active            BOOLEAN       Is this goal still active
  ---------------------------------------------------------------------------

threads

  -------------------------------------------------------------------------
  Column          Type          Description
  --------------- ------------- -------------------------------------------
  id              INTEGER PK    Auto increment

  created_date    DATE          When first mentioned

  description     TEXT          What the thread is about

  resolved        BOOLEAN       Has it been closed

  last_surfaced   DATE          Last time coach brought it up
  -------------------------------------------------------------------------

13. Week 1 Build Schedule

6 working days. Each day has a clear deliverable. Claude Code used
throughout — feed it one module at a time.

  -----------------------------------------------------------------------
  Day    Focus            Deliverable
  ------ ---------------- -----------------------------------------------
  Day 1  Foundation       FastAPI running, LLM abstraction built
                          (Gemini + Ollama adapters), config.json
                          loading, AppleScript calendar read working,
                          returns today's events as JSON

  Day 2  Voice Pipeline   faster-whisper installed and transcribing from
                          mic, Electron app shell with menu bar icon, IPC
                          bridge between Electron and FastAPI
                          established, basic session overlay UI

  Day 3  Coach Logic +    SQLite schema created, goals CRUD working,
         Goals            morning debrief prompt built with full context
                          injection (calendar + goals + yesterday
                          summary), end-to-end morning session works

  Day 4  Evening Journal  Evening session prompt built, calendar-aware
                          question generation, transcript save to
                          markdown, SQLite session insert, thread
                          creation from conversation

  Day 5  Agentic Calendar AppleScript write operations (create, move,
                          delete, reschedule), confirmation card UI in
                          session overlay, LLM structured JSON action
                          parsing, full agentic loop working

  Day 6  Journal UI +     Tab 2 journal list view with expand, Tab 3
         Notifications    goals UI, Mac notifications triggering
                          morning/evening sessions, drop-in session from
                          menu bar right-click

  Day 7  Integration +    End-to-end test both full sessions, fix edge
         Polish           cases, first-launch setup screen, README,
                          verify journal files readable, tag as v0.1
  -----------------------------------------------------------------------

14. Project Folder Structure

  lifepilot/

  electron/

  main.js ← menu bar, window management, notifications

  preload.js ← IPC bridge

  renderer/ ← React UI

  App.jsx

  tabs/Today.jsx

  tabs/Journal.jsx

  tabs/Goals.jsx

  components/SessionOverlay.jsx

  components/ConfirmCard.jsx

  backend/

  main.py ← FastAPI app

  llm/

  base.py ← LLMProvider interface

  gemini.py

  openai_compat.py ← covers OpenAI + Ollama + others

  factory.py

  calendar/

  applescript.py ← all AppleScript calls

  parser.py ← event JSON serializer

  coach/

  morning.py ← morning session logic

  evening.py ← evening session logic

  prompts.py ← all system prompts

  context.py ← context assembler

  stt/

  whisper.py ← faster-whisper wrapper

  db/

  models.py ← SQLAlchemy models

  sessions.py ← session CRUD

  goals.py ← goals CRUD

  threads.py ← threads CRUD

  ~/LifePilot/ ← user data (outside repo)

  config.json

  lifepilot.db

  journal/

  2025-01-20.md

15. Privacy & Data

- All data stored in ~/LifePilot/ on user's machine

- No telemetry, no analytics, no cloud sync

- LLM API calls: only transcribed text + calendar event titles sent

- Raw audio: never saved, never sent — transcribed in memory and
  discarded

- Ollama mode: fully offline, zero external calls

- Journal markdown files: readable in any text editor, owned by user
  forever

- Uninstall: delete the app + ~/LifePilot/ folder — nothing else to
  clean up

16. Definition of Done — End of Week 1

The product is working when this loop runs without intervention:

- 9am notification fires on Mac automatically

- User opens app from notification, session overlay appears, mic is live

- Coach greets with today's calendar context, flags any conflicts

- User speaks, coach responds one question at a time

- User reschedules an event by voice — confirmation card appears — user
  confirms — Apple Calendar is updated

- Session ends — transcript saved as markdown, summary in SQLite

- 9pm notification fires

- Evening session asks about actual calendar events from today

- Goals referenced and progress noted

- Tomorrow's calendar previewed, changes made if needed

- Journal tab shows today's entry with summary

- Goals tab allows editing goals that appear in next session

That is LifePilot v0.1. Everything else is V2.
