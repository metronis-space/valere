"""Validation helpers shared by all Phase 0 contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from utils.values import (
    coerce_date,
    coerce_datetime,
    duplicates,
    is_unresolved,
)

from .errors import ValidationReport


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
        return coerce_date(value)
    except (TypeError, ValueError):
        report.add(path, "date", "Expected ISO-8601 date (YYYY-MM-DD)")
        return None


def parse_datetime(value: Any, path: str, report: ValidationReport) -> Optional[datetime]:
    if is_unresolved(value):
        report.add(path, "unresolved", "A concrete ISO-8601 timestamp is required")
        return None
    try:
        return coerce_datetime(value)
    except ValueError as exc:
        if "UTC offset" in str(exc):
            report.add(path, "timezone", "Timestamp must include a UTC offset")
            return None
        report.add(path, "datetime", "Expected ISO-8601 timestamp with UTC offset")
        return None
    except TypeError:
        report.add(path, "datetime", "Expected ISO-8601 timestamp with UTC offset")
        return None
