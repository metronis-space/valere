"""Phase 1 adapters over dependency-neutral shared utilities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Set

from utils.errors import TruthError
from utils.values import coerce_date, coerce_datetime, require_concrete, unique_index


def require(value: Any, path: str) -> Any:
    return require_concrete(value, path, TruthError)


def iso_date(value: Any, path: str) -> date:
    require(value, path)
    try:
        return coerce_date(value)
    except (TypeError, ValueError) as exc:
        raise TruthError("%s must be an ISO-8601 date" % path) from exc


def iso_datetime(value: Any, path: str) -> datetime:
    require(value, path)
    try:
        return coerce_datetime(value)
    except (TypeError, ValueError) as exc:
        message = "%s must include a UTC offset" if "UTC offset" in str(exc) else "%s must be an ISO-8601 timestamp"
        raise TruthError(message % path) from exc


def optional_date(value: Any, path: str) -> Optional[date]:
    return None if value in (None, "") else iso_date(value, path)


def unique_ids(items: Iterable[Dict[str, Any]], key: str, path: str) -> Dict[str, Dict[str, Any]]:
    return unique_index(items, key, path, TruthError)


def referenced_facts(expression: Any) -> Set[str]:
    if not isinstance(expression, dict):
        return set()
    facts: Set[str] = set()
    if isinstance(expression.get("fact"), str):
        facts.add(expression["fact"])
    for key in ("all", "any"):
        for child in expression.get(key, []) if isinstance(expression.get(key), list) else []:
            facts.update(referenced_facts(child))
    if "not" in expression:
        facts.update(referenced_facts(expression["not"]))
    return facts


__all__ = [
    "iso_date",
    "iso_datetime",
    "optional_date",
    "referenced_facts",
    "require",
    "unique_ids",
]
