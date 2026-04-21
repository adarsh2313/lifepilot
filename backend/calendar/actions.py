"""Calendar action schema and executor.

The LLM proposes a CalendarAction. The frontend shows a ConfirmCard.
Only after the user clicks Confirm does POST /calendar/action run execute_action().

Action types
------------
create  — make a new event
move    — change start/end of an existing event (identified by uid)
delete  — remove an event
"""

from typing import Literal, Optional
from pydantic import BaseModel

from backend.calendar import provider as cal_provider


class CalendarAction(BaseModel):
    action:        Literal["create", "move", "delete"]
    uid:           Optional[str] = None   # required for move/delete
    calendar_name: Optional[str] = None  # required for create
    title:         Optional[str] = None  # required for create
    start_iso:     Optional[str] = None  # required for create/move (ISO datetime)
    end_iso:       Optional[str] = None  # required for create/move
    notes:         Optional[str] = ""


def execute_action(action: CalendarAction) -> dict:
    """Execute a confirmed calendar action. Returns a result dict."""
    if action.action == "create":
        if not action.calendar_name or not action.title or not action.start_iso or not action.end_iso:
            raise ValueError("create requires calendar_name, title, start_iso, end_iso")
        uid = cal_provider.create_event(
            calendar_name=action.calendar_name,
            title=action.title,
            start_iso=action.start_iso,
            end_iso=action.end_iso,
            notes=action.notes or "",
        )
        return {"status": "created", "uid": uid}

    elif action.action == "move":
        if not action.uid or not action.start_iso or not action.end_iso:
            raise ValueError("move requires uid, start_iso, end_iso")
        cal_provider.move_event(
            uid=action.uid,
            new_start_iso=action.start_iso,
            new_end_iso=action.end_iso,
        )
        return {"status": "moved", "uid": action.uid}

    elif action.action == "delete":
        if not action.uid:
            raise ValueError("delete requires uid")
        cal_provider.delete_event(uid=action.uid)
        return {"status": "deleted", "uid": action.uid}

    else:
        raise ValueError(f"Unknown action: {action.action}")
