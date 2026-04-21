"""Builds the context dict passed to the evening and morning coach."""

import json
from datetime import date

from sqlalchemy.orm import Session as DBSession

from backend.db.goals import build_goal_context
from backend.db.sessions import get_latest_session, get_recent_sessions
from backend.db.threads import surface_threads


def build_morning_context(db: DBSession) -> dict:
    """
    Returns a dict with everything the morning coach needs:
      - goals: structured dict from build_goal_context
      - open_threads: list of unresolved follow-up items (with goal_id linkage)
      - recent_sessions: last 7 sessions as compact dicts {date, session_type, one_line_summary, goal_updates}
      - schedule: DaySchedule dict for today (events + free_blocks), or None if calendar unavailable
      - issues: list of detected issues from morning.detect_issues()
    """
    goals = build_goal_context(db)
    open_threads = surface_threads(db)

    recent_sessions = get_recent_sessions(db, limit=7)

    # Try to fetch today's calendar schedule; fail gracefully
    schedule = None
    issues = []
    try:
        from backend.calendar import provider as cal_provider
        from backend.calendar.parser import build_day_schedule
        from backend.coach.morning import detect_issues

        today_str = date.today().isoformat()
        raw_events = cal_provider.get_events(today_str)
        day_schedule = build_day_schedule(raw_events, today_str)
        schedule = day_schedule.model_dump()
        issues = detect_issues(
            events=schedule["events"],
            free_blocks=schedule["free_blocks"],
            goals=goals,
        )
    except Exception:
        pass  # Calendar unavailable — morning session continues without it

    return {
        "goals": goals,
        "open_threads": open_threads,
        "recent_sessions": recent_sessions,
        "schedule": schedule,
        "issues": issues,
    }


def build_evening_context(db: DBSession) -> dict:
    """
    Returns a dict with everything the evening coach needs:
      - goals: structured dict from build_goal_context
      - open_threads: list of unresolved follow-up items
      - yesterday_summary: one-line summary from the previous evening session (or None)
    """
    goals = build_goal_context(db)
    open_threads = surface_threads(db)

    yesterday_summary: str | None = None
    last_evening = get_latest_session(db, session_type="evening")
    if last_evening and last_evening.summary:
        try:
            data = json.loads(last_evening.summary)
            yesterday_summary = data.get("one_line_summary")
        except (json.JSONDecodeError, AttributeError):
            yesterday_summary = last_evening.summary  # fallback: raw text

    return {
        "goals": goals,
        "open_threads": open_threads,
        "yesterday_summary": yesterday_summary,
    }
