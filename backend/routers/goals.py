from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from backend.db.database import get_db
from backend.db.goals import (
    GoalCreate,
    GoalProgress,
    GoalRead,
    build_goal_context,
    create_goal,
    get_active_goals,
    get_goal_history,
    update_goal,
    update_goal_progress,
)
from backend.db.threads import (
    ThreadCreate,
    ThreadRead,
    create_thread,
    resolve_thread,
    get_threads_for_goal,
)

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalUpdateText(BaseModel):
    text: str


@router.get("", response_model=list[GoalRead])
def list_goals(db: DBSession = Depends(get_db)):
    return get_active_goals(db)


@router.get("/history/{goal_id}", response_model=list[GoalRead])
def goal_history(goal_id: int, db: DBSession = Depends(get_db)):
    history = get_goal_history(db, goal_id)
    if not history:
        raise HTTPException(404, detail="Goal not found")
    return history


@router.get("/context")
def goals_context(db: DBSession = Depends(get_db)):
    return build_goal_context(db)


@router.post("", response_model=GoalRead, status_code=201)
def create(payload: GoalCreate, db: DBSession = Depends(get_db)):
    return create_goal(db, payload)


@router.put("/{goal_id}", response_model=GoalRead)
def update(goal_id: int, body: GoalUpdateText, db: DBSession = Depends(get_db)):
    try:
        return update_goal(db, goal_id, body.text)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@router.patch("/{goal_id}/progress", response_model=GoalRead)
def patch_progress(goal_id: int, body: GoalProgress, db: DBSession = Depends(get_db)):
    try:
        return update_goal_progress(db, goal_id, body.progress)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


# ── Thread sub-routes ─────────────────────────────────────────────────────────

class ThreadBody(BaseModel):
    text: str


@router.get("/{goal_id}/threads", response_model=list[ThreadRead])
def list_goal_threads(goal_id: int, db: DBSession = Depends(get_db)):
    """All threads (open + resolved) for a goal, newest first."""
    return get_threads_for_goal(db, goal_id)


@router.post("/{goal_id}/threads", response_model=ThreadRead, status_code=201)
def create_goal_thread(goal_id: int, body: ThreadBody, db: DBSession = Depends(get_db)):
    """Manually create a thread under a goal."""
    return create_thread(db, ThreadCreate(goal_id=goal_id, text=body.text))


@router.patch("/{goal_id}/threads/{thread_id}/resolve", response_model=ThreadRead)
def resolve_goal_thread(goal_id: int, thread_id: int, db: DBSession = Depends(get_db)):
    """Mark a thread as resolved."""
    try:
        return resolve_thread(db, thread_id)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
