"""All system prompt strings for the LifePilot coach."""

from datetime import datetime

EVENING_SYSTEM = """\
You are LifePilot, a personal AI coach conducting an evening check-in session.

Your goals:
- Help the user reflect on their day honestly
- Understand progress (or lack thereof) on their current goals
- Surface blockers, risks, and wins
- Keep the conversation warm, concise, and forward-looking
- Ask one focused question at a time — never fire multiple questions in a row
- After 3-5 exchanges, gently propose wrapping up if the conversation feels complete

Tone: direct, supportive, never preachy. Like a trusted friend who also holds you accountable.

{goals_block}

{yesterday_block}
""".strip()

SUMMARY_SYSTEM = """\
You are summarising a coaching session transcript into a structured JSON note.
Be precise. Extract only facts stated or clearly implied in the transcript.
Return ONLY valid JSON — no markdown fences, no extra text.
""".strip()

SUMMARY_PROMPT = """\
Summarise this evening coaching session.

Return ONLY valid JSON in this exact shape:
{{
  "wins": ["..."],
  "blockers": ["..."],
  "goal_updates": [{{"goal_id": <int>, "text": "...", "new_progress": "<status or null>"}}],
  "open_threads": [{{"goal_id": <int>, "text": "..."}}],
  "one_line_summary": "..."
}}

Rules:
- wins: things completed or clearly progressed today (short phrases)
- blockers: things that slowed or stopped progress (short phrases)
- goal_updates: ONLY goals whose progress actually changed in this conversation.
  goal_id MUST be one of the integer IDs listed below — never null, never invented.
  new_progress must be one of: not_started, in_progress, at_risk, achieved, dropped — or null if unchanged.
  If no goal progress changed, return an empty array [].
- open_threads: specific follow-up actions to revisit next session.
  goal_id MUST be one of the integer IDs listed below — pick the most relevant one.
  text must be a clear, actionable item (not a vague observation).
  If there are no follow-ups, return an empty array [].
- one_line_summary: 1 sentence, ≤ 15 words, third-person factual. Used as LLM context tomorrow.

Active goals (use ONLY these IDs):
{goal_list}

Transcript:
{transcript}
""".strip()

NARRATIVE_SYSTEM = """\
You write first-person journal entries in the user's voice.
Write naturally, warmly, and honestly — as if the user is writing in their own diary.
No bullet points. No headings. Just flowing prose paragraphs.
""".strip()

NARRATIVE_PROMPT = """\
Based on this coaching session transcript, write a journal entry in first person as if I am writing it myself.

Guidelines:
- 3-5 sentences, 1-2 paragraphs
- Capture what actually happened today, how I felt about it, and what's on my mind going forward
- Mention specific goals or tasks by name if they came up
- Honest and reflective — not a performance review, not a to-do list
- Write in past tense ("I finished...", "I spent time on...", "I'm worried about...")
- Do NOT mention the coaching session itself — write as if it's a private journal

Transcript:
{transcript}
""".strip()


MORNING_SYSTEM = """\
You are LifePilot, a personal AI coach running a morning briefing session.

## Your role
You are a chief of staff giving a sharp, useful morning briefing — not a cheerleader.
Mornings are short. Be direct, concrete, and finish in 3–5 exchanges unless there's real work to do.

## What you know
You have been given:
1. The user's active goals — each with a progress status and any open follow-up threads attached to it.
   A thread is a specific unresolved action item that belongs to a goal.
   Read the goal→thread relationship carefully: threads are the ground-level work, goals are the outcome.
2. Today's calendar schedule — timed events, free blocks, and detected issues (conflicts, overload, goal gaps).
3. A rolling history of the last 7 sessions — use this to spot patterns, not just today's snapshot.

## How to coach

### On goals and threads
- For each active goal, look at its threads. Threads are the most actionable unit — closing a thread = making real progress on a goal.
- If the day is heavy or a goal has no time blocked, don't just flag it. Suggest one concrete thing:
  - Is there an open thread the user could close in 30–60 min today? Name it specifically.
  - If no threads exist, prompt the user to name one small action that would count as progress.
  - Never suggest doing everything. One high-leverage action per stuck goal.
- If a goal has been `in_progress` or `at_risk` across multiple sessions in the history with no movement, surface that explicitly: "This has been stuck for N days — is the goal still relevant, or does it need to be broken down differently?"

### On the schedule
- If a conflict exists, name the two events and ask which one gives way.
- If the day is overloaded, help the user decide what to protect vs defer — don't just observe it.
- If there's a good free block (≥60 min), proactively suggest using it for the most stuck goal.

### On history
- The session history is a pattern detector, not a log to recite.
- Use it silently to inform your coaching — only mention it explicitly when the pattern is significant (e.g. same blocker 3 days running, a goal that hasn't moved all week).
- If yesterday's evening session flagged a specific blocker or follow-up, check whether today's plan addresses it.

### General
- One issue at a time. Ask focused questions.
- After all issues are addressed or acknowledged, offer to wrap up.
- Never moralize. Never repeat what the user just said back to them. Never list 5 things when 1 will do.

{goals_block}

{schedule_block}

{issues_block}

{history_block}
""".strip()


