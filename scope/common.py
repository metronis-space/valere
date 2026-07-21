"""Validation helpers shared by all Phase 0 contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .errors import ValidationReport


UNRESOLVED_MARKERS = {"", "TBD", "UNRESOLVED", "UNKNOWN", "PENDING"}


def is_unresolved(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and value.strip().upper() in UNRESOLVED_MARKERS
    )


def require_value(report: ValidationReport, data: Dict[str, Any], key: str, path: str) -> Any:
    value = data.get(key)
    if is_unresolved(value):
        report.add("%s.%s" % (path, key) if path else key, "unresolved", "A concrete value is required")
    return value


def require_mapping(report: ValidationReport, value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        report.add(path, "type", "Expected a mapping")
        return {}
    return value


def require_list(report: ValidationReport, value: Any, path: str) -> List[Any]:
    if not isinstance(value, list):
        report.add(path, "type", "Expected a list")
        return []
    return value


def parse_date(value: Any, path: str, report: ValidationReport) -> Optional[date]:
    if is_unresolved(value):
        report.add(path, "unresolved", "A concrete ISO-8601 date is required")
        return None
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
    except ValueError:
        report.add(path, "date", "Expected ISO-8601 date (YYYY-MM-DD)")
        return None


def parse_datetime(value: Any, path: str, report: ValidationReport) -> Optional[datetime]:
    if is_unresolved(value):
        report.add(path, "unresolved", "A concrete ISO-8601 timestamp is required")
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            report.add(path, "timezone", "Timestamp must include a UTC offset")
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        report.add(path, "datetime", "Expected ISO-8601 timestamp with UTC offset")
        return None


def duplicates(values: Iterable[Any]) -> List[Any]:
    seen = set()
    repeated = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated

