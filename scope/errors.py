"""Phase 0 error types backed by shared validation primitives."""

from utils.errors import ValereError, ValidationIssue
from utils.errors import ValidationReport as SharedValidationReport


class BoundaryError(ValereError):
    """Raised when a fail-closed Phase 0 control rejects an operation."""


class ValidationReport(SharedValidationReport):
    """Validation report whose fail-closed exception is ``BoundaryError``."""

    def require_ok(self) -> None:
        super().require_ok(BoundaryError)


__all__ = ["BoundaryError", "ValidationIssue", "ValidationReport"]
