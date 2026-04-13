from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.db.models import Thread


class ThreadCreate(BaseModel):
    goal_id: int | None = None
    text: str


class ThreadRead(BaseModel):
    id: int
    goal_id: int | None
    text: str
    resolved: bool
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


def create_thread(db: DBSession, payload: ThreadCreate) -> Thread:
    thread = Thread(goal_id=payload.goal_id, text=payload.text)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def resolve_thread(db: DBSession, thread_id: int) -> Thread:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    thread.resolved = True
    thread.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(thread)
    return thread


def get_open_threads(db: DBSession) -> list[Thread]:
    return (
        db.query(Thread)
        .filter(Thread.resolved == False)
        .order_by(Thread.created_at)
        .all()
    )


def surface_threads(db: DBSession, limit: int = 5) -> list[dict]:
    """Returns open threads as dicts for LLM context."""
    threads = get_open_threads(db)[:limit]
    return [{"id": t.id, "text": t.text, "goal_id": t.goal_id} for t in threads]
