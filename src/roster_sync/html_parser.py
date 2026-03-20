from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from .models import MonthNavigation, ParsedRosterMonth, RosterEntry, RosterEntryType


TIME_RANGE_PATTERN = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
BREAK_PATTERN = re.compile(r"\((\d+)\s+min\.\s+pauze\)")


@dataclass(slots=True)
class RosterHtmlParser:
    timezone: ZoneInfo

    def parse_month(self, html: str) -> ParsedRosterMonth:
        soup = BeautifulSoup(html, "html.parser")
        navigation = self._parse_navigation(soup)
        entries: list[RosterEntry] = []
        current_period = navigation.current_period

        for day_cell in soup.select("table.calender td[title]"):
            cell_date = self._parse_date(day_cell["title"])
            if current_period and cell_date.strftime("%Y-%m") != current_period:
                continue
            for item in day_cell.find_all("div", attrs={"uo": True}, recursive=False):
                entry = self._parse_entry(item, cell_date)
                if entry is not None:
                    entries.append(entry)

        return ParsedRosterMonth(navigation=navigation, entries=entries)

    def _parse_navigation(self, soup: BeautifulSoup) -> MonthNavigation:
        current_option = soup.select_one("select option[selected]")
        available_periods = tuple(
            option.get("value", "")
            for option in soup.select("select option")
            if option.get("value")
        )

        previous_period = None
        next_period = None
        for link in soup.select("table.calender thead a[href]"):
            href = link["href"]
            label = link.get_text(" ", strip=True).lower()
            period = self._extract_period_from_href(href)
            if "vorige maand" in label:
                previous_period = period
            if "volgende maand" in label:
                next_period = period

        return MonthNavigation(
            current_period=current_option.get("value") if current_option else None,
            previous_period=previous_period,
            next_period=next_period,
            available_periods=available_periods,
        )

    def _parse_entry(self, item: Tag, cell_date: date) -> RosterEntry | None:
        classes = tuple(item.get("class", []))
        source_uri = item.get("uo")
        title = self._extract_title(item)
        text = item.get_text(" ", strip=True)

        if "ass" in classes:
            start_at, end_at = self._extract_datetimes(cell_date, text)
            return RosterEntry(
                source_id=source_uri or f"assignment:{cell_date.isoformat()}:{title}",
                entry_type=RosterEntryType.ASSIGNMENT,
                roster_date=cell_date,
                title=title or "Untitled assignment",
                start_at=start_at,
                end_at=end_at,
                break_minutes=self._extract_break_minutes(text),
                description=text,
                raw_label=text,
                source_uri=source_uri,
                css_classes=classes,
            )

        if "agen-onbeschikbaar" in classes:
            start_at = datetime.combine(cell_date, time.min, self.timezone)
            return RosterEntry(
                source_id=source_uri or f"unavailable:{cell_date.isoformat()}",
                entry_type=RosterEntryType.UNAVAILABLE,
                roster_date=cell_date,
                title=title or text or "Unavailable",
                start_at=start_at,
                end_at=start_at + timedelta(days=1),
                description=text,
                raw_label=text,
                source_uri=source_uri,
                css_classes=classes,
            )

        if "agen-werk" in classes:
            start_at, end_at = self._extract_worked_datetimes(cell_date, text)
            return RosterEntry(
                source_id=source_uri or f"worked:{cell_date.isoformat()}:{text}",
                entry_type=RosterEntryType.WORKED,
                roster_date=cell_date,
                title=title or "Worked",
                start_at=start_at,
                end_at=end_at,
                description=text,
                raw_label=text,
                source_uri=source_uri,
                css_classes=classes,
            )

        return RosterEntry(
            source_id=source_uri or f"other:{cell_date.isoformat()}:{text}",
            entry_type=RosterEntryType.OTHER,
            roster_date=cell_date,
            title=title or text or "Unknown entry",
            start_at=None,
            end_at=None,
            description=text,
            raw_label=text,
            source_uri=source_uri,
            css_classes=classes,
        )

    def _extract_title(self, item: Tag) -> str:
        nested = item.find("div")
        if nested and nested.get("title"):
            return nested["title"].strip()
        if nested:
            return nested.get_text(" ", strip=True)
        text = item.get_text(" ", strip=True)
        if text:
            return text
        return item.get("title", "").strip()

    def _extract_datetimes(
        self, cell_date: date, text: str
    ) -> tuple[datetime | None, datetime | None]:
        match = TIME_RANGE_PATTERN.search(text)
        if not match:
            return None, None
        return (
            self._combine(cell_date, match.group(1)),
            self._combine(cell_date, match.group(2)),
        )

    def _extract_worked_datetimes(
        self, cell_date: date, text: str
    ) -> tuple[datetime | None, datetime | None]:
        return self._extract_datetimes(cell_date, text)

    def _extract_break_minutes(self, text: str) -> int | None:
        match = BREAK_PATTERN.search(text)
        return int(match.group(1)) if match else None

    def _combine(self, value: date, hhmm: str) -> datetime:
        hour, minute = (int(part) for part in hhmm.split(":"))
        return datetime.combine(value, time(hour=hour, minute=minute), self.timezone)

    def _parse_date(self, raw_value: str) -> date:
        return date.fromisoformat(raw_value)

    def _extract_period_from_href(self, href: str) -> str | None:
        query = parse_qs(urlparse(href).query)
        values = query.get("periode")
        return values[0] if values else None
