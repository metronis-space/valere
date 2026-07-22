"""Executable Phase 1 truth and policy kernel."""

from utils.errors import TruthError

from .authority import AuthorityGraph, InMemoryCitator, SupportDecision, classification_metrics
from .compiler import Phase1Compiler
from .ontology import OntologyRegistry, registry_impact
from .rules import (
    RuleCompiler,
    RuleOutcome,
    RulePack,
    ar_001_effort_experiment,
    counterfactual_check,
    evaluate_expression,
    held_out_coverage,
    rule_version_diff,
)
from .sources import AuthoritySnapshotBuilder, HttpSourceConnector, InMemorySourceConnector, SnapshotStore

__all__ = [
    "AuthorityGraph",
    "AuthoritySnapshotBuilder",
    "HttpSourceConnector",
    "InMemoryCitator",
    "InMemorySourceConnector",
    "OntologyRegistry",
    "Phase1Compiler",
    "RuleCompiler",
    "RuleOutcome",
    "RulePack",
    "SnapshotStore",
    "SupportDecision",
    "TruthError",
    "ar_001_effort_experiment",
    "classification_metrics",
    "counterfactual_check",
    "evaluate_expression",
    "held_out_coverage",
    "registry_impact",
    "rule_version_diff",
]
