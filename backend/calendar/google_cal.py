"""Google Calendar API backend.

Same public interface as applescript.py so provider.py can swap between them:
    get_events(date_str)  → list[dict]
    create_event(...)     → str (event id / uid)
    move_event(...)
    delete_event(...)

Reads credentials from google_credentials.json (written by auth.py).
The Google API service is built lazily and cached for the process lifetime.
"""

import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache

from googleapiclient.discovery import build

from backend.calendar.auth import load_credentials

logger = logging.getLogger(__name__)

# Re-use one service object across requests
_service = None
_creds   = None


def _get_service():
    """Return a cached service for the main thread."""
    global _service, _creds
    if _service is None:
        _creds   = load_credentials()
        _service = build("calendar", "v3", credentials=_creds, cache_discovery=False)
    return _service


def _new_service():
    """Build a fresh service instance (required per-thread — httplib2 is not thread-safe)."""
    creds = load_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _local_midnight(date_str: str, offset_hours: int = 0) -> str:
    """Return an RFC3339 string for midnight (+ offset hours) on date_str in local time.

    Produces format like 2026-04-14T00:00:00+05:30 (colon in offset required by Google).
    """
    dt = datetime.fromisoformat(f"{date_str}T00:00:00")
    dt = dt + timedelta(hours=offset_hours)
    local_offset = datetime.now(timezone.utc).astimezone().utcoffset()
    dt = dt.replace(tzinfo=timezone(local_offset))
    # isoformat() gives +05:30 with colon — correct for RFC3339
    return dt.isoformat()


def _parse_gcal_dt(dt_obj: dict) -> datetime:
    """Parse a Google Calendar dateTime or date dict into a Python datetime."""
    if "dateTime" in dt_obj:
        return datetime.fromisoformat(dt_obj["dateTime"])
    # all-day event → date only
    return datetime.fromisoformat(dt_obj["date"] + "T00:00:00")


def get_events(date_str: str) -> list[dict]:
    """Fetch all events across all calendars for the given date (YYYY-MM-DD).

    Uses a batch-style approach: build all requests then execute in parallel
    via a thread pool so we don't pay N×latency for N calendars.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    service  = _get_service()
    time_min = _local_midnight(date_str, 0)
    time_max = _local_midnight(date_str, 24)

    cal_list  = service.calendarList().list().execute()
    calendars = cal_list.get("items", [])

    def _fetch_cal(cal):
        svc      = _new_service()   # fresh per-thread — httplib2 is not thread-safe
        cal_id   = cal["id"]
        cal_name = cal.get("summary", cal_id)
        try:
            result = svc.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=100,
            ).execute()
        except Exception as e:
            logger.warning("Skipping calendar %s: %s", cal_name, e)
            return []

        items = []
        for item in result.get("items", []):
            if item.get("status") == "cancelled":
                continue
            start_obj = item.get("start", {})
            end_obj   = item.get("end",   {})
            all_day   = "date" in start_obj and "dateTime" not in start_obj
            start_dt  = _parse_gcal_dt(start_obj)
            end_dt    = _parse_gcal_dt(end_obj)
            duration  = max(0, int((end_dt - start_dt).total_seconds() / 60))
            items.append({
                "uid":          item["id"],
                "title":        item.get("summary", "(no title)"),
                "start":        start_dt.isoformat(),
                "end":          end_dt.isoformat(),
                "all_day":      all_day,
                "calendar":     cal_name,
                "notes":        item.get("description", ""),
                "duration_min": duration,
            })
        return items

    events = []
    with ThreadPoolExecutor(max_workers=min(len(calendars), 8)) as pool:
        futures = {pool.submit(_fetch_cal, cal): cal for cal in calendars}
        for future in as_completed(futures):
            events.extend(future.result())

    events.sort(key=lambda e: e["start"])
    return events


def create_event(calendar_name: str, title: str, start_iso: str, end_iso: str, notes: str = "") -> str:
    """Create an event. calendar_name is matched against calendar summaries."""
    service = _get_service()

    cal_id = _resolve_calendar_id(service, calendar_name)

    body = {
        "summary": title,
        "description": notes,
        "start": {"dateTime": start_iso, "timeZone": _local_tz()},
        "end":   {"dateTime": end_iso,   "timeZone": _local_tz()},
    }
    result = service.events().insert(calendarId=cal_id, body=body).execute()
    return result["id"]


def move_event(uid: str, new_start_iso: str, new_end_iso: str) -> None:
    """Update start/end of an event. Searches all calendars for the uid."""
    service = _get_service()
    cal_id  = _find_event_calendar(service, uid)

    event = service.events().get(calendarId=cal_id, eventId=uid).execute()
    tz = event.get("start", {}).get("timeZone") or _local_tz()
    event["start"] = {"dateTime": new_start_iso, "timeZone": tz}
    event["end"]   = {"dateTime": new_end_iso,   "timeZone": tz}
    service.events().update(calendarId=cal_id, eventId=uid, body=event).execute()


def delete_event(uid: str) -> None:
    """Delete an event by id. Searches all calendars."""
    service = _get_service()
    cal_id  = _find_event_calendar(service, uid)
    service.events().delete(calendarId=cal_id, eventId=uid).execute()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _local_tz() -> str:
    import time as _time
    return _time.tzname[0]


def _resolve_calendar_id(service, name: str) -> str:
    """Return calendar id whose summary matches name (case-insensitive)."""
    cal_list = service.calendarList().list().execute()
    for cal in cal_list.get("items", []):
        if cal.get("summary", "").lower() == name.lower():
            return cal["id"]
    # Fall back to primary
    logger.warning("Calendar %r not found, using primary", name)
    return "primary"


def _find_event_calendar(service, event_id: str) -> str:
    """Search all calendars for an event id, return its calendar id."""
    cal_list = service.calendarList().list().execute()
    for cal in cal_list.get("items", []):
        try:
            service.events().get(calendarId=cal["id"], eventId=event_id).execute()
            return cal["id"]
        except Exception:
            continue
    raise ValueError(f"Event not found in any calendar: {event_id}")
