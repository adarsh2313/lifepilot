"""Parse raw event dicts into CalendarEvent models and compute free blocks."""

from datetime import datetime, date, timedelta
from typing import Optional
from pydantic import BaseModel


class CalendarEvent(BaseModel):
    uid:      str
    title:    str
    start:    str          # ISO datetime string
    end:      str          # ISO datetime string
    all_day:  bool
    calendar: str
    notes:    str = ""
    duration_min: int      # computed

    @property
    def start_dt(self) -> datetime:
        return datetime.fromisoformat(self.start)

    @property
    def end_dt(self) -> datetime:
        return datetime.fromisoformat(self.end)

    @property
    def start_time_str(self) -> str:
        return self.start_dt.strftime("%H:%M")

    @property
    def end_time_str(self) -> str:
        return self.end_dt.strftime("%H:%M")


class FreeBlock(BaseModel):
    start:       str   # ISO datetime
    end:         str   # ISO datetime
    duration_min: int


class DaySchedule(BaseModel):
    date:        str              # YYYY-MM-DD
    events:      list[CalendarEvent]
    free_blocks: list[FreeBlock]  # gaps between events (8am–10pm window)


def parse_events(raw_events: list[dict]) -> list[CalendarEvent]:
    """Convert raw dicts into CalendarEvent models.

    Strips timezone info from datetimes so naive comparisons work throughout.
    """
    result = []
    for e in raw_events:
        start_dt = datetime.fromisoformat(e["start"]).replace(tzinfo=None)
        end_dt   = datetime.fromisoformat(e["end"]).replace(tzinfo=None)
        duration = max(0, int((end_dt - start_dt).total_seconds() / 60))
        result.append(CalendarEvent(
            uid=e["uid"],
            title=e["title"],
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            all_day=e["all_day"],
            calendar=e["calendar"],
            notes=e.get("notes", ""),
            duration_min=duration,
        ))
    return sorted(result, key=lambda e: e.start)


def compute_free_blocks(
    events: list[CalendarEvent],
    date_str: str,
    day_start_hour: int = 8,
    day_end_hour: int = 22,
    min_gap_min: int = 15,
) -> list[FreeBlock]:
    """
    Compute free blocks in the day_start..day_end window.
    All-day events are ignored (they don't block time).
    Overlapping events are merged before gap detection.
    """
    day = date.fromisoformat(date_str)
    window_start = datetime(day.year, day.month, day.day, day_start_hour, 0)
    window_end   = datetime(day.year, day.month, day.day, day_end_hour,   0)

    # Only timed events that overlap the window
    timed = [
        e for e in events
        if not e.all_day
        and e.end_dt > window_start
        and e.start_dt < window_end
    ]

    # Clamp to window and merge overlapping intervals
    intervals = []
    for e in timed:
        s = max(e.start_dt, window_start)
        en = min(e.end_dt, window_end)
        if s < en:
            intervals.append((s, en))
    intervals.sort()

    merged: list[tuple[datetime, datetime]] = []
    for s, en in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], en))
        else:
            merged.append((s, en))

    # Gaps between merged intervals
    free: list[FreeBlock] = []
    cursor = window_start
    for s, en in merged:
        if s > cursor:
            gap_min = int((s - cursor).total_seconds() / 60)
            if gap_min >= min_gap_min:
                free.append(FreeBlock(
                    start=cursor.isoformat(),
                    end=s.isoformat(),
                    duration_min=gap_min,
                ))
        cursor = max(cursor, en)
    if cursor < window_end:
        gap_min = int((window_end - cursor).total_seconds() / 60)
        if gap_min >= min_gap_min:
            free.append(FreeBlock(
                start=cursor.isoformat(),
                end=window_end.isoformat(),
                duration_min=gap_min,
            ))
    return free


def build_day_schedule(raw_events: list[dict], date_str: str) -> DaySchedule:
    events = parse_events(raw_events)
    free   = compute_free_blocks(events, date_str)
    return DaySchedule(date=date_str, events=events, free_blocks=free)
