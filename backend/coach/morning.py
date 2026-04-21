"""Morning session state machine + issue detection.

Detects issues from the day's calendar and goals, then runs a coaching session
that opens with a proactive briefing rather than a generic "how was your day".

Issue types detected:
  conflict     — two events overlap
  overloaded   — > 5 timed events or < 60 min free in the working window
  goal_gap     — an active goal has no time blocked today (by keyword match)
"""

import json
from datetime import date, datetime
from pathlib import Path
import os

from sqlalchemy.orm import Session as DBSession

from backend.config import get_config
from backend.coach.prompts import (
    build_morning_system,
    SUMMARY_SYSTEM, SUMMARY_PROMPT,
    NARRATIVE_SYSTEM, NARRATIVE_PROMPT,
)
from backend.db.goals import update_goal_progress
from backend.db.sessions import save_session, SessionCreate
from backend.db.threads import create_thread, ThreadCreate
from backend.llm.factory import get_provider


# ── Issue detection ────────────────────────────────────────────────────────────

def detect_issues(events: list[dict], free_blocks: list[dict], goals: dict) -> list[dict]:
    """
    Return a list of issue dicts, each with:
      type:        "conflict" | "overloaded" | "goal_gap"
      description: human-readable string for the coach to use
    """
    issues = []

    timed = [e for e in events if not e.get("all_day")]

    # ── Conflicts ─────────────────────────────────────────────────────────────
    sorted_events = sorted(timed, key=lambda e: e["start"])
    for i in range(len(sorted_events) - 1):
        a = sorted_events[i]
        b = sorted_events[i + 1]
        if a["end"] > b["start"]:
            issues.append({
                "type": "conflict",
                "description": (
                    f"Conflict: \"{a['title']}\" ({_fmt_time(a['start'])}–{_fmt_time(a['end'])}) "
                    f"overlaps \"{b['title']}\" ({_fmt_time(b['start'])}–{_fmt_time(b['end'])})"
                ),
            })

    # ── Overloaded ────────────────────────────────────────────────────────────
    total_free = sum(fb["duration_min"] for fb in free_blocks)
    if len(timed) > 5 or total_free < 60:
        issues.append({
            "type": "overloaded",
            "description": (
                f"Heavy day: {len(timed)} events, "
                f"only {total_free} min free in your working window"
            ),
        })

    # ── Goal gaps ─────────────────────────────────────────────────────────────
    all_goals = (
        goals.get("weekly", []) +
        goals.get("monthly", []) +
        goals.get("custom", [])
    )
    active_goals = [g for g in all_goals if g.get("progress") not in ("achieved", "dropped")]

    event_titles_lower = " ".join(e["title"].lower() for e in timed)
    for goal in active_goals:
        # Simple keyword match: any word from the goal text (≥4 chars) in event titles
        keywords = [w for w in goal["text"].lower().split() if len(w) >= 4]
        if keywords and not any(kw in event_titles_lower for kw in keywords):
            issues.append({
                "type": "goal_gap",
                "description": (
                    f"No time blocked for \"{goal['text']}\" "
                    f"[{goal['progress']}]"
                    + (f" — due {goal['due_date']}" if goal.get("due_date") else "")
                ),
            })

    return issues


def _fmt_time(iso: str) -> str:
    """Format an ISO datetime string as HH:MM."""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return iso


# ── Session start ──────────────────────────────────────────────────────────────

async def start_morning_session(db: DBSession) -> dict:
    from backend.coach.context import build_morning_context
    ctx = build_morning_context(db)

    system = build_morning_system(
        goals=ctx["goals"],
        open_threads=ctx["open_threads"],
        recent_sessions=ctx.get("recent_sessions", []),
        schedule=ctx.get("schedule"),
        issues=ctx.get("issues", []),
    )

    # Build a concise opening message from detected issues
    opening = _build_opening(ctx.get("issues", []), ctx.get("schedule"))

    return {
        "system": system,
        "context": ctx,
        "history": [{"role": "assistant", "content": opening}],
        "opening_message": opening,
    }


