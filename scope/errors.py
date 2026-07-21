"""Shared validation result types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List


class BoundaryError(RuntimeError):
    """Raised when a fail-closed Phase 0 control rejects an operation."""


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

    def add(
        self,
        path: str,
        code: str,
        message: str,
        severity: str = "ERROR",
    ) -> None:
        self.issues.append(ValidationIssue(path, code, message, severity))

    def extend(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def merge(self, other: "ValidationReport", prefix: str = "") -> None:
        for issue in other.issues:
            path = "%s.%s" % (prefix, issue.path) if prefix and issue.path else prefix or issue.path
            self.add(path, issue.code, issue.message, issue.severity)

    def require_ok(self) -> None:
        if not self.ok:
            detail = "; ".join(
                "%s [%s]: %s" % (item.path, item.code, item.message)
                for item in self.issues
                if item.severity == "ERROR"
            )
            raise BoundaryError(detail)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": sum(item.severity == "ERROR" for item in self.issues),
            "warning_count": sum(item.severity == "WARNING" for item in self.issues),
            "issues": [item.to_dict() for item in self.issues],
        }

