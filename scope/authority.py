"""A4 — human authority, responsibility, and signoff control."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from utils.artifacts import canonical_json
from utils.catalogs import DEPLOYMENT_TIERS, SEVERITIES
from utils.errors import BoundaryError, BoundaryValidationReport as ValidationReport
from utils.values import duplicates

from .common import (
    parse_datetime,
    require_list,
    require_mapping,
    require_value,
)


def _valid_at(value: Dict[str, Any], at: datetime) -> bool:
    scratch = ValidationReport()
    start = parse_datetime(value.get("valid_from"), "valid_from", scratch)
    end = parse_datetime(value.get("valid_until"), "valid_until", scratch)
    return scratch.ok and bool(start and end and start <= at <= end)


def validate_authority_matrix(matrix: Dict[str, Any], now: Optional[datetime] = None) -> ValidationReport:
    report = ValidationReport()
    now = now or datetime.now(timezone.utc)
    if matrix.get("schema_version") != 1:
        report.add("schema_version", "version", "Expected AuthoritySignoffMatrix schema version 1")
    for field in ("matrix_id", "matrix_version", "authority_owner"):
        require_value(report, matrix, field, "")
    if not isinstance(matrix.get("matrix_version"), int) or isinstance(matrix.get("matrix_version"), bool) or matrix.get("matrix_version", 0) < 1:
        report.add("matrix_version", "version", "Version must be a positive integer")
    if matrix.get("approval_status") != "APPROVED":
        report.add("approval_status", "not-approved", "Authority matrix requires owner approval")

    actors_list = require_list(report, matrix.get("actors"), "actors")
    actors: Dict[str, Dict[str, Any]] = {}
    actor_ids = []
    for index, value in enumerate(actors_list):
        path = "actors[%d]" % index
        actor = require_mapping(report, value, path)
        for field in ("actor_id", "display_name", "organization"):
            require_value(report, actor, field, path)
        actor_id = actor.get("actor_id")
        actor_ids.append(actor_id)
        if isinstance(actor_id, str):
            actors[actor_id] = actor
        roles = require_list(report, actor.get("roles"), path + ".roles")
        if not roles:
            report.add(path + ".roles", "empty", "Actor needs at least one role")
        credentials = require_list(report, actor.get("credentials"), path + ".credentials")
        if not credentials:
            report.add(path + ".credentials", "empty", "Actor needs an affirmative credential record")
        for credential_index, credential_value in enumerate(credentials):
            credential_path = "%s.credentials[%d]" % (path, credential_index)
            credential = require_mapping(report, credential_value, credential_path)
            for field in ("credential_id", "type", "status", "verified_by", "valid_until"):
                require_value(report, credential, field, credential_path)
            expiry = parse_datetime(credential.get("valid_until"), credential_path + ".valid_until", report)
            if credential.get("status") == "ACTIVE" and expiry and expiry <= now:
                report.add(credential_path + ".valid_until", "expired", "Expired credential cannot remain ACTIVE")
        delegations = require_list(report, actor.get("delegations"), path + ".delegations")
        for delegation_index, delegation_value in enumerate(delegations):
            delegation_path = "%s.delegations[%d]" % (path, delegation_index)
            delegation = require_mapping(report, delegation_value, delegation_path)
            for field in ("delegation_id", "delegated_by", "valid_from", "valid_until"):
                require_value(report, delegation, field, delegation_path)
            for field in ("action_types", "severities", "deployment_tiers", "matter_ids"):
                values = require_list(report, delegation.get(field), delegation_path + "." + field)
                if not values:
                    report.add(delegation_path + "." + field, "empty", "Delegation scope cannot be empty")
            start = parse_datetime(delegation.get("valid_from"), delegation_path + ".valid_from", report)
            end = parse_datetime(delegation.get("valid_until"), delegation_path + ".valid_until", report)
            if start and end and end <= start:
                report.add(delegation_path, "time-range", "Delegation must end after it begins")
            unknown_severity = set(delegation.get("severities", [])) - SEVERITIES
            unknown_tier = set(delegation.get("deployment_tiers", [])) - DEPLOYMENT_TIERS
            if unknown_severity:
                report.add(delegation_path + ".severities", "enum", "Unknown severities: %s" % ", ".join(sorted(unknown_severity)))
            if unknown_tier:
                report.add(delegation_path + ".deployment_tiers", "enum", "Unknown tiers: %s" % ", ".join(sorted(unknown_tier)))
        conflicts = require_mapping(report, actor.get("conflicts"), path + ".conflicts")
        require_list(report, conflicts.get("matter_ids"), path + ".conflicts.matter_ids")
        walls = require_mapping(report, actor.get("ethical_walls"), path + ".ethical_walls")
        require_list(report, walls.get("denied_matter_ids"), path + ".ethical_walls.denied_matter_ids")
    if duplicates(actor_ids):
        report.add("actors", "duplicate", "Actor IDs must be unique")

    responsibility = require_mapping(report, matrix.get("responsibility"), "responsibility")
    for field in ("lawyer_of_record_by_matter", "customer_owner_by_matter"):
        mapping = require_mapping(report, responsibility.get(field), "responsibility." + field)
        if not mapping:
            report.add("responsibility." + field, "empty", "At least one explicit matter owner is required")
        for matter_id, actor_id in mapping.items():
            if actor_id not in actors:
                report.add("responsibility.%s.%s" % (field, matter_id), "unknown-actor", "Owner must reference a registered actor")
    for field in ("rights_owner", "governance_owner", "release_owner"):
        actor_id = require_value(report, responsibility, field, "responsibility")
        if actor_id not in actors:
            report.add("responsibility." + field, "unknown-actor", "Owner must reference a registered actor")

    policies_list = require_list(report, matrix.get("approval_policies"), "approval_policies")
    policies: Dict[str, Dict[str, Any]] = {}
    action_types = []
    for index, value in enumerate(policies_list):
        path = "approval_policies[%d]" % index
        policy = require_mapping(report, value, path)
        action_type = require_value(report, policy, "action_type", path)
        action_types.append(action_type)
        if isinstance(action_type, str):
            policies[action_type] = policy
        for field in ("severities", "deployment_tiers", "required_roles"):
            values = require_list(report, policy.get(field), path + "." + field)
            if not values:
                report.add(path + "." + field, "empty", "Approval policy scope cannot be empty")
        minimum = policy.get("min_approvers")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            report.add(path + ".min_approvers", "range", "At least one approver is required")
        if policy.get("self_approval_allowed") is not False:
            report.add(path + ".self_approval_allowed", "self-approval", "Self approval must be prohibited")
        if policy.get("distinct_actors_required") is not True:
            report.add(path + ".distinct_actors_required", "separation-of-duties", "Distinct approvers must be required")
        if not {"HIGH", "CRITICAL"} <= set(policy.get("severities", [])):
            report.add(path + ".severities", "high-severity-gap", "Every action policy must cover HIGH and CRITICAL")
    if duplicates(action_types):
        report.add("approval_policies", "duplicate", "Action types must be unique")
    if not policies:
        report.add("approval_policies", "empty", "At least one high-severity action policy is required")

    # Prove that every high-severity policy has a currently authorized human.
    for action_type, policy in policies.items():
        capable = []
        capable_roles: Set[str] = set()
        for actor in actors.values():
            active_credential = any(
                credential.get("status") == "ACTIVE"
                and _credential_valid(credential, now)
                for credential in actor.get("credentials", [])
            )
            active_delegation = any(
                action_type in delegation.get("action_types", [])
                and "HIGH" in delegation.get("severities", [])
                and _valid_at(delegation, now)
                for delegation in actor.get("delegations", [])
            )
            role_match = bool(set(actor.get("roles", [])) & set(policy.get("required_roles", [])))
            if active_credential and active_delegation and role_match:
                capable.append(actor["actor_id"])
                capable_roles.update(set(actor.get("roles", [])) & set(policy.get("required_roles", [])))
        if len(capable) < policy.get("min_approvers", 1):
            report.add(
                "approval_policies.%s" % action_type,
                "unowned-high-severity",
                "Not enough currently credentialed/delegated human owners",
            )
        missing_roles = set(policy.get("required_roles", [])) - capable_roles
        if missing_roles:
            report.add(
                "approval_policies.%s.required_roles" % action_type,
                "unowned-required-role",
                "No currently credentialed/delegated owner for roles: %s" % ", ".join(sorted(missing_roles)),
            )

    workflow = require_mapping(report, matrix.get("release_signoff_workflow"), "release_signoff_workflow")
    stages = require_list(report, workflow.get("stages"), "release_signoff_workflow.stages")
    if not stages:
        report.add("release_signoff_workflow.stages", "empty", "Release signoff needs explicit stages")
    require_value(report, workflow, "e_signature_provider", "release_signoff_workflow")

    logs = require_mapping(report, matrix.get("audit_logs"), "audit_logs")
    for name in ("client_decisions", "exceptions_overrides"):
        config = require_mapping(report, logs.get(name), "audit_logs." + name)
        if config.get("format") != "HASH_CHAINED_JSONL" or config.get("append_only") is not True:
            report.add("audit_logs." + name, "immutability", "Audit log must be append-only hash-chained JSONL")
        require_value(report, config, "path", "audit_logs." + name)

    approval = require_mapping(report, matrix.get("approval"), "approval")
    for field in ("actor_id", "role", "approved_at"):
        require_value(report, approval, field, "approval")
    parse_datetime(approval.get("approved_at"), "approval.approved_at", report)
    approval_actor = actors.get(approval.get("actor_id"))
    if not approval_actor or approval.get("role") not in approval_actor.get("roles", []):
        report.add("approval", "unauthorized-approver", "Matrix approver must be registered with the stated role")
    if matrix.get("authority_owner") not in actors:
        report.add("authority_owner", "unknown-actor", "Authority owner must reference a registered actor")
    if matrix.get("test_fixture") is True and matrix.get("approval_status") == "APPROVED":
        report.add("test_fixture", "fixture-boundary", "A test fixture cannot approve a production authority matrix")
    return report


def _credential_valid(credential: Dict[str, Any], at: datetime) -> bool:
    if credential.get("status") != "ACTIVE":
        return False
    scratch = ValidationReport()
    expiry = parse_datetime(credential.get("valid_until"), "valid_until", scratch)
    return scratch.ok and bool(expiry and expiry > at)


@dataclass(frozen=True)
class SignoffDecision:
    approved: bool
    reasons: List[str]
    accepted_actor_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reasons": self.reasons,
            "accepted_actor_ids": self.accepted_actor_ids,
        }


class AuthorityEngine:
    def __init__(self, matrix: Dict[str, Any], now: Optional[datetime] = None):
        self.now = now or datetime.now(timezone.utc)
        self.matrix = matrix
        report = validate_authority_matrix(matrix, now=self.now)
        report.require_ok()
        self.actors = {item["actor_id"]: item for item in matrix["actors"]}
        self.policies = {item["action_type"]: item for item in matrix["approval_policies"]}

    def actor_authorized(
        self,
        actor_id: str,
        action_type: str,
        severity: str,
        tier: str,
        matter_id: str,
        at: Optional[datetime] = None,
    ) -> List[str]:
        at = at or self.now
        reasons: List[str] = []
        actor = self.actors.get(actor_id)
        policy = self.policies.get(action_type)
        if not actor:
            return ["unknown-actor"]
        if not policy:
            return ["unknown-action-policy"]
        if severity not in policy["severities"]:
            reasons.append("severity-not-covered")
        if tier not in policy["deployment_tiers"]:
            reasons.append("tier-not-covered")
        if not set(actor["roles"]) & set(policy["required_roles"]):
            reasons.append("required-role-missing")
        if not any(_credential_valid(value, at) for value in actor["credentials"]):
            reasons.append("no-active-credential")
        delegation_match = any(
            action_type in value["action_types"]
            and severity in value["severities"]
            and tier in value["deployment_tiers"]
            and ("*" in value["matter_ids"] or matter_id in value["matter_ids"])
            and _valid_at(value, at)
            for value in actor["delegations"]
        )
        if not delegation_match:
            reasons.append("no-active-delegation")
        if matter_id in actor["conflicts"]["matter_ids"]:
            reasons.append("conflict")
        if matter_id in actor["ethical_walls"]["denied_matter_ids"]:
            reasons.append("ethical-wall")
        return reasons

    def evaluate_signoff(self, request: Dict[str, Any], approvals: Sequence[Dict[str, Any]]) -> SignoffDecision:
        action_type = request.get("action_type", "")
        policy = self.policies.get(action_type)
        if not policy:
            return SignoffDecision(False, ["unknown-action-policy"], [])
        reasons: List[str] = []
        accepted: List[str] = []
        seen: Set[str] = set()
        roles: Set[str] = set()
        for approval in approvals:
            actor_id = approval.get("actor_id", "")
            if approval.get("decision") != "APPROVE":
                reasons.append("non-approval:%s" % actor_id)
                continue
            if actor_id == request.get("requester_id") and not policy["self_approval_allowed"]:
                reasons.append("self-approval:%s" % actor_id)
                continue
            if actor_id in seen and policy["distinct_actors_required"]:
                reasons.append("duplicate-approver:%s" % actor_id)
                continue
            at_report = ValidationReport()
            at = parse_datetime(approval.get("approved_at"), "approved_at", at_report)
            if not at_report.ok or at is None:
                reasons.append("invalid-approval-time:%s" % actor_id)
                continue
            actor_reasons = self.actor_authorized(
                actor_id,
                action_type,
                request.get("severity", ""),
                request.get("deployment_tier", ""),
                request.get("matter_id", ""),
                at,
            )
            if actor_reasons:
                reasons.extend("%s:%s" % (actor_id, reason) for reason in actor_reasons)
                continue
            seen.add(actor_id)
            accepted.append(actor_id)
            roles.update(self.actors[actor_id]["roles"])
        if len(accepted) < policy["min_approvers"]:
            reasons.append("insufficient-approvers")
        if not set(policy["required_roles"]) <= roles:
            reasons.append("required-role-coverage")
        if policy.get("lawyer_of_record_required"):
            lawyer = self.matrix["responsibility"]["lawyer_of_record_by_matter"].get(request.get("matter_id"))
            if lawyer not in accepted:
                reasons.append("lawyer-of-record-missing")
        return SignoffDecision(not reasons, reasons, accepted)

    def record_client_decision(
        self,
        path: str,
        actor_id: str,
        payload: Dict[str, Any],
        occurred_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        matter_id = payload.get("matter_id")
        expected = self.matrix["responsibility"]["customer_owner_by_matter"].get(matter_id)
        if expected != actor_id:
            raise BoundaryError("Only the registered customer owner may record this client decision")
        if not payload.get("decision"):
            raise BoundaryError("Client decision payload requires decision")
        return _append_audit_event(path, "CLIENT_DECISION", actor_id, payload, occurred_at)

    def record_override(
        self,
        path: str,
        request: Dict[str, Any],
        approvals: Sequence[Dict[str, Any]],
        payload: Dict[str, Any],
        occurred_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if request.get("action_type") != "override-control":
            raise BoundaryError("Override requests must use the override-control policy")
        decision = self.evaluate_signoff(request, approvals)
        if not decision.approved:
            raise BoundaryError("Override signoff denied: %s" % ", ".join(decision.reasons))
        enriched = dict(payload)
        enriched["approver_ids"] = decision.accepted_actor_ids
        enriched["matter_id"] = request.get("matter_id")
        return _append_audit_event(
            path,
            "EXCEPTION_OVERRIDE",
            request.get("requester_id", ""),
            enriched,
            occurred_at,
        )


def _event_hash(event_without_hash: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(event_without_hash).encode("utf-8")).hexdigest()


def verify_audit_events(events: Sequence[Dict[str, Any]]) -> None:
    previous = "GENESIS"
    for expected_sequence, event in enumerate(events, start=1):
        if event.get("sequence") != expected_sequence:
            raise BoundaryError("Audit sequence gap at event %d" % expected_sequence)
        if event.get("previous_hash") != previous:
            raise BoundaryError("Audit chain mismatch at event %d" % expected_sequence)
        supplied = event.get("event_hash")
        unsigned = {key: value for key, value in event.items() if key != "event_hash"}
        calculated = _event_hash(unsigned)
        if supplied != calculated:
            raise BoundaryError("Audit event hash mismatch at event %d" % expected_sequence)
        previous = supplied


def read_audit_log(path: str) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    events = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BoundaryError("Invalid audit JSON on line %d" % line_number) from exc
            if not isinstance(event, dict):
                raise BoundaryError("Audit line %d is not an object" % line_number)
            events.append(event)
    verify_audit_events(events)
    return events


def _append_audit_event(
    path: str,
    event_type: str,
    actor_id: str,
    payload: Dict[str, Any],
    occurred_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append one fsync'd, hash-chained decision or override event."""

    try:
        import fcntl
    except ImportError as exc:
        raise BoundaryError(
            "Append-only audit logging requires POSIX file locking (fcntl), "
            "unavailable on this platform"
        ) from exc

    if event_type not in {"CLIENT_DECISION", "EXCEPTION_OVERRIDE"}:
        raise BoundaryError("Unsupported audit event type")
    if not actor_id or not isinstance(payload, dict) or not payload:
        raise BoundaryError("Audit events require an actor and non-empty payload")
    if event_type == "EXCEPTION_OVERRIDE":
        for field in ("reason", "control", "approver_ids", "expires_at"):
            if not payload.get(field):
                raise BoundaryError("Override payload requires %s" % field)
        if actor_id in payload.get("approver_ids", []):
            raise BoundaryError("An override requester cannot self-approve")
    occurred_at = occurred_at or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        raise BoundaryError("Audit timestamp must be timezone-aware")

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(destination), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            events = []
            handle.seek(0)
            for line in handle:
                if line.strip():
                    events.append(json.loads(line))
            verify_audit_events(events)
            unsigned = {
                "sequence": len(events) + 1,
                "event_type": event_type,
                "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
                "actor_id": actor_id,
                "payload": payload,
                "previous_hash": events[-1]["event_hash"] if events else "GENESIS",
            }
            event = dict(unsigned)
            event["event_hash"] = _event_hash(unsigned)
            handle.seek(0, os.SEEK_END)
            handle.write(canonical_json(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return event
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise BoundaryError("Unable to append audit event: %s" % exc) from exc


def high_severity_ownership_report(matrix: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    report = validate_authority_matrix(matrix, now=now)
    ownership_issues = [
        issue.to_dict()
        for issue in report.issues
        if issue.code in {"unowned-high-severity", "unowned-required-role", "expired", "not-approved"}
    ]
    return {
        "complete": report.ok and not ownership_issues,
        "issues": ownership_issues,
        "validation": report.to_dict(),
    }
