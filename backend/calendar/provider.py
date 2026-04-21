"""Calendar provider dispatcher.

Reads `calendar_backend` from config.json:
    "google"      → backend/calendar/google_cal.py   (default)
    "applescript" → backend/calendar/applescript.py

All callers import from here, never directly from a backend module.
"""

from backend.config import get_config


def _backend():
    cfg = get_config()
    backend = cfg.get("calendar_backend", "google")
    if backend == "applescript":
        from backend.calendar import applescript
        return applescript
    else:
        from backend.calendar import google_cal
        return google_cal


def get_events(date_str: str) -> list[dict]:
    return _backend().get_events(date_str)


def create_event(calendar_name: str, title: str, start_iso: str, end_iso: str, notes: str = "") -> str:
    return _backend().create_event(calendar_name, title, start_iso, end_iso, notes)


def move_event(uid: str, new_start_iso: str, new_end_iso: str) -> None:
    return _backend().move_event(uid, new_start_iso, new_end_iso)


def delete_event(uid: str) -> None:
    return _backend().delete_event(uid)
