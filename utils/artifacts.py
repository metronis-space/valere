"""Canonical serialization, hashing, document loading, and atomic writes."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from .errors import DocumentError


def load_document(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle) if file_path.suffix.lower() == ".json" else yaml.safe_load(handle)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise DocumentError("Unable to load %s: %s" % (path, exc)) from exc
    if not isinstance(value, dict):
        raise DocumentError("%s must contain a mapping at its root" % path)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def without_fingerprint(value: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    result = copy.deepcopy(value)
    for field in fields:
        result.pop(field, None)
    return result


def set_fingerprint(value: Dict[str, Any], field: str = "artifact_fingerprint") -> Dict[str, Any]:
    value[field] = fingerprint(without_fingerprint(value, (field,)))
    return value


def verify_fingerprint(value: Dict[str, Any], field: str = "artifact_fingerprint") -> bool:
    expected = value.get(field)
    return isinstance(expected, str) and fingerprint(without_fingerprint(value, (field,))) == expected


def _atomic_write(path: str, writer: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".%s." % destination.name, dir=str(destination.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, value: Any) -> None:
    def write(handle: Any) -> None:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    _atomic_write(path, write)


def atomic_write_yaml(path: str, value: Any) -> None:
    def write(handle: Any) -> None:
        yaml.safe_dump(value, handle, sort_keys=False, allow_unicode=True)

    _atomic_write(path, write)
