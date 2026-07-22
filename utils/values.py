"""Shared scalar parsing and collection helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Type

from .errors import ValereError


UNRESOLVED_MARKERS = {"", "TBD", "UNRESOLVED", "UNKNOWN", "PENDING", "DRAFT"}


def is_unresolved(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().upper() in UNRESOLVED_MARKERS)


def require_concrete(value: Any, path: str, error_type: Type[ValereError] = ValereError) -> Any:
    if is_unresolved(value):
        raise error_type("%s requires a concrete value" % path)
    return value


def coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def coerce_datetime(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def duplicates(values: Iterable[Any]) -> List[Any]:
    seen = set()
    repeated = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def deep_get(value: Dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = value
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return default
        current = current[segment]
    return current


def unique_index(
    items: Iterable[Dict[str, Any]],
    key: str,
    path: str,
    error_type: Type[ValereError] = ValereError,
) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise error_type("%s[%d] must be a mapping" % (path, index))
        item_id = str(require_concrete(item.get(key), "%s[%d].%s" % (path, index, key), error_type))
        if item_id in indexed:
            raise error_type("duplicate %s %s in %s" % (key, item_id, path))
        indexed[item_id] = item
    return indexed
