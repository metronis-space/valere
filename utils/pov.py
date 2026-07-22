"""Canonical identity and scope for the bounded Harvey LAB M&A POV.

Keep fixture identity here so Phase 0 and Phase 1 cannot silently drift apart.
"""

HARVEY_REPOSITORY = "https://github.com/harveyai/harvey-labs"
HARVEY_COMMIT = "845a08840869b21a5c11958aae58bf5f00a7b775"
HARVEY_MA_ROOT = "tasks/corporate-ma"
HARVEY_POV_TASK = "tasks/corporate-ma/analyze-change-of-control-provisions-across-targets-material-contracts"
HARVEY_POV_TASK_URL = "%s/tree/%s/%s" % (HARVEY_REPOSITORY, HARVEY_COMMIT, HARVEY_POV_TASK)

POV_WORKFLOW = "counterparty-paper-review"
POV_WORKSTREAM = "contracts-consents"
POV_DATE = "2026-07-22"
POV_TIMESTAMP = "2026-07-22T12:00:00+00:00"
POV_MATTER_ID = "harvey-ma-pov-change-control"
POV_BUYER_ID = "harvey-lab-ma-pov"
POV_LEGAL_ACTOR_ID = "synthetic-legal"
POV_PRODUCT_ACTOR_ID = "synthetic-product"
POV_SPONSOR_ACTOR_ID = "synthetic-sponsor"


__all__ = [
    "HARVEY_COMMIT",
    "HARVEY_MA_ROOT",
    "HARVEY_POV_TASK",
    "HARVEY_POV_TASK_URL",
    "HARVEY_REPOSITORY",
    "POV_BUYER_ID",
    "POV_DATE",
    "POV_LEGAL_ACTOR_ID",
    "POV_MATTER_ID",
    "POV_PRODUCT_ACTOR_ID",
    "POV_SPONSOR_ACTOR_ID",
    "POV_TIMESTAMP",
    "POV_WORKFLOW",
    "POV_WORKSTREAM",
]
