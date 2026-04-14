"""Evening session state machine.

Lifecycle:
  start()  → returns opening coach message, session_id
  chat()   → user sends a message, returns coach reply
  end()    → generates summary + narrative, writes journal, persists to DB
"""

import json
import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session as DBSession

from backend.config import get_config
from backend.coach.context import build_evening_context
from backend.coach.prompts import (
    build_evening_system,
    SUMMARY_SYSTEM, SUMMARY_PROMPT,
    NARRATIVE_SYSTEM, NARRATIVE_PROMPT,
)
from backend.db.goals import update_goal_progress
from backend.db.sessions import save_session, SessionCreate
from backend.db.threads import create_thread, ThreadCreate
from backend.llm.factory import get_provider

OPENING_MESSAGE = "Hey — how was your day? What's top of mind?"


def _parse_json_response(raw: str) -> dict | None:
    """
    Robustly extract JSON from an LLM response.
    Handles: plain JSON, ```json fences, ``` fences, stray 'json' prefix.
    Returns parsed dict or None on failure.
    """
    text = raw.strip()

    # Strip any markdown code fence (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(l for l in inner if l.strip() != "```").strip()

    # Find the first { and last } to extract the JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


async def start_session(db: DBSession) -> dict:
    ctx = build_evening_context(db)
    system = build_evening_system(
        goals=ctx["goals"],
        open_threads=ctx["open_threads"],
        yesterday_summary=ctx["yesterday_summary"],
    )
    return {
        "system": system,
        "context": ctx,
        "history": [{"role": "assistant", "content": OPENING_MESSAGE}],
        "opening_message": OPENING_MESSAGE,
    }


async def chat_turn(system: str, history: list[dict], user_message: str) -> str:
    history.append({"role": "user", "content": user_message})
    provider = get_provider(get_config())
    reply = await provider.chat(messages=history, system=system)
    history.append({"role": "assistant", "content": reply})
    return reply


async def end_session(db: DBSession, history: list[dict], context: dict) -> dict:
    """
    Two LLM calls:
      1. Summary call → structured JSON (wins, blockers, goal_updates, open_threads, one_line_summary)
      2. Narrative call → first-person journal paragraph for the human reader

    Then: apply goal updates, create threads, save session to DB, write journal.
    Returns the summary dict with 'narrative' added.
    """
    provider = get_provider(get_config())

    transcript_text = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in history
    )

    # Collect goal IDs for the summary prompt
    all_goals = (
        context["goals"].get("weekly", []) +
        context["goals"].get("monthly", []) +
        context["goals"].get("custom", [])
    )
    # Build a readable goal list for the summary prompt
    goal_list_lines = [
        f"  id={g['id']}: {g['text']} [{g['progress']}]"
        for g in all_goals
    ]
    goal_list_str = "\n".join(goal_list_lines) if goal_list_lines else "  (no active goals)"

    # ── Call 1: structured summary ────────────────────────────────────────────
    summary_raw = await provider.chat(
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
            transcript=transcript_text,
            goal_list=goal_list_str,
        )}],
        system=SUMMARY_SYSTEM,
    )

    summary = _parse_json_response(summary_raw)
    if summary is None:
        summary = {"one_line_summary": "Session ended — summary could not be parsed.", "raw": summary_raw}

    # ── Call 2: narrative journal paragraph ───────────────────────────────────
    narrative_raw = await provider.chat(
        messages=[{"role": "user", "content": NARRATIVE_PROMPT.format(transcript=transcript_text)}],
        system=NARRATIVE_SYSTEM,
    )
    summary["narrative"] = narrative_raw.strip()

    # ── Apply goal progress updates ───────────────────────────────────────────
    for update in summary.get("goal_updates", []):
        goal_id = update.get("goal_id")
        new_progress = update.get("new_progress")
        if goal_id and new_progress:
            try:
                update_goal_progress(db, goal_id, new_progress)
            except Exception:
                pass

    # ── Create open threads, linked to goals ─────────────────────────────────
    valid_goal_ids = {g["id"] for g in all_goals}
    for thread in summary.get("open_threads", []):
        text = thread.get("text") if isinstance(thread, dict) else str(thread)
        goal_id = thread.get("goal_id") if isinstance(thread, dict) else None
        if not text:
            continue
        # Only link to goal if ID is valid; otherwise store unlinked
        linked_id = goal_id if goal_id in valid_goal_ids else None
        create_thread(db, ThreadCreate(goal_id=linked_id, text=text))

    today = date.today().isoformat()

    # ── Persist session ───────────────────────────────────────────────────────
    save_session(
        db,
        SessionCreate(
            date=today,
            session_type="evening",
            transcript=history,
            summary=json.dumps(summary),
            goals_snapshot=context["goals"],
            threads_snapshot=context["open_threads"],
        ),
    )

    # ── Write journal ─────────────────────────────────────────────────────────
    _write_journal(today, summary)

    return summary


def _write_journal(today: str, summary: dict) -> None:
    """
    Journal is for the human reader only.
    Leads with the narrative paragraph. Full session data lives in the DB.
    """
    config = get_config()
    journal_dir = Path(os.path.expanduser(config.get("journal_dir", "~/LifePilot/journal")))
    journal_dir.mkdir(parents=True, exist_ok=True)

    journal_path = journal_dir / f"{today}.md"

    # Parse the date for a friendlier heading
    try:
        d = datetime.strptime(today, "%Y-%m-%d")
        heading = d.strftime("%B %-d, %Y")   # e.g. "April 14, 2025"
    except ValueError:
        heading = today

    lines = [
        f"# {heading}",
        "",
        summary.get("narrative", "_No narrative generated._"),
        "",
    ]

    journal_path.write_text("\n".join(lines), encoding="utf-8")
