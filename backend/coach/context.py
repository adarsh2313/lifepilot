"""Builds the context dict passed to the evening (and later morning) coach."""

import json

from sqlalchemy.orm import Session as DBSession

from backend.db.goals import build_goal_context
from backend.db.sessions import get_latest_session
from backend.db.threads import surface_threads


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
