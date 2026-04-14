"""Calendar router.

GET  /calendar/today      → DaySchedule for today
GET  /calendar/tomorrow   → DaySchedule for tomorrow
GET  /calendar/date/{date} → DaySchedule for any YYYY-MM-DD
POST /calendar/action     → execute a confirmed CalendarAction
"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from backend.calendar import applescript
from backend.calendar.parser import build_day_schedule, DaySchedule
from backend.calendar.actions import CalendarAction, execute_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calendar", tags=["calendar"])


def _get_schedule(date_str: str) -> DaySchedule:
    try:
        raw = applescript.get_events(date_str)
    except RuntimeError as e:
        logger.exception("Calendar read failed for %s", date_str)
        # Common cause: backend launched via `conda run` loses macOS GUI session
        # context needed for AppleScript. Use `conda activate` + `uvicorn` instead.
        raise HTTPException(status_code=503, detail=f"Calendar unavailable: {e}")
    return build_day_schedule(raw, date_str)


@router.get("/today", response_model=DaySchedule)
def get_today():
    return _get_schedule(date.today().isoformat())


@router.get("/tomorrow", response_model=DaySchedule)
def get_tomorrow():
    return _get_schedule((date.today() + timedelta(days=1)).isoformat())


@router.get("/date/{date_str}", response_model=DaySchedule)
def get_date(date_str: str):
    try:
        date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    return _get_schedule(date_str)


@router.post("/action")
def run_action(action: CalendarAction):
    """Execute a user-confirmed calendar action."""
    try:
        result = execute_action(action)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Calendar error: {e}")