def _build_opening(issues: list[dict], schedule: dict | None) -> str:
    if not issues and not schedule:
        return "Good morning! What's on your mind for today?"

    parts = []

    conflicts   = [i for i in issues if i["type"] == "conflict"]
    overloaded  = [i for i in issues if i["type"] == "overloaded"]
    goal_gaps   = [i for i in issues if i["type"] == "goal_gap"]

    event_count = len([e for e in (schedule["events"] if schedule else []) if not e.get("all_day")])

    if event_count:
        parts.append(f"Good morning — you've got {event_count} events today.")
    else:
        parts.append("Good morning — your calendar looks clear today.")

    if conflicts:
        c = conflicts[0]
        parts.append(c["description"] + ".")

    if overloaded:
        parts.append(overloaded[0]["description"] + ".")

    if goal_gaps:
        gap_names = [i["description"].split('"')[1] for i in goal_gaps if '"' in i["description"]]
        if gap_names:
            joined = ", ".join(f'"{n}"' for n in gap_names[:2])
            parts.append(f"No time blocked for {joined}.")

    if len(issues) > 1:
        parts.append("Want to sort any of this out?")
    elif issues:
        parts.append("Want to fix it?")
    else:
        parts.append("How are you feeling about the day?")

    return " ".join(parts)


# ── Shared chat turn (re-used from evening) ────────────────────────────────────

async def chat_turn(system: str, history: list[dict], user_message: str) -> str:
    history.append({"role": "user", "content": user_message})
    provider = get_provider(get_config())
    reply = await provider.chat(messages=history, system=system)
    history.append({"role": "assistant", "content": reply})
    return reply


# ── Session end ────────────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(l for l in inner if l.strip() != "```").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


async def end_morning_session(db: DBSession, history: list[dict], context: dict) -> dict:
    """Same post-processing as the evening session."""
    provider = get_provider(get_config())

    transcript_text = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in history
    )

    all_goals = (
        context["goals"].get("weekly", []) +
        context["goals"].get("monthly", []) +
        context["goals"].get("custom", [])
    )
    goal_list_str = "\n".join(
        f"  id={g['id']}: {g['text']} [{g['progress']}]" for g in all_goals
    ) or "  (no active goals)"

    summary_raw = await provider.chat(
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
            transcript=transcript_text,
            goal_list=goal_list_str,
        )}],
        system=SUMMARY_SYSTEM,
    )

    summary = _parse_json_response(summary_raw)
    if summary is None:
        summary = {"one_line_summary": "Morning session ended — summary could not be parsed.", "raw": summary_raw}

    narrative_raw = await provider.chat(
        messages=[{"role": "user", "content": NARRATIVE_PROMPT.format(transcript=transcript_text)}],
        system=NARRATIVE_SYSTEM,
    )
    summary["narrative"] = narrative_raw.strip()

    for update in summary.get("goal_updates", []):
        goal_id = update.get("goal_id")
        new_progress = update.get("new_progress")
        if goal_id and new_progress:
            try:
                update_goal_progress(db, goal_id, new_progress)
            except Exception:
                pass

    valid_goal_ids = {g["id"] for g in all_goals}
    for thread in summary.get("open_threads", []):
        text = thread.get("text") if isinstance(thread, dict) else str(thread)
        goal_id = thread.get("goal_id") if isinstance(thread, dict) else None
        if not text:
            continue
        linked_id = goal_id if goal_id in valid_goal_ids else None
        create_thread(db, ThreadCreate(goal_id=linked_id, text=text))

    today = date.today().isoformat()

    save_session(
        db,
        SessionCreate(
            date=today,
            session_type="morning",
            transcript=history,
            summary=json.dumps(summary),
            goals_snapshot=context["goals"],
            threads_snapshot=context["open_threads"],
        ),
    )

    return summary
