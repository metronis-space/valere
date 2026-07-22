"""B3: typed legal/contract ontology and versioned schema registry."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from utils.artifacts import canonical_json, fingerprint, set_fingerprint
from utils.catalogs import MA_WORKSTREAM_CATALOG

from .common import require, unique_ids
from .errors import TruthError


TYPE_CATEGORIES = {
    "ENTITY",
    "PARTY",
    "CAPACITY",
    "OWNERSHIP",
    "CAPITALIZATION",
    "TRANSACTION",
    "AGREEMENT",
    "DOCUMENT",
    "CLAUSE",
    "DEFINED_TERM",
    "CROSS_REFERENCE",
    "AMENDMENT",
    "FACT",
    "EVENT",
    "OBLIGATION",
    "RIGHT",
    "ISSUE",
    "CONSEQUENCE",
    "REMEDY",
    "DELIVERABLE",
    "FINDING",
    "TRUTH_SOURCE",
    "VERIFICATION_MODE",
}
TYPE_STATUSES = {"ACTIVE", "DEPRECATED", "QUARANTINED"}
JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
MIGRATION_OPS = {"rename_field", "set_default", "map_enum", "drop_field"}


def _validate_value(value: Any, schema: Mapping[str, Any], path: str) -> None:
    expected = schema.get("type")
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected not in checks:
        raise TruthError("%s has unsupported JSON type %s" % (path, expected))
    if not checks[expected](value):
        raise TruthError("%s must be %s" % (path, expected))
    if "enum" in schema and value not in schema["enum"]:
        raise TruthError("%s must be one of %s" % (path, schema["enum"]))
    if expected == "object":
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                raise TruthError("%s.%s is required" % (path, name))
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise TruthError("%s has unknown fields: %s" % (path, ", ".join(unknown)))
        for name, child in value.items():
            if name in properties:
                _validate_value(child, properties[name], "%s.%s" % (path, name))
    if expected == "array":
        item_schema = schema.get("items")
        if not isinstance(item_schema, dict):
            raise TruthError("%s array schema requires items" % path)
        for index, child in enumerate(value):
            _validate_value(child, item_schema, "%s[%d]" % (path, index))


def _schema_references(schema: Any) -> Set[str]:
    if isinstance(schema, list):
        result: Set[str] = set()
        for item in schema:
            result.update(_schema_references(item))
        return result
    if not isinstance(schema, dict):
        return set()
    result = {schema["$ref"]} if isinstance(schema.get("$ref"), str) else set()
    for value in schema.values():
        result.update(_schema_references(value))
    return result


class OntologyRegistry:
    def __init__(self, document: Mapping[str, Any]):
        self.document = copy.deepcopy(dict(document))
        self.registry_id = str(require(self.document.get("registry_id"), "registry_id"))
        self.version = int(require(self.document.get("version"), "version"))
        if self.version < 1:
            raise TruthError("ontology version must be positive")
        self.types = unique_ids(self.document.get("types", []), "type_id", "types")
        self.workstream_packs = unique_ids(self.document.get("workstream_packs", []), "workstream_id", "workstream_packs")
        self.migrations = list(self.document.get("migrations", []))
        self._validate()

    def _validate_schema(self, type_id: str, schema: Mapping[str, Any]) -> None:
        if schema.get("type") != "object":
            raise TruthError("%s schema root must be object" % type_id)
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            raise TruthError("%s schema requires properties" % type_id)
        if not isinstance(schema.get("required", []), list):
            raise TruthError("%s required must be a list" % type_id)
        missing_required = sorted(set(schema.get("required", [])) - set(properties))
        if missing_required:
            raise TruthError("%s requires undefined fields: %s" % (type_id, ", ".join(missing_required)))
        for name, spec in properties.items():
            if not isinstance(spec, dict):
                raise TruthError("%s.%s schema must be a mapping" % (type_id, name))
            if "$ref" not in spec and spec.get("type") not in JSON_TYPES:
                raise TruthError("%s.%s needs a JSON type or $ref" % (type_id, name))

    def _validate(self) -> None:
        if not self.types:
            raise TruthError("ontology must define types")
        for type_id, definition in self.types.items():
            if definition.get("category") not in TYPE_CATEGORIES:
                raise TruthError("%s has unsupported category" % type_id)
            if definition.get("status") not in TYPE_STATUSES:
                raise TruthError("%s has unsupported status" % type_id)
            if definition.get("status") == "QUARANTINED" and definition.get("production", False):
                raise TruthError("quarantined type %s cannot be production" % type_id)
            if definition.get("status") == "DEPRECATED" and not definition.get("replacement_type_id"):
                raise TruthError("deprecated type %s needs a replacement" % type_id)
            self._validate_schema(type_id, definition.get("schema", {}))
            references = set(definition.get("references", [])) | _schema_references(definition.get("schema", {}))
            missing = sorted(references - set(self.types))
            if missing:
                raise TruthError("%s references undefined types: %s" % (type_id, ", ".join(missing)))
        deprecated_replacements = {
            item.get("replacement_type_id")
            for item in self.types.values()
            if item.get("status") == "DEPRECATED"
        }
        if None in deprecated_replacements or not deprecated_replacements <= set(self.types):
            raise TruthError("deprecated type replacement is undefined")
        expected = set(MA_WORKSTREAM_CATALOG)
        actual = set(self.workstream_packs)
        if actual != expected:
            raise TruthError("workstream packs must match the closed 22-pack catalog; missing=%s extra=%s" % (sorted(expected - actual), sorted(actual - expected)))
        for workstream_id, pack in self.workstream_packs.items():
            type_ids = set(pack.get("type_ids", []))
            missing = sorted(type_ids - set(self.types))
            if missing:
                raise TruthError("workstream %s references undefined types: %s" % (workstream_id, ", ".join(missing)))
            if not type_ids:
                raise TruthError("workstream %s must declare typed outputs" % workstream_id)
        self._validate_no_orphans()
        self._validate_migrations()
        if "consent-requirement" not in self.types or "consent-status" not in self.types:
            raise TruthError("consent requirement and consent status must be distinct types")

    def _validate_no_orphans(self) -> None:
        production = {type_id for type_id, item in self.types.items() if item.get("production", False)}
        roots = {type_id for type_id, item in self.types.items() if item.get("root", False)}
        referenced: Set[str] = set()
        for item in self.types.values():
            referenced.update(item.get("references", []))
            referenced.update(_schema_references(item.get("schema", {})))
        for pack in self.workstream_packs.values():
            referenced.update(pack.get("type_ids", []))
        orphans = sorted(production - roots - referenced)
        if orphans:
            raise TruthError("orphan production types: %s" % ", ".join(orphans))

    def _validate_migrations(self) -> None:
        seen: Set[Tuple[int, int]] = set()
        for index, migration in enumerate(self.migrations):
            source = int(migration.get("from_version", 0))
            target = int(migration.get("to_version", 0))
            if target != source + 1 or (source, target) in seen:
                raise TruthError("migration[%d] must be a unique single-version step" % index)
            seen.add((source, target))
            for operation in migration.get("operations", []):
                if operation.get("op") not in MIGRATION_OPS:
                    raise TruthError("migration[%d] has unsupported operation" % index)

    def validate_instance(self, type_id: str, value: Mapping[str, Any], production: bool = True) -> Dict[str, Any]:
        definition = self.types.get(type_id)
        if not definition:
            raise TruthError("undefined ontology type %s" % type_id)
        if production and definition.get("status") != "ACTIVE":
            raise TruthError("type %s is not active for production" % type_id)
        normalized = copy.deepcopy(dict(value))
        _validate_value(normalized, definition["schema"], type_id)
        encoded = canonical_json(normalized)
        round_trip = json.loads(encoded)
        if canonical_json(round_trip) != encoded:
            raise TruthError("%s failed deterministic round trip" % type_id)
        return round_trip

    def migrate(self, type_id: str, value: Mapping[str, Any], from_version: int, to_version: Optional[int] = None) -> Dict[str, Any]:
        target = to_version or self.version
        if from_version > target:
            raise TruthError("downgrade migrations are not supported")
        current = copy.deepcopy(dict(value))
        version = from_version
        steps = {(int(item["from_version"]), int(item["to_version"])): item for item in self.migrations}
        while version < target:
            step = steps.get((version, version + 1))
            if not step:
                raise TruthError("no migration path from version %d to %d" % (version, target))
            for operation in step.get("operations", []):
                if operation.get("type_id") not in {None, type_id}:
                    continue
                name = operation["op"]
                if name == "rename_field":
                    old, new = operation["from"], operation["to"]
                    if old in current:
                        if new in current:
                            raise TruthError("migration would overwrite %s" % new)
                        current[new] = current.pop(old)
                elif name == "set_default":
                    current.setdefault(operation["field"], copy.deepcopy(operation.get("value")))
                elif name == "map_enum" and operation["field"] in current:
                    current[operation["field"]] = operation.get("mapping", {}).get(current[operation["field"]], current[operation["field"]])
                elif name == "drop_field":
                    current.pop(operation["field"], None)
            version += 1
        return self.validate_instance(type_id, current)

    def artifact(self) -> Dict[str, Any]:
        value = copy.deepcopy(self.document)
        value["artifact_type"] = "OntologyRegistry"
        value["schema_version"] = 1
        value["workstream_pack_count"] = len(self.workstream_packs)
        value["production_type_count"] = sum(bool(item.get("production")) for item in self.types.values())
        value["quarantined_type_ids"] = sorted(type_id for type_id, item in self.types.items() if item.get("status") == "QUARANTINED")
        value["gates"] = {
            "no_orphan_production_types": True,
            "closed_22_workstream_packs": len(self.workstream_packs) == 22,
            "round_trip_enabled": True,
            "ambiguous_types_quarantined": all(not item.get("production") for item in self.types.values() if item.get("status") == "QUARANTINED"),
            "migration_chain_valid": True,
        }
        set_fingerprint(value, "registry_fingerprint")
        return value


def registry_impact(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    old_version, new_version = int(previous.get("version", 0)), int(current.get("version", 0))
    if new_version <= old_version:
        raise TruthError("ontology changes require a version increment")
    old_types = unique_ids(previous.get("types", []), "type_id", "previous.types")
    new_types = unique_ids(current.get("types", []), "type_id", "current.types")
    added = sorted(set(new_types) - set(old_types))
    removed = sorted(set(old_types) - set(new_types))
    changed = sorted(type_id for type_id in set(old_types) & set(new_types) if fingerprint(old_types[type_id]) != fingerprint(new_types[type_id]))
    affected = set(added + removed + changed)
    for type_id, definition in new_types.items():
        references = set(definition.get("references", [])) | _schema_references(definition.get("schema", {}))
        if references & affected:
            affected.add(type_id)
    packs = []
    for pack in current.get("workstream_packs", []):
        if set(pack.get("type_ids", [])) & affected:
            packs.append(pack.get("workstream_id"))
    result = {
        "registry_id": current.get("registry_id"),
        "from_version": old_version,
        "to_version": new_version,
        "added_types": added,
        "removed_types": removed,
        "changed_types": changed,
        "affected_type_ids": sorted(affected),
        "affected_workstreams": sorted(item for item in packs if item),
    }
    set_fingerprint(result, "impact_fingerprint")
    return result
