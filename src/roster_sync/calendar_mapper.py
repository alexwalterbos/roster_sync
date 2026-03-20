from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import CalendarEventDraft, RosterEntry, RosterEntryType


def roster_entry_to_event(entry: RosterEntry) -> CalendarEventDraft | None:
    if entry.entry_type is RosterEntryType.ASSIGNMENT:
        if entry.start_at is None or entry.end_at is None:
            return None

        return CalendarEventDraft(
            source_id=entry.source_id,
            title=entry.title,
            start_at=entry.start_at,
            end_at=entry.end_at,
            all_day=False,
            description=entry.description,
        )

    if entry.entry_type is RosterEntryType.UNAVAILABLE:
        start_at = entry.start_at
        end_at = entry.end_at

        if start_at is None or end_at is None:
            start_at = datetime.combine(
                entry.roster_date,
                time.min,
                tzinfo=_entry_timezone(entry),
            )
            end_at = start_at + timedelta(days=1)

        return CalendarEventDraft(
            source_id=entry.source_id,
            title=entry.title,
            start_at=start_at,
            end_at=end_at,
            all_day=True,
            description=entry.description,
        )

    return None


def map_entries_to_events(entries: list[RosterEntry]) -> list[CalendarEventDraft]:
    events: list[CalendarEventDraft] = []
    for entry in entries:
        event = roster_entry_to_event(entry)
        if event is not None:
            events.append(event)
    return events


def _entry_timezone(entry: RosterEntry):
    if entry.start_at is not None:
        return entry.start_at.tzinfo
    if entry.end_at is not None:
        return entry.end_at.tzinfo
    return None
