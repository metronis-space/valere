"""Phase 0 boundary controls for Valere.

The package deliberately separates executable validation from the commercial,
legal, and human decisions that the software is not authorized to invent.
"""

from utils.errors import BoundaryError, BoundaryValidationReport as ValidationReport, ValidationIssue

from .compiler import Phase0Compiler

__all__ = [
    "BoundaryError",
    "Phase0Compiler",
    "ValidationIssue",
    "ValidationReport",
]

__version__ = "0.1.0"
