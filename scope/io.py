"""Backward-compatible Phase 0 facade over shared artifact utilities."""

from typing import Any, Dict

from utils.artifacts import atomic_write_json, atomic_write_yaml, canonical_json, fingerprint
from utils.artifacts import load_document as load_shared_document
from utils.errors import DocumentError

from .errors import BoundaryError


def load_document(path: str) -> Dict[str, Any]:
    """Load a mapping and preserve Phase 0's historical error contract."""

    try:
        return load_shared_document(path)
    except DocumentError as exc:
        raise BoundaryError(str(exc)) from exc


__all__ = [
    "atomic_write_json",
    "atomic_write_yaml",
    "canonical_json",
    "fingerprint",
    "load_document",
]
