"""AppleScript bridge for macOS Calendar.app.

All reads and writes go through `osascript`. We never import EventKit or
use any other bridge — just subprocess + text parsing.

Public API
----------
get_events(date_str)         → list[dict]   raw event dicts for a given date (YYYY-MM-DD)
create_event(calendar, title, start_iso, end_iso, notes="") → str (uid)
move_event(uid, new_start_iso, new_end_iso)
delete_event(uid)
"""

import signal
import subprocess
from datetime import datetime, time
from threading import Lock


_OSA_LOCK = Lock()


# ── Low-level runner ──────────────────────────────────────────────────────────

def _run(script: str) -> str:
    """Run an AppleScript string via osascript stdin. Raises on non-zero exit."""
    # Use absolute binary + explicit "-" stdin mode for reliability.
    # Retry once if osascript gets interrupted by a signal (e.g., transient SIGINT).
    for attempt in (1, 2):
        with _OSA_LOCK:
            try:
                result = subprocess.run(
                    ["/usr/bin/osascript", "-l", "AppleScript", "-"],
                    input=script,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError("AppleScript timed out after 45s")
        if result.returncode == 0:
            return result.stdout.strip()
        if result.returncode == -2 and attempt == 1:
            continue

        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        if result.returncode < 0:
            try:
                sig_name = signal.Signals(-result.returncode).name
            except ValueError:
                sig_name = f"SIG{-result.returncode}"
            msg = stderr or stdout or f"terminated by signal {sig_name}"
        else:
            msg = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"AppleScript error: {msg}")

    raise RuntimeError("AppleScript error: interrupted")


# ── Read events ───────────────────────────────────────────────────────────────

_READ_SCRIPT = """\
set dayStart to date "{day_start}"
set dayEnd to date "{day_end}"

set output to ""
tell application "Calendar"
    repeat with aCal in calendars
        set calName to name of aCal
        repeat with evt in (every event of aCal)
            set evtStart to start date of evt
            if evtStart is greater than or equal to dayStart and evtStart is less than or equal to dayEnd then
                set eTitle to summary of evt
                set eStart to evtStart as string
                set eEnd   to (end date of evt) as string
                set eUid   to uid of evt
                set eNotes to ""
                set allDay to false
                -- Format: UID||TITLE||START_STR||END_STR||ALL_DAY||CALENDAR||NOTES
                set output to output & eUid & "||" & eTitle & "||" & eStart & "||" & eEnd & "||" & allDay & "||" & calName & "||" & eNotes & "\\n"
            end if
        end repeat
    end repeat
end tell
return output
"""


_AS_DATE_FMTS = [
    "%A, %d %B %Y at %I:%M:%S %p",   # Tuesday, 14 April 2026 at 10:30:00 PM
    "%A, %B %d, %Y at %I:%M:%S %p",  # Tuesday, April 14, 2026 at 10:30:00 PM
    "%A, %d %B %Y %H:%M:%S",
]


def _parse_as_date(s: str) -> datetime:
    """Parse an AppleScript 'date as string' value into a Python datetime.

    macOS returns narrow no-break space (U+202F) before AM/PM — normalise to
    a regular space before matching format strings.
    """
    s = s.strip().replace('\u202f', ' ')
    for fmt in _AS_DATE_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse AppleScript date: {s!r}")


def get_events(date_str: str) -> list[dict]:
    """Return raw event dicts for date_str (YYYY-MM-DD), sorted by start time."""
    day_start = datetime.fromisoformat(f"{date_str}T00:00:00")
    day_end = datetime.fromisoformat(f"{date_str}T23:59:59")
    day_start_s = day_start.strftime("%A, %d %B %Y %H:%M:%S")
    day_end_s = day_end.strftime("%A, %d %B %Y %H:%M:%S")
    script = (
        _READ_SCRIPT
        .replace("{day_start}", day_start_s)
        .replace("{day_end}", day_end_s)
    )
    raw = _run(script)
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("||", 6)
        if len(parts) < 6:
            continue
        uid, title, start_s, end_s, all_day, calendar = parts[:6]
        notes = parts[6] if len(parts) > 6 else ""
        try:
            start_dt = _parse_as_date(start_s)
            end_dt   = _parse_as_date(end_s)
        except ValueError:
            continue
        duration_sec = (end_dt - start_dt).total_seconds()
        inferred_all_day = (
            start_dt.time() == time(0, 0)
            and duration_sec >= (23 * 60 * 60)
        )
        clean_notes = notes.strip()
        if clean_notes.lower() == "missing value":
            clean_notes = ""
        events.append({
            "uid":      uid.strip(),
            "title":    title.strip(),
            "start":    start_dt.isoformat(),
            "end":      end_dt.isoformat(),
            "all_day":  all_day.strip().lower() == "true" or inferred_all_day,
            "calendar": calendar.strip(),
            "notes":    clean_notes,
        })
    events.sort(key=lambda e: e["start"])
    return events


# ── Write operations ──────────────────────────────────────────────────────────

def _iso_to_applescript_date(iso: str) -> str:
    """Convert ISO datetime string to AppleScript date literal."""
    dt = datetime.fromisoformat(iso)
    # AppleScript date format: "Monday, 14 April 2025 09:00:00"
    return dt.strftime("%A, %d %B %Y %H:%M:%S")


def create_event(calendar_name: str, title: str, start_iso: str, end_iso: str, notes: str = "") -> str:
    """Create a new event. Returns the UID of the created event."""
    start_str = _iso_to_applescript_date(start_iso)
    end_str   = _iso_to_applescript_date(end_iso)
    safe_notes = notes.replace('"', '\\"')
    safe_title = title.replace('"', '\\"')
    safe_cal   = calendar_name.replace('"', '\\"')

    script = f"""\
tell application "Calendar"
    set targetCal to calendar "{safe_cal}"
    set newEvent to make new event at end of events of targetCal with properties ¬
        {{summary:"{safe_title}", start date:date "{start_str}", end date:date "{end_str}", description:"{safe_notes}"}}
    return uid of newEvent
end tell
"""
    return _run(script)


def move_event(uid: str, new_start_iso: str, new_end_iso: str) -> None:
    """Move an existing event to new start/end times."""
    start_str = _iso_to_applescript_date(new_start_iso)
    end_str   = _iso_to_applescript_date(new_end_iso)
    safe_uid  = uid.replace('"', '\\"')

    script = f"""\
tell application "Calendar"
    repeat with aCal in calendars
        repeat with evt in (every event of aCal whose uid is "{safe_uid}")
            set start date of evt to date "{start_str}"
            set end date of evt to date "{end_str}"
            return "ok"
        end repeat
    end repeat
    return "not_found"
end tell
"""
    result = _run(script)
    if result == "not_found":
        raise ValueError(f"Event not found: {uid}")


def delete_event(uid: str) -> None:
    """Delete an event by UID."""
    safe_uid = uid.replace('"', '\\"')

    script = f"""\
tell application "Calendar"
    repeat with aCal in calendars
        repeat with evt in (every event of aCal whose uid is "{safe_uid}")
            delete evt
            return "ok"
        end repeat
    end repeat
    return "not_found"
end tell
"""
    result = _run(script)
    if result == "not_found":
        raise ValueError(f"Event not found: {uid}")
