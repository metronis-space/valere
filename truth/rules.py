"""B4: source-backed contract logic, playbooks, coverage, and AR-001."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from utils.artifacts import fingerprint, set_fingerprint
from utils.errors import TruthError
from utils.values import deep_get

from .authority import AuthorityGraph
from .common import iso_date, optional_date, referenced_facts, require, unique_ids
from .ontology import OntologyRegistry


RULE_KINDS = {"LEGAL_RULE", "CONTRACT_LOGIC", "BUYER_POLICY"}
ACTION_KINDS = {"REQUIRED", "FALLBACK"}
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "exists"}
OUTCOME_STATUSES = {"MATCHED", "NO_RULE", "LOW_CONFIDENCE", "CONFLICT", "ABSTAIN"}


def validate_expression(expression: Any, path: str = "expression") -> None:
    if not isinstance(expression, dict) or not expression:
        raise TruthError("%s must be a non-empty mapping" % path)
    structural = [key for key in ("all", "any", "not", "fact") if key in expression]
    if len(structural) != 1:
        raise TruthError("%s must contain exactly one of all/any/not/fact" % path)
    if "all" in expression or "any" in expression:
        key = "all" if "all" in expression else "any"
        children = expression[key]
        if not isinstance(children, list) or not children:
            raise TruthError("%s.%s must be a non-empty list" % (path, key))
        for index, child in enumerate(children):
            validate_expression(child, "%s.%s[%d]" % (path, key, index))
    elif "not" in expression:
        validate_expression(expression["not"], "%s.not" % path)
    else:
        require(expression.get("fact"), "%s.fact" % path)
        operator = expression.get("op")
        if operator not in OPERATORS:
            raise TruthError("%s has unsupported operator %s" % (path, operator))
        if operator != "exists" and "value" not in expression:
            raise TruthError("%s.%s requires a value" % (path, operator))


def evaluate_expression(expression: Mapping[str, Any], facts: Mapping[str, Any]) -> bool:
    validate_expression(expression)
    if "all" in expression:
        return all(evaluate_expression(item, facts) for item in expression["all"])
    if "any" in expression:
        return any(evaluate_expression(item, facts) for item in expression["any"])
    if "not" in expression:
        return not evaluate_expression(expression["not"], facts)
    missing = object()
    actual = deep_get(dict(facts), str(expression["fact"]), missing)
    operator = expression["op"]
    expected = expression.get("value")
    if operator == "exists":
        return (actual is not missing) is bool(expression.get("value", True))
    if actual is missing:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "in":
        return actual in expected
    if operator == "contains":
        return expected in actual
    raise TruthError("unsupported expression operator")


def _conjunction_leaves(expression: Mapping[str, Any]) -> Optional[List[Mapping[str, Any]]]:
    if "fact" in expression:
        return [expression]
    if "all" in expression:
        leaves: List[Mapping[str, Any]] = []
        for child in expression["all"]:
            nested = _conjunction_leaves(child)
            if nested is None:
                return None
            leaves.extend(nested)
        return leaves
    return None


def expression_satisfiable(expression: Mapping[str, Any]) -> bool:
    """Catch deterministic contradictions in conjunctive rule predicates."""

    validate_expression(expression)
    leaves = _conjunction_leaves(expression)
    if leaves is None:
        return True
    by_fact: Dict[str, List[Mapping[str, Any]]] = {}
    for leaf in leaves:
        by_fact.setdefault(str(leaf["fact"]), []).append(leaf)
    for constraints in by_fact.values():
        equals = {fingerprint(item.get("value")) for item in constraints if item["op"] == "eq"}
        if len(equals) > 1:
            return False
        equal_values = [item.get("value") for item in constraints if item["op"] == "eq"]
        if equal_values and any(item["op"] == "ne" and item.get("value") == equal_values[0] for item in constraints):
            return False
        numeric_lower: Optional[Tuple[float, bool]] = None
        numeric_upper: Optional[Tuple[float, bool]] = None
        for item in constraints:
            if item["op"] in {"gt", "gte"} and isinstance(item.get("value"), (int, float)):
                candidate = (float(item["value"]), item["op"] == "gt")
                if numeric_lower is None or candidate[0] > numeric_lower[0] or (candidate[0] == numeric_lower[0] and candidate[1]):
                    numeric_lower = candidate
            if item["op"] in {"lt", "lte"} and isinstance(item.get("value"), (int, float)):
                candidate = (float(item["value"]), item["op"] == "lt")
                if numeric_upper is None or candidate[0] < numeric_upper[0] or (candidate[0] == numeric_upper[0] and candidate[1]):
                    numeric_upper = candidate
        if numeric_lower is not None and numeric_upper is not None:
            if numeric_lower[0] > numeric_upper[0] or (numeric_lower[0] == numeric_upper[0] and (numeric_lower[1] or numeric_upper[1])):
                return False
        if equal_values and isinstance(equal_values[0], (int, float)):
            equal = float(equal_values[0])
            if numeric_lower and (equal < numeric_lower[0] or (equal == numeric_lower[0] and numeric_lower[1])):
                return False
            if numeric_upper and (equal > numeric_upper[0] or (equal == numeric_upper[0] and numeric_upper[1])):
                return False
    return True


def _expressions_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    combined = {"all": [left, right]}
    return expression_satisfiable(combined)


@dataclass(frozen=True)
class RuleOutcome:
    issue_family: str
    status: str
    matched_rule_ids: List[str]
    actions: List[Dict[str, Any]]
    confidence: float
    reasons: List[str]
    evidence: List[Dict[str, Any]]
    dependent_facts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_family": self.issue_family,
            "status": self.status,
            "matched_rule_ids": list(self.matched_rule_ids),
            "actions": copy.deepcopy(self.actions),
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "evidence": copy.deepcopy(self.evidence),
            "dependent_facts": list(self.dependent_facts),
        }


class RulePack:
    def __init__(self, artifact: Mapping[str, Any]):
        self.artifact = copy.deepcopy(dict(artifact))
        self.rules = unique_ids(self.artifact.get("rules", []), "rule_id", "rules")
        self.issue_families = set(self.artifact.get("coverage_declaration", {}).get("issue_families", []))
        self.minimum_confidence = float(self.artifact.get("minimum_confidence", 0.8))

    def evaluate(self, issue_family: str, facts: Mapping[str, Any], as_of: date) -> RuleOutcome:
        if issue_family not in self.issue_families:
            return RuleOutcome(issue_family, "NO_RULE", [], [], 0.0, ["issue family is outside declared coverage"], [], [])
        candidates = []
        for rule in self.rules.values():
            if not rule.get("active") or rule.get("issue_family") != issue_family:
                continue
            effective = iso_date(rule["effective_from"], "%s.effective_from" % rule["rule_id"])
            expires = optional_date(rule.get("effective_until"), "%s.effective_until" % rule["rule_id"])
            if effective > as_of or (expires and expires <= as_of):
                continue
            if not evaluate_expression(rule["applies_when"], facts):
                continue
            if not evaluate_expression(rule["trigger"], facts):
                continue
            if rule.get("exceptions") and evaluate_expression(rule["exceptions"], facts):
                continue
            candidates.append(rule)
        if not candidates:
            return RuleOutcome(issue_family, "NO_RULE", [], [], 0.0, ["no active rule matched the supplied facts"], [], [])
        candidates.sort(key=lambda item: (-int(item.get("priority", 0)), item["rule_id"]))
        highest = int(candidates[0].get("priority", 0))
        selected = [item for item in candidates if int(item.get("priority", 0)) == highest]
        overridden = {rule_id for item in selected for rule_id in item.get("overrides", [])}
        selected = [item for item in selected if item["rule_id"] not in overridden]
        action_signatures = {
            fingerprint([(action.get("kind"), action.get("recommendation")) for action in item.get("actions", [])])
            for item in selected
        }
        if len(selected) > 1 and len(action_signatures) > 1:
            return RuleOutcome(issue_family, "CONFLICT", [item["rule_id"] for item in selected], [], 0.0, ["equal-precedence rules prescribe conflicting actions"], [], [])
        confidence = min(float(item.get("confidence", 0)) for item in selected)
        if confidence < self.minimum_confidence:
            return RuleOutcome(issue_family, "LOW_CONFIDENCE", [item["rule_id"] for item in selected], [], confidence, ["matched rules fall below the confidence floor"], [], sorted(set().union(*(referenced_facts(item["trigger"]) for item in selected))))
        actions: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []
        dependent: Set[str] = set()
        for rule in selected:
            dependent.update(referenced_facts(rule["applies_when"]))
            dependent.update(referenced_facts(rule["trigger"]))
            if rule.get("exceptions"):
                dependent.update(referenced_facts(rule["exceptions"]))
            primaries = []
            fallbacks = []
            for action in rule.get("actions", []):
                prerequisites = action.get("prerequisites")
                if prerequisites:
                    dependent.update(referenced_facts(prerequisites))
                if prerequisites and not evaluate_expression(prerequisites, facts):
                    continue
                target = primaries if action["kind"] == "REQUIRED" else fallbacks
                target.append(copy.deepcopy(action))
            actions.extend(primaries or fallbacks)
            evidence.extend(copy.deepcopy(rule.get("source_refs", [])))
        actions.sort(key=lambda item: (0 if item["kind"] == "REQUIRED" else 1, -int(item.get("priority", 0)), item["action_id"]))
        if not actions:
            return RuleOutcome(issue_family, "ABSTAIN", [item["rule_id"] for item in selected], [], confidence, ["a rule matched but no action prerequisites were satisfied"], evidence, sorted(dependent))
        return RuleOutcome(issue_family, "MATCHED", [item["rule_id"] for item in selected], actions, confidence, [], evidence, sorted(dependent))


class RuleCompiler:
    def __init__(self, graph: AuthorityGraph, ontology: OntologyRegistry, authorized_owners: Iterable[str]):
        self.graph = graph
        self.ontology = ontology
        self.authorized_owners = set(authorized_owners)

    def _validate_source_ref(self, rule: Mapping[str, Any], source_ref: Mapping[str, Any], index: int) -> None:
        source_id = source_ref.get("source_id")
        proposition_id = source_ref.get("proposition_id")
        span_id = source_ref.get("span_id")
        if source_id not in self.graph.documents or proposition_id not in self.graph.propositions:
            raise TruthError("%s source_refs[%d] is not in the authority graph" % (rule["rule_id"], index))
        proposition = self.graph.propositions[proposition_id]
        matching = [item for item in proposition["support"] if item["source_id"] == source_id and item["span_id"] == span_id]
        if not matching:
            raise TruthError("%s source_refs[%d] is not proposition-backed" % (rule["rule_id"], index))
        source_kind = self.graph.documents[source_id]["authority_kind"]
        expected = {
            "LEGAL_RULE": {"STATUTE", "REGULATION", "COURT_RULE", "OPINION", "AGENCY_GUIDANCE"},
            "CONTRACT_LOGIC": {"CONTRACT"},
            "BUYER_POLICY": {"PLAYBOOK"},
        }[rule["kind"]]
        if source_kind not in expected:
            raise TruthError("%s cannot present %s as %s" % (rule["rule_id"], source_kind, rule["kind"]))
        if rule["kind"] == "LEGAL_RULE":
            as_of = iso_date(rule["effective_from"], "%s.effective_from" % rule["rule_id"])
            jurisdiction = str(self.graph.documents[source_id].get("jurisdiction"))
            decision = self.graph.classify(str(proposition_id), jurisdiction, as_of)
            if not decision.supported:
                raise TruthError("%s legal source is cutoff-invalid, unsupported, or lacks citator coverage" % rule["rule_id"])

    def _validate_rule(self, rule: Mapping[str, Any]) -> None:
        rule_id = str(require(rule.get("rule_id"), "rule.rule_id"))
        if rule.get("kind") not in RULE_KINDS:
            raise TruthError("%s has unsupported kind" % rule_id)
        if int(rule.get("version", 0)) < 1:
            raise TruthError("%s version must be positive" % rule_id)
        if rule.get("active") and rule.get("owner") not in self.authorized_owners:
            raise TruthError("%s has no authorized owner" % rule_id)
        issue_type = rule.get("issue_type_id")
        definition = self.ontology.types.get(issue_type)
        if not definition or definition.get("category") != "ISSUE" or definition.get("status") != "ACTIVE":
            raise TruthError("%s requires an active ISSUE ontology type" % rule_id)
        iso_date(rule.get("effective_from"), "%s.effective_from" % rule_id)
        optional_date(rule.get("effective_until"), "%s.effective_until" % rule_id)
        for key in ("applies_when", "trigger"):
            validate_expression(rule.get(key), "%s.%s" % (rule_id, key))
            if not expression_satisfiable(rule[key]):
                raise TruthError("%s.%s is unsatisfiable" % (rule_id, key))
        if rule.get("exceptions"):
            validate_expression(rule["exceptions"], "%s.exceptions" % rule_id)
        source_refs = rule.get("source_refs", [])
        if rule.get("active") and not source_refs:
            raise TruthError("%s active rule needs source evidence" % rule_id)
        for index, source_ref in enumerate(source_refs):
            self._validate_source_ref(rule, source_ref, index)
        actions = rule.get("actions", [])
        if not actions:
            raise TruthError("%s requires at least one action" % rule_id)
        action_ids = set()
        for index, action in enumerate(actions):
            action_id = str(require(action.get("action_id"), "%s.actions[%d].action_id" % (rule_id, index)))
            if action_id in action_ids:
                raise TruthError("%s has duplicate action %s" % (rule_id, action_id))
            action_ids.add(action_id)
            if action.get("kind") not in ACTION_KINDS:
                raise TruthError("%s action %s has unsupported kind" % (rule_id, action_id))
            require(action.get("recommendation"), "%s.actions[%d].recommendation" % (rule_id, index))
            require(action.get("authority_action"), "%s.actions[%d].authority_action" % (rule_id, index))
            if action.get("prerequisites"):
                validate_expression(action["prerequisites"], "%s.actions[%d].prerequisites" % (rule_id, index))
        confidence = float(rule.get("confidence", -1))
        if not 0 <= confidence <= 1:
            raise TruthError("%s confidence must be in [0,1]" % rule_id)

    def compile(self, document: Mapping[str, Any]) -> RulePack:
        body = copy.deepcopy(dict(document))
        rules = unique_ids(body.get("rules", []), "rule_id", "rules")
        if not rules:
            raise TruthError("rule pack cannot be empty")
        for rule in rules.values():
            self._validate_rule(rule)
        for rule in rules.values():
            unknown = sorted(set(rule.get("overrides", [])) - set(rules))
            if unknown:
                raise TruthError("%s overrides unknown rules: %s" % (rule["rule_id"], ", ".join(unknown)))
        active = [item for item in rules.values() if item.get("active")]
        conflicts = []
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                if left["issue_family"] != right["issue_family"] or int(left.get("priority", 0)) != int(right.get("priority", 0)):
                    continue
                if right["rule_id"] in left.get("overrides", []) or left["rule_id"] in right.get("overrides", []):
                    continue
                if not _expressions_overlap(left["applies_when"], right["applies_when"]) or not _expressions_overlap(left["trigger"], right["trigger"]):
                    continue
                left_actions = [(item["kind"], item["recommendation"]) for item in left["actions"]]
                right_actions = [(item["kind"], item["recommendation"]) for item in right["actions"]]
                if left_actions != right_actions:
                    conflicts.append([left["rule_id"], right["rule_id"]])
        if conflicts:
            raise TruthError("unresolved equal-precedence rule conflicts: %s" % conflicts)
        declaration = body.get("coverage_declaration", {})
        families = set(declaration.get("issue_families", []))
        if not families:
            raise TruthError("coverage declaration requires issue families")
        undeclared = sorted({item["issue_family"] for item in active} - families)
        if undeclared:
            raise TruthError("active rules use undeclared issue families: %s" % ", ".join(undeclared))
        gaps = declaration.get("no_rule", [])
        for gap in gaps:
            if not gap.get("issue_family") or not gap.get("reason") or not gap.get("owner"):
                raise TruthError("no-rule declarations require issue_family, reason, and owner")
        body["rules"] = sorted(rules.values(), key=lambda item: item["rule_id"])
        body["artifact_type"] = "RulePack"
        body["schema_version"] = 1
        body["source_snapshot_id"] = self.graph.snapshot["snapshot_id"]
        body["authority_graph_fingerprint"] = self.graph.artifact()["graph_fingerprint"]
        body["ontology_fingerprint"] = self.ontology.artifact()["registry_fingerprint"]
        body["gates"] = {
            "every_active_rule_has_source": all(item.get("source_refs") for item in active),
            "every_active_rule_has_owner": all(item.get("owner") in self.authorized_owners for item in active),
            "logic_satisfiable": True,
            "conflicts_resolved": True,
            "coverage_declared": True,
            "no_rule_path_explicit": bool(gaps),
        }
        set_fingerprint(body, "rule_pack_fingerprint")
        return RulePack(body)


def rule_version_diff(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    if int(current.get("version", 0)) <= int(previous.get("version", 0)):
        raise TruthError("rule pack changes require a version increment")
    old = unique_ids(previous.get("rules", []), "rule_id", "previous.rules")
    new = unique_ids(current.get("rules", []), "rule_id", "current.rules")
    result = {
        "from_version": previous.get("version"),
        "to_version": current.get("version"),
        "added_rule_ids": sorted(set(new) - set(old)),
        "removed_rule_ids": sorted(set(old) - set(new)),
        "changed_rule_ids": sorted(rule_id for rule_id in set(old) & set(new) if fingerprint(old[rule_id]) != fingerprint(new[rule_id])),
    }
    set_fingerprint(result, "diff_fingerprint")
    return result


def held_out_coverage(pack: RulePack, cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not cases:
        raise TruthError("held-out coverage requires cases")
    rows = []
    for case in cases:
        outcome = pack.evaluate(str(case["issue_family"]), case.get("facts", {}), iso_date(case["as_of"], "case.as_of"))
        expected = set(case.get("expected_rule_ids", []))
        matched = set(outcome.matched_rule_ids)
        accepted = outcome.status == case.get("expected_status", "MATCHED") and (not expected or expected == matched)
        rows.append({"case_id": case["case_id"], "issue_family": case["issue_family"], "accepted": accepted, "status": outcome.status})
    by_family = {}
    for family in sorted({row["issue_family"] for row in rows}):
        subset = [row for row in rows if row["issue_family"] == family]
        by_family[family] = sum(row["accepted"] for row in subset) / float(len(subset))
    curve = []
    for size in sorted({1, len(rows) // 2 or 1, len(rows)}):
        subset = rows[:size]
        curve.append({"held_out_cases": size, "coverage": sum(row["accepted"] for row in subset) / float(size)})
    return {
        "sample_size": len(rows),
        "coverage": sum(row["accepted"] for row in rows) / float(len(rows)),
        "by_issue_family": by_family,
        "curve": curve,
        "rows": rows,
    }


def counterfactual_check(
    pack: RulePack,
    issue_family: str,
    baseline: Mapping[str, Any],
    counterfactual: Mapping[str, Any],
    changed_fact_paths: Iterable[str],
    as_of: date,
) -> Dict[str, Any]:
    before = pack.evaluate(issue_family, baseline, as_of)
    after = pack.evaluate(issue_family, counterfactual, as_of)
    changed = set(changed_fact_paths)
    allowed = set(before.dependent_facts) | set(after.dependent_facts)
    undeclared = sorted(changed - allowed)
    result = {
        "issue_family": issue_family,
        "changed_fact_paths": sorted(changed),
        "dependent_fact_paths": sorted(allowed),
        "undeclared_changes": undeclared,
        "before": before.to_dict(),
        "after": after.to_dict(),
        "output_changed": before.to_dict() != after.to_dict(),
        "passed": not undeclared and before.to_dict() != after.to_dict(),
    }
    set_fingerprint(result, "counterfactual_fingerprint")
    return result


def ar_001_effort_experiment(issue_family: str, observations: Sequence[Mapping[str, Any]], maximum_exponent: float = 0.9) -> Dict[str, Any]:
    """Fit minutes = a * matters^b; b < 1 is sub-linear effort scaling."""

    if len(observations) < 3:
        raise TruthError("AR-001 requires at least three matter-count observations")
    points = sorted((int(item["accepted_matters"]), float(item["senior_lawyer_minutes"])) for item in observations)
    if any(matters <= 0 or minutes <= 0 for matters, minutes in points):
        raise TruthError("AR-001 observations must be positive")
    if len({matters for matters, _ in points}) != len(points):
        raise TruthError("AR-001 matter counts must be unique")
    xs = [math.log(item[0]) for item in points]
    ys = [math.log(item[1]) for item in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        raise TruthError("AR-001 requires varying matter counts")
    exponent = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    intercept = y_mean - exponent * x_mean
    predicted = [intercept + exponent * x for x in xs]
    total = sum((y - y_mean) ** 2 for y in ys)
    residual = sum((y - estimate) ** 2 for y, estimate in zip(ys, predicted))
    r_squared = 1.0 if total == 0 else 1 - residual / total
    passed = exponent < maximum_exponent
    result = {
        "experiment_id": "AR-001",
        "issue_family": issue_family,
        "observations": [{"accepted_matters": item[0], "senior_lawyer_minutes": item[1]} for item in points],
        "scaling_exponent": exponent,
        "maximum_exponent": maximum_exponent,
        "r_squared": r_squared,
        "passed": passed,
        "decision": "CONTINUE" if passed else "STOP_OR_NARROW",
    }
    set_fingerprint(result, "experiment_fingerprint")
    return result
