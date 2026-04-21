import json
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.db.models import Session as SessionModel


class SessionCreate(BaseModel):
    date: str                                          # YYYY-MM-DD
    session_type: Literal["morning", "evening"]
    transcript: list[dict] | None = None               # [{role, content}, ...]
    summary: str | None = None
    goals_snapshot: dict | None = None
    threads_snapshot: list[dict] | None = None


def save_session(db: DBSession, payload: SessionCreate) -> SessionModel:
    session = SessionModel(
        date=payload.date,
        session_type=payload.session_type,
        transcript=json.dumps(payload.transcript) if payload.transcript else None,
        summary=payload.summary,
        goals_snapshot=json.dumps(payload.goals_snapshot) if payload.goals_snapshot else None,
        threads_snapshot=json.dumps(payload.threads_snapshot) if payload.threads_snapshot else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_latest_session(db: DBSession, session_type: str | None = None) -> SessionModel | None:
    q = db.query(SessionModel)
    if session_type:
        q = q.filter(SessionModel.session_type == session_type)
    return q.order_by(SessionModel.created_at.desc()).first()


def get_sessions_for_date(db: DBSession, target_date: str) -> list[SessionModel]:
    return (
        db.query(SessionModel)
        .filter(SessionModel.date == target_date)
        .order_by(SessionModel.created_at)
        .all()
    )


def get_recent_sessions(db: DBSession, limit: int = 7) -> list[dict]:
    """Return the last `limit` sessions as compact dicts for LLM context.

    Each dict contains:
      date, session_type, one_line_summary, goal_updates (list of {goal_id, text, new_progress})
    """
    rows = (
        db.query(SessionModel)
        .order_by(SessionModel.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in reversed(rows):   # oldest first so the stack reads chronologically
        entry: dict = {
            "date": row.date,
            "session_type": row.session_type,
            "one_line_summary": None,
            "goal_updates": [],
        }
        if row.summary:
            try:
                data = json.loads(row.summary)
                entry["one_line_summary"] = data.get("one_line_summary")
                entry["goal_updates"] = data.get("goal_updates") or []
            except (json.JSONDecodeError, AttributeError):
                entry["one_line_summary"] = str(row.summary)[:120]
        result.append(entry)
    return result
