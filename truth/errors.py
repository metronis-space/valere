"""Fail-closed error type for the Phase 1 truth kernel."""

from utils.errors import ValereError


class TruthError(ValereError):
    """Raised when Phase 1 cannot produce a trustworthy result."""


__all__ = ["TruthError"]
