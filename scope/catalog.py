"""Compatibility exports for the canonical Valere catalogs.

New code should import these phase-neutral definitions from ``utils.catalogs``.
This module remains so downstream Phase 0 integrations do not break.
"""

from utils.catalogs import (
    DELIVERABLE_KINDS,
    DEPLOYMENT_TIERS,
    MA_WORKSTREAM_CATALOG,
    REQUIRED_GOVERNANCE_CONTROLS,
    RIGHTS_DECISIONS,
    RIGHTS_USES,
    SEVERITIES,
    TRANSACTION_STRUCTURES,
    WORKFLOW_CATALOG,
)

__all__ = [
    "DELIVERABLE_KINDS",
    "DEPLOYMENT_TIERS",
    "MA_WORKSTREAM_CATALOG",
    "REQUIRED_GOVERNANCE_CONTROLS",
    "RIGHTS_DECISIONS",
    "RIGHTS_USES",
    "SEVERITIES",
    "TRANSACTION_STRUCTURES",
    "WORKFLOW_CATALOG",
]
