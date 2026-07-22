"""Shared exception and validation-report primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Type


class ValereError(RuntimeError):
    """Base class for expected, fail-closed Valere errors."""


class BoundaryError(ValereError):
    """Raised when a fail-closed Phase 0 control rejects an operation."""


class TruthError(ValereError):
    """Raised when Phase 1 cannot produce a trustworthy result."""


class MatterError(ValereError):
    """Raised when Phase 2 canonical state or compiled criteria are invalid."""


class DocumentError(ValereError):
    """Raised when a configuration or artifact cannot be loaded safely."""


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    code: str
    message: str
    severity: str = "ERROR"

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)

    def add(self, path: str, code: str, message: str, severity: str = "ERROR") -> None:
        self.issues.append(ValidationIssue(path, code, message, severity))

    def extend(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def merge(self, other: "ValidationReport", prefix: str = "") -> None:
        for issue in other.issues:
            path = "%s.%s" % (prefix, issue.path) if prefix and issue.path else prefix or issue.path
            self.add(path, issue.code, issue.message, issue.severity)

    def error_message(self) -> str:
        return "; ".join(
            "%s [%s]: %s" % (item.path, item.code, item.message)
            for item in self.issues
            if item.severity == "ERROR"
        )

    def require_ok(self, error_type: Type[ValereError] = ValereError) -> None:
        if not self.ok:
            raise error_type(self.error_message())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": sum(item.severity == "ERROR" for item in self.issues),
            "warning_count": sum(item.severity == "WARNING" for item in self.issues),
            "issues": [item.to_dict() for item in self.issues],
        }


class BoundaryValidationReport(ValidationReport):
    """Validation report that fails closed with ``BoundaryError`` by default."""

    def require_ok(self, error_type: Type[ValereError] = BoundaryError) -> None:
        super().require_ok(error_type)


__all__ = [
    "BoundaryError",
    "BoundaryValidationReport",
    "DocumentError",
    "MatterError",
    "TruthError",
    "ValereError",
    "ValidationIssue",
    "ValidationReport",
]
