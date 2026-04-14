from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session as DBSession

from backend.db.models import Goal


# ── Pydantic schemas ──────────────────────────────────────────────────────────

VALID_HORIZONS = {"weekly", "monthly", "custom"}
VALID_PROGRESS = {"not_started", "in_progress", "at_risk", "achieved", "dropped"}


class GoalCreate(BaseModel):
    text: str
    horizon: Literal["weekly", "monthly", "custom"]
    due_date: str | None = None   # YYYY-MM-DD, required for custom
    period: str | None = None     # e.g. "2024-W15" or "2024-04"

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Goal text cannot be empty")
        return v.strip()

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("due_date must be in YYYY-MM-DD format")
        return v


class GoalRead(BaseModel):
    id: int
    text: str
    horizon: str
    due_date: str | None
    active: bool
    progress: str
    period: str | None
    version: int
    parent_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalProgress(BaseModel):
    progress: Literal["not_started", "in_progress", "at_risk", "achieved", "dropped"]


# ── CRUD ──────────────────────────────────────────────────────────────────────

def _auto_period(horizon: str) -> str | None:
    """Auto-generate period string for weekly/monthly goals."""
    today = date.today()
    if horizon == "weekly":
        return today.strftime("%G-W%V")   # ISO week, e.g. "2025-W16"
    if horizon == "monthly":
        return today.strftime("%Y-%m")    # e.g. "2025-04"
    return None


def create_goal(db: DBSession, payload: GoalCreate) -> Goal:
    period = payload.period or _auto_period(payload.horizon)
    goal = Goal(
        text=payload.text,
        horizon=payload.horizon,
        due_date=payload.due_date,
        period=period,
        active=True,
        progress="not_started",
        version=1,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def update_goal(db: DBSession, goal_id: int, new_text: str) -> Goal:
    """Versioned update: deactivates old row, inserts new one."""
    old = db.get(Goal, goal_id)
    if old is None or not old.active:
        raise ValueError(f"Active goal {goal_id} not found")

    old.active = False
    db.flush()

    new = Goal(
        text=new_text.strip(),
        horizon=old.horizon,
        due_date=old.due_date,
        period=old.period,
        active=True,
        progress=old.progress,
        version=old.version + 1,
        parent_id=old.id,
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


def get_active_goals(db: DBSession) -> list[Goal]:
    return db.query(Goal).filter(Goal.active == True).order_by(Goal.created_at).all()


def get_goal_history(db: DBSession, root_id: int) -> list[Goal]:
    """Returns all versions of a goal chain, oldest first."""
    results: list[Goal] = []
    current_id: int | None = root_id

    # Walk up to find the root (no parent)
    root = db.get(Goal, root_id)
    if root is None:
        return []
    while root.parent_id is not None:
        root = db.get(Goal, root.parent_id)

    # Walk down collecting the chain
    def collect(goal_id: int):
        g = db.get(Goal, goal_id)
        if g:
            results.append(g)
            child = db.query(Goal).filter(Goal.parent_id == g.id).first()
            if child:
                collect(child.id)

    collect(root.id)
    return results


def update_goal_progress(db: DBSession, goal_id: int, progress: str) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None or not goal.active:
        raise ValueError(f"Active goal {goal_id} not found")
    goal.progress = progress
    goal.updated_at = datetime.utcnow()
    if progress == "dropped":
        goal.active = False
    db.commit()
    db.refresh(goal)
    return goal


def build_goal_context(db: DBSession) -> dict:
    """Returns a structured dict suitable for inclusion in LLM system prompts."""
    goals = get_active_goals(db)
    return {
        "weekly": [
            {"id": g.id, "text": g.text, "period": g.period, "progress": g.progress}
            for g in goals if g.horizon == "weekly"
        ],
        "monthly": [
            {"id": g.id, "text": g.text, "period": g.period, "progress": g.progress}
            for g in goals if g.horizon == "monthly"
        ],
        "custom": [
            {"id": g.id, "text": g.text, "due_date": g.due_date, "progress": g.progress}
            for g in goals if g.horizon == "custom"
        ],
    }
