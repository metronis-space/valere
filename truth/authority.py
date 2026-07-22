"""B2: cutoff-aware authority, treatment, and proposition-support graph."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from utils.artifacts import fingerprint, set_fingerprint
from utils.errors import TruthError

from .common import iso_date, optional_date, require, unique_ids


TREATMENTS = {"CITES", "FOLLOWS", "DISTINGUISHES", "QUESTIONS", "OVERRULES", "WITHDRAWS", "SUPERSEDES"}
SUPPORT_TYPES = {"HOLDING", "DICTA", "TEXT", "CONTRACT_TEXT", "BUYER_POLICY"}
POLARITIES = {"SUPPORTS", "CONTRADICTS"}
NEGATIVE_TREATMENTS = {"OVERRULES", "WITHDRAWS", "SUPERSEDES"}


class CitatorConnector(Protocol):
    def treatment_for(self, source_id: str, as_of: date) -> Dict[str, Any]:
        ...


class InMemoryCitator:
    def __init__(self, statuses: Optional[Mapping[str, Mapping[str, Any]]] = None, covered: bool = True):
        self.statuses = {key: dict(value) for key, value in (statuses or {}).items()}
        self.covered = covered

    def treatment_for(self, source_id: str, as_of: date) -> Dict[str, Any]:
        if not self.covered:
            return {"covered": False, "status": "UNKNOWN", "as_of": as_of.isoformat()}
        result = copy.deepcopy(self.statuses.get(source_id, {"status": "GOOD"}))
        result.update({"covered": True, "as_of": as_of.isoformat()})
        return result


def _span_index(snapshot: Mapping[str, Any]) -> Dict[Tuple[str, str], Mapping[str, Any]]:
    result: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    for document in snapshot.get("documents", []):
        for span in document.get("spans", []):
            result[(document["source_id"], span["span_id"])] = span
    return result


@dataclass(frozen=True)
class SupportDecision:
    proposition_id: str
    status: str
    controlling: List[Dict[str, Any]]
    persuasive: List[Dict[str, Any]]
    adverse: List[Dict[str, Any]]
    reasons: List[str]
    coverage_flags: List[str]

    @property
    def supported(self) -> bool:
        return self.status == "SUPPORTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposition_id": self.proposition_id,
            "status": self.status,
            "supported": self.supported,
            "controlling": copy.deepcopy(self.controlling),
            "persuasive": copy.deepcopy(self.persuasive),
            "adverse": copy.deepcopy(self.adverse),
            "reasons": list(self.reasons),
            "coverage_flags": list(self.coverage_flags),
        }


class AuthorityGraph:
    """Normalized graph that never treats citation existence as support."""

    def __init__(
        self,
        snapshot: Mapping[str, Any],
        hierarchy: Mapping[str, Mapping[str, Any]],
        treatments: Iterable[Mapping[str, Any]],
        propositions: Iterable[Mapping[str, Any]],
        citator: Optional[CitatorConnector] = None,
    ):
        if not snapshot.get("ready"):
            raise TruthError("authority graph requires a ready authority snapshot")
        self.snapshot = copy.deepcopy(dict(snapshot))
        self.documents = unique_ids(self.snapshot.get("documents", []), "source_id", "snapshot.documents")
        self.spans = _span_index(self.snapshot)
        self.hierarchy = {key: copy.deepcopy(dict(value)) for key, value in hierarchy.items()}
        self.treatments = unique_ids([copy.deepcopy(dict(item)) for item in treatments], "treatment_id", "treatments")
        self.propositions = unique_ids([copy.deepcopy(dict(item)) for item in propositions], "proposition_id", "propositions")
        self.citator = citator or InMemoryCitator(covered=False)
        self._validate()

    def _validate(self) -> None:
        for source_id, document in self.documents.items():
            body = document.get("issuing_body")
            if document.get("authority_kind") in {"OPINION", "STATUTE", "REGULATION", "COURT_RULE", "AGENCY_GUIDANCE"} and body not in self.hierarchy:
                raise TruthError("source %s has no hierarchy entry for %s" % (source_id, body))
        for treatment_id, treatment in self.treatments.items():
            if treatment.get("type") not in TREATMENTS:
                raise TruthError("%s has unsupported treatment" % treatment_id)
            if treatment.get("from_source_id") not in self.documents or treatment.get("to_source_id") not in self.documents:
                raise TruthError("%s references an unknown source" % treatment_id)
            iso_date(treatment.get("effective_date"), "%s.effective_date" % treatment_id)
        for proposition_id, proposition in self.propositions.items():
            require(proposition.get("text"), "%s.text" % proposition_id)
            links = proposition.get("support", [])
            if not isinstance(links, list) or not links:
                raise TruthError("%s requires at least one proposition-to-span link" % proposition_id)
            for index, link in enumerate(links):
                source_id = link.get("source_id")
                span_id = link.get("span_id")
                if source_id not in self.documents or (source_id, span_id) not in self.spans:
                    raise TruthError("%s support[%d] references an unknown source span" % (proposition_id, index))
                if link.get("support_type") not in SUPPORT_TYPES or link.get("polarity") not in POLARITIES:
                    raise TruthError("%s support[%d] has unsupported annotations" % (proposition_id, index))
                confidence = float(link.get("confidence", -1))
                if not 0 <= confidence <= 1:
                    raise TruthError("%s support[%d].confidence must be in [0,1]" % (proposition_id, index))
                if not link.get("verified_by"):
                    raise TruthError("%s support[%d] needs a verifier" % (proposition_id, index))

    def _negative_history(self, source_id: str, as_of: date) -> List[Dict[str, Any]]:
        adverse: List[Dict[str, Any]] = []
        for treatment in self.treatments.values():
            if treatment.get("to_source_id") != source_id:
                continue
            if iso_date(treatment["effective_date"], "treatment.effective_date") > as_of:
                continue
            if treatment["type"] in NEGATIVE_TREATMENTS or treatment["type"] in {"QUESTIONS", "DISTINGUISHES"}:
                adverse.append(copy.deepcopy(treatment))
        return sorted(adverse, key=lambda item: (item["effective_date"], item["treatment_id"]))

    def _weight(self, document: Mapping[str, Any], target_jurisdiction: str, support_type: str) -> str:
        kind = document.get("authority_kind")
        same_jurisdiction = document.get("jurisdiction") == target_jurisdiction
        hierarchy = self.hierarchy.get(str(document.get("issuing_body")), {})
        if support_type != "DICTA" and same_jurisdiction and (kind in {"STATUTE", "REGULATION", "COURT_RULE"} or hierarchy.get("binding", False)):
            return "CONTROLLING"
        return "PERSUASIVE"

    def classify(self, proposition_id: str, target_jurisdiction: str, as_of: date, minimum_confidence: float = 0.8) -> SupportDecision:
        if proposition_id not in self.propositions:
            return SupportDecision(proposition_id, "NO_RULE", [], [], [], ["unknown proposition"], ["NO_PROPOSITION"])
        proposition = self.propositions[proposition_id]
        controlling: List[Dict[str, Any]] = []
        persuasive: List[Dict[str, Any]] = []
        adverse: List[Dict[str, Any]] = []
        reasons: List[str] = []
        flags: Set[str] = set()
        low_confidence = False
        for link in proposition["support"]:
            document = self.documents[link["source_id"]]
            effective = iso_date(document["effective_date"], "%s.effective_date" % document["source_id"])
            repealed = optional_date(document.get("repealed_date"), "%s.repealed_date" % document["source_id"])
            if effective > as_of or (repealed and repealed <= as_of):
                flags.add("OUTSIDE_CUTOFF")
                continue
            history = self._negative_history(document["source_id"], as_of)
            adverse.extend(history)
            citator = self.citator.treatment_for(document["source_id"], as_of)
            requires_citator = document.get("authority_kind") == "OPINION"
            if requires_citator and not citator.get("covered"):
                flags.add("CITATOR_UNAVAILABLE")
                continue
            if any(item["type"] in NEGATIVE_TREATMENTS for item in history) or citator.get("status") in {"OVERRULED", "WITHDRAWN", "REVERSED"}:
                flags.add("NEGATIVE_HISTORY")
                continue
            if link["polarity"] == "CONTRADICTS":
                adverse.append(copy.deepcopy(link))
                continue
            if float(link["confidence"]) < minimum_confidence:
                low_confidence = True
                continue
            evidence = copy.deepcopy(link)
            evidence["source_fingerprint"] = document["content_fingerprint"]
            evidence["span_fingerprint"] = self.spans[(link["source_id"], link["span_id"])]["content_fingerprint"]
            evidence["weight"] = self._weight(document, target_jurisdiction, link["support_type"])
            if evidence["weight"] == "CONTROLLING":
                controlling.append(evidence)
            else:
                persuasive.append(evidence)
        if controlling or persuasive:
            status = "SUPPORTED"
        elif low_confidence:
            status = "LOW_CONFIDENCE"
            flags.add("LOW_CONFIDENCE")
            reasons.append("all usable evidence is below the confidence threshold")
        else:
            status = "ABSTAIN"
            reasons.append("no cutoff-valid supporting span is available")
        if adverse:
            flags.add("ADVERSE_AUTHORITY_PRESENT")
        return SupportDecision(
            proposition_id,
            status,
            sorted(controlling, key=lambda item: (item["source_id"], item["span_id"])),
            sorted(persuasive, key=lambda item: (item["source_id"], item["span_id"])),
            adverse,
            reasons,
            sorted(flags),
        )

    def conflicting_authority(self, proposition_id: str, as_of: date) -> List[Dict[str, Any]]:
        proposition = self.propositions.get(proposition_id, {})
        conflicts = []
        for link in proposition.get("support", []):
            if link.get("polarity") == "CONTRADICTS":
                conflicts.append(copy.deepcopy(link))
            conflicts.extend(self._negative_history(str(link.get("source_id")), as_of))
        return conflicts

    def artifact(self) -> Dict[str, Any]:
        value = {
            "artifact_type": "AuthorityPropositionGraph",
            "schema_version": 1,
            "snapshot_id": self.snapshot["snapshot_id"],
            "hierarchy": self.hierarchy,
            "treatments": sorted(self.treatments.values(), key=lambda item: item["treatment_id"]),
            "propositions": sorted(self.propositions.values(), key=lambda item: item["proposition_id"]),
        }
        set_fingerprint(value, "graph_fingerprint")
        return value


def classification_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Measure usable-citation classification and false acceptance."""

    if not rows:
        raise TruthError("classification gold set cannot be empty")
    true_positive = sum(bool(row.get("expected_supported")) and bool(row.get("predicted_supported")) for row in rows)
    false_positive = sum(not bool(row.get("expected_supported")) and bool(row.get("predicted_supported")) for row in rows)
    false_negative = sum(bool(row.get("expected_supported")) and not bool(row.get("predicted_supported")) for row in rows)
    adverse_total = sum(bool(row.get("expected_adverse")) for row in rows)
    adverse_found = sum(bool(row.get("expected_adverse")) and bool(row.get("predicted_adverse")) for row in rows)
    precision = true_positive / float(true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / float(true_positive + false_negative) if true_positive + false_negative else 1.0
    return {
        "sample_size": len(rows),
        "precision": precision,
        "recall": recall,
        "false_accept_rate": false_positive / float(len(rows)),
        "adverse_retrieval_recall": adverse_found / float(adverse_total) if adverse_total else 1.0,
        "counts": {"true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative},
    }
