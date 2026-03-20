from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class RosterEntryType(StrEnum):
    ASSIGNMENT = "assignment"
    WORKED = "worked"
    UNAVAILABLE = "unavailable"
    OTHER = "other"


@dataclass(slots=True)
class RosterEntry:
    source_id: str
    entry_type: RosterEntryType
    roster_date: date
    title: str
    start_at: datetime | None
    end_at: datetime | None
    break_minutes: int | None = None
    description: str | None = None
    raw_label: str | None = None
    source_uri: str | None = None
    css_classes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class MonthNavigation:
    current_period: str | None
    previous_period: str | None
    next_period: str | None
    available_periods: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class ParsedRosterMonth:
    navigation: MonthNavigation
    entries: list[RosterEntry]


@dataclass(slots=True)
class FilledPeriodCheck:
    period: str
    entry_count: int
    syncable_event_count: int
    fetch_source: str
    fetch_url: str


@dataclass(slots=True)
class FilledPeriodScan:
    start_period: str
    last_filled_period: str | None
    stop_period: str | None
    periods: list[FilledPeriodCheck]
    error_period: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class CalendarEventDraft:
    source_id: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    description: str | None = None
    location: str | None = None