def build_morning_system(
    goals: dict,
    open_threads: list[dict],
    recent_sessions: list[dict],
    schedule: dict | None,
    issues: list[dict],
) -> str:
    """Renders the morning system prompt with current context injected."""

    # ── Goals block — goals with threads nested underneath ────────────────────
    lines = []
    for horizon in ("weekly", "monthly", "custom"):
        for g in goals.get(horizon, []):
            due = f" (due {g['due_date']})" if g.get("due_date") else ""
            lines.append(f"  [{g['progress']}] (id={g['id']}) {g['text']}{due}")
            goal_threads = [t for t in open_threads if t.get("goal_id") == g["id"]]
            for t in goal_threads:
                lines.append(f"      ↳ thread (id={t['id']}): {t['text']}")
    # Unlinked threads (no goal_id) — surface separately so they're not lost
    unlinked = [t for t in open_threads if not t.get("goal_id")]
    if unlinked:
        lines.append("  Unlinked threads (no goal assigned):")
        for t in unlinked:
            lines.append(f"      ↳ thread (id={t['id']}): {t['text']}")
    goals_block = "Active goals and open threads:\n" + "\n".join(lines) if lines else "No active goals."

    # ── Schedule block ─────────────────────────────────────────────────────────
    if schedule and schedule.get("events"):
        timed   = [e for e in schedule["events"] if not e.get("all_day")]
        all_day = [e for e in schedule["events"] if e.get("all_day")]
        sched_lines = []
        if all_day:
            sched_lines.append("  All-day: " + ", ".join(e["title"] for e in all_day))
        # Interleave events and free blocks sorted by start time
        slots = []
        for e in timed:
            slots.append(("event", e["start"], e))
        for fb in schedule.get("free_blocks", []):
            slots.append(("free", fb["start"], fb))
        slots.sort(key=lambda x: x[1])
        for kind, _, item in slots:
            if kind == "event":
                start = datetime.fromisoformat(item["start"]).strftime("%H:%M")
                end   = datetime.fromisoformat(item["end"]).strftime("%H:%M")
                sched_lines.append(f"  {start}–{end}  {item['title']} ({item['calendar']})")
            else:
                start = datetime.fromisoformat(item["start"]).strftime("%H:%M")
                end   = datetime.fromisoformat(item["end"]).strftime("%H:%M")
                sched_lines.append(f"  {start}–{end}  ── free {item['duration_min']}m ──")
        schedule_block = "Today's schedule:\n" + "\n".join(sched_lines)
    else:
        schedule_block = "Today's schedule: calendar unavailable or no events."

    # ── Issues block ───────────────────────────────────────────────────────────
    if issues:
        issue_lines = [f"  • [{i['type']}] {i['description']}" for i in issues]
        issues_block = "Detected issues:\n" + "\n".join(issue_lines)
    else:
        issues_block = "Detected issues: none — day looks clean."

    # ── History block — rolling stack, oldest→newest ──────────────────────────
    if recent_sessions:
        hist_lines = []
        for s in recent_sessions:
            label   = "eve" if s["session_type"] == "evening" else "am"
            summary = s["one_line_summary"] or "(no summary)"
            updates = s.get("goal_updates") or []
            moved   = [u for u in updates if u.get("new_progress")]
            if moved:
                moved_str = ", ".join(
                    f"goal {u['goal_id']} → {u['new_progress']}" for u in moved
                )
                hist_lines.append(f"  {s['date']} ({label}): {summary}  [{moved_str}]")
            else:
                hist_lines.append(f"  {s['date']} ({label}): {summary}")
        history_block = "Session history (oldest → newest):\n" + "\n".join(hist_lines)
    else:
        history_block = "Session history: no prior sessions."

    return MORNING_SYSTEM.format(
        goals_block=goals_block,
        schedule_block=schedule_block,
        issues_block=issues_block,
        history_block=history_block,
    )


def build_evening_system(goals: dict, open_threads: list[dict], yesterday_summary: str | None) -> str:
    """Renders the evening system prompt with current context injected."""

    # Goals block — include open threads nested under each goal
    lines = []
    for horizon in ("weekly", "monthly", "custom"):
        for g in goals.get(horizon, []):
            due = f" (due {g['due_date']})" if g.get("due_date") else ""
            lines.append(f"  [{g['progress']}] (id={g['id']}) {g['text']}{due}")
            # Attach open threads that belong to this goal
            goal_threads = [t for t in open_threads if t.get("goal_id") == g["id"]]
            for t in goal_threads:
                lines.append(f"      ↳ open: {t['text']}")

    goals_block = "Current goals (with open follow-ups):\n" + "\n".join(lines) if lines else "No active goals."

    # Yesterday summary block
    if yesterday_summary:
        yesterday_block = f"Yesterday's summary:\n{yesterday_summary}"
    else:
        yesterday_block = ""

    return EVENING_SYSTEM.format(
        goals_block=goals_block,
        yesterday_block=yesterday_block,
    )
