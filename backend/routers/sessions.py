"""Session router — evening check-in endpoints.

Session state (system prompt + message history) is kept server-side in a
simple in-memory dict keyed by session_id. This is intentionally simple:
one active session at a time is the expected usage pattern.
"""

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.coach.evening import start_session, chat_turn, end_session
from backend.coach.morning import start_morning_session, chat_turn as morning_chat_turn, end_morning_session
from backend.db.database import get_db

router = APIRouter(prefix="/session", tags=["session"])

# In-memory session store: {session_id: {system, history, context, session_type}}
_active_sessions: dict[str, dict[str, Any]] = {}


# ── Schemas ───────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    session_type: Literal["evening", "morning"] = "evening"


class StartResponse(BaseModel):
    session_id: str
    message: str          # opening coach message
    session_type: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    message: str


class EndRequest(BaseModel):
    session_id: str


class EndResponse(BaseModel):
    summary: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartResponse)
async def session_start(req: StartRequest, db: DBSession = Depends(get_db)):
    """Start a new coaching session (evening or morning)."""
    if req.session_type == "morning":
        state = await start_morning_session(db)
    else:
        state = await start_session(db)

    session_id = str(uuid.uuid4())
    state["session_type"] = req.session_type
    _active_sessions[session_id] = state
    return StartResponse(
        session_id=session_id,
        message=state["opening_message"],
        session_type=req.session_type,
    )


@router.post("/chat", response_model=ChatResponse)
async def session_chat(req: ChatRequest):
    """Send a user message and get the coach's reply."""
    state = _active_sessions.get(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found. Call /session/start first.")

    reply = await chat_turn(
        system=state["system"],
        history=state["history"],
        user_message=req.message,
    )
    return ChatResponse(message=reply)


@router.post("/end", response_model=EndResponse)
async def session_end(req: EndRequest, db: DBSession = Depends(get_db)):
    """End the session: generate summary, save to DB."""
    state = _active_sessions.pop(req.session_id, None)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found or already ended.")

    if state.get("session_type") == "morning":
        summary = await end_morning_session(
            db=db,
            history=state["history"],
            context=state["context"],
        )
    else:
        summary = await end_session(
            db=db,
            history=state["history"],
            context=state["context"],
        )
    return EndResponse(summary=summary)


@router.get("/list")
def session_list(db: DBSession = Depends(get_db)):
    """List saved sessions (most recent first)."""
    from backend.db.models import Session as SessionModel
    sessions = (
        db.query(SessionModel)
        .order_by(SessionModel.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": s.id,
            "date": s.date,
            "session_type": s.session_type,
            "one_line_summary": _extract_summary(s.summary),
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


def _extract_summary(raw: str | None) -> str | None:
    if not raw:
        return None
    import json
    try:
        return json.loads(raw).get("one_line_summary")
    except Exception:
        return raw[:100]
