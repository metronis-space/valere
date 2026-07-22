"""C4: independent document ingestion, round-trip metrics, and evidence graph."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from collections import defaultdict
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence
from xml.etree import ElementTree

from utils.artifacts import set_fingerprint
from utils.errors import MatterError


INGESTOR_ID = "c4-zipxml-poppler-regex-v1"
SEVERITY_WEIGHT = {"CRITICAL": 5, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
ALLOWED_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".eml", ".json", ".txt", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MAX_FILE_BYTES = 5_000_000
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_zip(path: Path) -> tuple[bool, str | None]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
                return False, "archive contains an unsafe member path"
            if any("vbaproject.bin" in name.lower() or name.lower().endswith((".exe", ".dll", ".js", ".vbs")) for name in names):
                return False, "archive contains a macro or executable payload"
    except (OSError, zipfile.BadZipFile):
        return False, "office file is not a valid ZIP package"
    return True, None


def inventory_document_world(root: str, expected: Mapping[str, str]) -> Dict[str, Any]:
    base = Path(root)
    if not base.is_dir():
        raise MatterError("document-world directory does not exist")
    paths = sorted(path for path in base.rglob("*") if path.is_file())
    actual_names = {str(path.relative_to(base)) for path in paths}
    issues = []
    if actual_names != set(expected):
        issues.append(
            "inventory mismatch; missing=%s unexpected=%s"
            % (sorted(set(expected) - actual_names), sorted(actual_names - set(expected)))
        )
    records = []
    hashes: Dict[str, list[str]] = defaultdict(list)
    for path in paths:
        relative = str(path.relative_to(base))
        data = path.read_bytes()
        safe = path.suffix.lower() in ALLOWED_EXTENSIONS and len(data) <= MAX_FILE_BYTES
        reason = None
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            safe, reason = False, "file type is not allowlisted"
        elif len(data) > MAX_FILE_BYTES:
            safe, reason = False, "file exceeds the size limit"
        elif b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in data or data.startswith((b"MZ", b"\x7fELF", b"\xd0\xcf\x11\xe0")):
            safe, reason = False, "malware/executable signature detected"
        elif path.suffix.lower() in {".docx", ".xlsx"}:
            safe, reason = _safe_zip(path)
        digest = _hash(path)
        hashes[digest].append(relative)
        if digest != expected.get(relative):
            issues.append("file fingerprint mismatch: %s" % relative)
        if not safe:
            issues.append("unsafe file %s: %s" % (relative, reason))
        records.append(
            {
                "path": relative,
                "extension": path.suffix.lower(),
                "size_bytes": len(data),
                "sha256": digest,
                "safe": safe,
                "reason": reason,
            }
        )
    duplicates = [names for names in hashes.values() if len(names) > 1]
    return {
        "ok": not issues,
        "files": records,
        "issues": issues,
        "duplicate_groups": duplicates,
        "macro_count": sum(not item["safe"] and "macro" in str(item["reason"]) for item in records),
    }


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter("{%s}p" % W):
        paragraphs.append("".join(node.text or "" for node in paragraph.iter("{%s}t" % W)))
    return "\n".join(paragraphs)


def _xlsx_content(path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relations.findall("{%s}Relationship" % PR)}
        result = {}
        formulas = {}
        for sheet in workbook.findall(".//{%s}sheet" % S):
            target = targets[sheet.attrib["{%s}id" % R]]
            xml_path = "xl/" + target.lstrip("/")
            tree = ElementTree.fromstring(archive.read(xml_path))
            cells = {}
            for cell in tree.findall(".//{%s}c" % S):
                reference = cell.attrib["r"]
                if cell.attrib.get("t") == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//{%s}t" % S))
                else:
                    raw = cell.findtext("{%s}v" % S)
                    value = float(raw) if raw and "." in raw else int(raw) if raw is not None else None
                cells[reference] = value
                formula = cell.findtext("{%s}f" % S)
                if formula:
                    formulas["%s!%s" % (sheet.attrib["name"], reference)] = formula
            result[sheet.attrib["name"]] = cells
    return {"cells": result, "formulas": formulas}


def _pdf_text(path: Path) -> tuple[str, str]:
    command = shutil.which("pdftotext")
    if command:
        run = subprocess.run([command, "-layout", str(path), "-"], capture_output=True, check=False)
        if run.returncode == 0 and run.stdout.strip():
            return run.stdout.decode("utf-8", errors="replace"), "poppler-pdftotext"
    values = []
    for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", path.read_bytes()):
        value = match.group(1).decode("ascii", errors="replace")
        values.append(value.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\"))
    if not values:
        raise ValueError("PDF has no extractable text")
    return "\n".join(values), "pdf-literal-fallback"


def _email_text(path: Path) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    body = message.get_body(preferencelist=("plain",))
    return "Subject: %s\n%s" % (message.get("Subject", ""), body.get_content() if body else "")


def _observation(
    fact_path: str,
    value: Any,
    file: str,
    source: str,
    needle: str,
    method: str,
    locator: str | None = None,
) -> Dict[str, Any]:
    start = source.find(needle)
    return {
        "fact_path": fact_path,
        "value": value,
        "file": file,
        "method": method,
        "confidence": 1.0,
        "span": {
            "start": start,
            "end": start + len(needle) if start >= 0 else -1,
            "text": needle,
            "locator": locator or "characters:%d-%d" % (start, start + len(needle)),
        },
    }


def _match(
    observations: list[Dict[str, Any]],
    text: str,
    pattern: str,
    fact_path: str,
    file: str,
    convert: Any = str,
    method: str = "independent-regex",
) -> None:
    match = re.search(pattern, text, re.MULTILINE)
    if match:
        raw = match.group(1)
        observations.append(_observation(fact_path, convert(raw), file, text, raw, method))


def _extract_files(root: Path) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    observations: list[Dict[str, Any]] = []
    parsed: Dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root))
        suffix = path.suffix.lower()
        if suffix == ".docx":
            text = _docx_text(path)
            parsed[relative] = {"kind": "DOCX", "text": text}
            if relative.endswith("material-services-agreement.docx"):
                _match(observations, text, r"^Target Party: (.+)$", "contract.target_party", relative)
                _match(observations, text, r"^Counterparty: (.+)$", "contract.counterparty", relative)
                _match(observations, text, r"Annual Contract Value: USD (\d+)", "contract.annual_value_usd", relative, int)
                clause = "A merger or transfer of control requires the Counterparty's prior written consent."
                if clause in text:
                    observations.append(_observation("contract.change_control_clause", True, relative, text, clause, "clause-parser"))
                    observations.append(_observation("contract.consent_required", True, relative, text, "prior written consent", "clause-parser"))
            elif relative.endswith("amendment-001.docx"):
                _match(observations, text, r"^Effective Date: (\d{4}-\d{2}-\d{2})$", "contract.amendment.effective_date", relative)
                _match(observations, text, r"^Order: (\d+)$", "contract.amendment.order", relative, int)
            elif relative.endswith("disclosure-schedule.docx"):
                mappings = [
                    (r"Software Asset Value: USD (\d+)", "assets.software_value_usd", int),
                    (r"Accounts Payable Liability: USD (\d+)", "liabilities.accounts_payable_usd", int),
                    (r"Debt Principal: USD (\d+)", "debts.principal_usd", int),
                    (r"Lien Status: (\S+)", "liens.status", str),
                    (r"Employee employee-001 Status: (\S+)", "employees.employee-001.status", str),
                ]
                for pattern, fact, convert in mappings:
                    _match(observations, text, pattern, fact, relative, convert)
        elif suffix == ".xlsx":
            value = _xlsx_content(path)
            parsed[relative] = {"kind": "XLSX", **value}
            cells = value["cells"]
            for sheet, cell, fact in (
                ("Capitalization", "C2", "capitalization.units"),
                ("Capitalization", "D2", "capitalization.value_usd"),
                ("Ownership", "C2", "ownership.seller_target_percentage"),
            ):
                raw = cells[sheet][cell]
                observations.append(_observation(fact, raw, relative, str(raw), str(raw), "ooxml-cell-parser", "%s!%s" % (sheet, cell)))
        elif suffix == ".pdf":
            text, engine = _pdf_text(path)
            parsed[relative] = {"kind": "PDF", "text": text, "engine": engine}
            _match(observations, text, r"Transaction Structure: (\S+)", "transaction.structure", relative, method=engine)
            _match(observations, text, r"Signing Date: (\d{4}-\d{2}-\d{2})", "transaction.signing", relative, method=engine)
            _match(observations, text, r"Closing Date: (\d{4}-\d{2}-\d{2})", "transaction.closing", relative, method=engine)
        elif suffix == ".eml":
            parsed[relative] = {"kind": "EMAIL", "text": _email_text(path)}
        elif suffix == ".json":
            parsed[relative] = {"kind": "JSON", "value": json.loads(path.read_text(encoding="utf-8"))}
        elif suffix == ".txt":
            text = path.read_text(encoding="utf-8")
            parsed[relative] = {"kind": "TEXT", "text": text}
            if relative.endswith("consent-register.txt"):
                _match(observations, text, r"Consent Status: (\S+)", "contract.consent_status", relative)
                _match(observations, text, r"Notice Status: (\S+)", "contract.notice_status", relative)
                _match(observations, text, r"Approval Status: (\S+)", "contract.approval_status", relative)
                _match(observations, text, r"Waiver Status: (\S+)", "contract.consent_waived", relative, lambda value: None if value == "UNKNOWN" else value)
            elif relative.endswith("litigation-regulatory.txt"):
                _match(observations, text, r"Litigation Status: (\S+)", "litigation.status", relative)
                _match(observations, text, r"Regulatory Status: (\S+)", "regulatory.status", relative)
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            command = shutil.which("tesseract")
            if command:
                run = subprocess.run([command, str(path), "stdout"], capture_output=True, check=False)
                if run.returncode:
                    raise ValueError("OCR failed for %s" % relative)
                parsed[relative] = {"kind": "IMAGE", "text": run.stdout.decode("utf-8", errors="replace"), "engine": "tesseract-cli"}
            else:
                parsed[relative] = {"kind": "IMAGE", "text": "", "engine": "ocr-unavailable"}
    return observations, parsed


def _expected_facts(world: Mapping[str, Any]) -> list[Dict[str, Any]]:
    entities = {item["entity_id"]: item["name"] for item in world["entities"]}
    contract = world["contracts"][0]
    amendment = contract["amendments"][0]
    consent = world["consents"][0]
    transaction = world["transaction"]
    cap = world["capitalization"][0]
    ownership = next(item for item in world["ownership"] if item["owner_id"] == "seller")
    values = [
        ("contract.target_party", entities["target"], "HIGH", ".docx"),
        ("contract.counterparty", entities["counterparty"], "HIGH", ".docx"),
        ("contract.change_control_clause", True, "CRITICAL", ".docx"),
        ("contract.consent_required", True, "CRITICAL", ".docx"),
        ("contract.annual_value_usd", contract["annual_value"]["amount"], "HIGH", ".docx"),
        ("contract.amendment.order", amendment["order"], "HIGH", ".docx"),
        ("contract.amendment.effective_date", amendment["effective_date"], "HIGH", ".docx"),
        ("transaction.structure", transaction["structure"], "HIGH", ".pdf"),
        ("transaction.signing", transaction["timeline"]["signing"], "HIGH", ".pdf"),
        ("transaction.closing", transaction["timeline"]["closing"], "CRITICAL", ".pdf"),
        ("contract.consent_status", consent["state"], "CRITICAL", ".txt"),
        ("contract.notice_status", consent["notice_state"], "HIGH", ".txt"),
        ("contract.approval_status", consent["approval_state"], "HIGH", ".txt"),
        ("contract.consent_waived", consent["waived"], "HIGH", ".txt"),
        ("capitalization.units", cap["units"], "MEDIUM", ".xlsx"),
        ("capitalization.value_usd", cap["value"], "MEDIUM", ".xlsx"),
        ("ownership.seller_target_percentage", ownership["percentage"], "MEDIUM", ".xlsx"),
        ("assets.software_value_usd", world["assets"][0]["value"]["amount"], "MEDIUM", ".docx"),
        ("liabilities.accounts_payable_usd", world["liabilities"][0]["value"]["amount"], "MEDIUM", ".docx"),
        ("debts.principal_usd", world["debts"][0]["principal"]["amount"], "MEDIUM", ".docx"),
        ("liens.status", world["liens"][0]["status"], "LOW", ".docx"),
        ("employees.employee-001.status", world["employees"][0]["status"], "LOW", ".docx"),
        ("litigation.status", world["litigation"][0]["status"], "LOW", ".txt"),
        ("regulatory.status", world["regulatory"][0]["status"], "MEDIUM", ".txt"),
    ]
    return [{"fact_path": path, "expected": value, "severity": severity, "file_type": file_type} for path, value, severity, file_type in values]


def _group_metrics(rows: Sequence[Mapping[str, Any]], key: str) -> Dict[str, Any]:
    result = {}
    for name in sorted({str(row[key]) for row in rows}):
        group = [row for row in rows if str(row[key]) == name]
        recovered = sum(row["status"] == "RECOVERED" for row in group)
        false = sum(row["status"] in {"MISMATCH", "CONFLICT"} for row in group)
        result[name] = {
            "expected": len(group),
            "recovered": recovered,
            "precision": recovered / (recovered + false) if recovered + false else 1.0,
            "recall": recovered / len(group) if group else 1.0,
            "unknown_rate": sum(row["status"] == "UNKNOWN" for row in group) / len(group) if group else 0.0,
        }
    return result


def _compare(world: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    grouped: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in observations:
        grouped[str(item["fact_path"])].append(item)
    rows = []
    for expected in _expected_facts(world):
        found = grouped.get(expected["fact_path"], [])
        values = [item["value"] for item in found]
        if not values:
            status = "UNKNOWN"
        elif any(value != expected["expected"] for value in values) and expected["expected"] in values:
            status = "CONFLICT"
        elif all(value == expected["expected"] for value in values):
            status = "RECOVERED"
        else:
            status = "MISMATCH"
        support = next((item for item in found if item["value"] == expected["expected"]), None)
        rows.append(
            {
                **expected,
                "actual_values": values,
                "status": status,
                "support": support,
            }
        )
    recovered = sum(row["status"] == "RECOVERED" for row in rows)
    false = sum(row["status"] in {"MISMATCH", "CONFLICT"} for row in rows)
    weighted_total = sum(SEVERITY_WEIGHT[row["severity"]] for row in rows)
    weighted_recovered = sum(SEVERITY_WEIGHT[row["severity"]] for row in rows if row["status"] == "RECOVERED")
    metrics = {
        "expected_fields": len(rows),
        "recovered_fields": recovered,
        "precision": recovered / (recovered + false) if recovered + false else 1.0,
        "recall": recovered / len(rows),
        "severity_weighted_recovery": weighted_recovered / weighted_total,
        "span_accuracy": sum(
            row["status"] == "RECOVERED" and row["support"] and row["support"]["span"]["start"] >= 0 for row in rows
        )
        / len(rows),
        "mean_extraction_uncertainty": sum(
            1.0 - row["support"]["confidence"] if row["support"] else 1.0 for row in rows
        )
        / len(rows),
        "unknown_rate": sum(row["status"] == "UNKNOWN" for row in rows) / len(rows),
        "unrecoverable_fact_paths": [row["fact_path"] for row in rows if row["status"] != "RECOVERED"],
        "by_severity": _group_metrics(rows, "severity"),
        "by_file_type": _group_metrics(rows, "file_type"),
    }
    return rows, metrics


def _document_quality(parsed: Mapping[str, Any]) -> Dict[str, Any]:
    contract = parsed["contracts/material-services-agreement.docx"]["text"]
    amendment = parsed["contracts/amendment-001.docx"]["text"]
    workbook = parsed["financial/capitalization-funds-flow.xlsx"]
    funds = workbook["cells"]["Funds Flow"]
    defined_term = 'Defined Term: "Change of Control"' in contract
    cross_reference = "See Section 2.1" in contract and "Section 2.1 Consent Evidence" in contract
    signatures = contract.count("Signed for ") == 2 and amendment.count("Signed for ") == 2
    math_valid = workbook["formulas"].get("Funds Flow!B4") == "B2-B3" and funds["B4"] == funds["B2"] - funds["B3"]
    precedence = {
        "documents": [
            {"document_id": "contract-001", "order": 0, "status": "CURRENT"},
            {"document_id": "amendment-001", "order": 1, "status": "CURRENT", "amends": "contract-001"},
        ],
        "operative_clause_source": "contract-001",
        "amendment_confirms_unchanged": "remain unchanged" in amendment,
    }
    return {
        "defined_terms_valid": defined_term,
        "cross_references_valid": cross_reference,
        "signatures_valid": signatures,
        "math_valid": math_valid,
        "precedence": precedence,
        "precedence_valid": precedence["amendment_confirms_unchanged"],
    }


def _evidence_classifications(world: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], phase2: Mapping[str, Any]) -> list[Dict[str, Any]]:
    recovered = {row["fact_path"] for row in rows if row["status"] == "RECOVERED"}
    result = []
    for item in world["evidence"]:
        expected = item["availability"]
        if expected == "AVAILABLE":
            actual = "AVAILABLE" if item["fact_path"] in recovered else "MISSING"
        else:
            actual = expected
        result.append(
            {
                "evidence_id": item["evidence_id"],
                "fact_path": item["fact_path"],
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )
    missing = next((item for item in phase2.get("examples", []) if item.get("kind") == "MISSING_EVIDENCE"), None)
    if missing:
        state = next(item for item in missing["issue_plan"]["evidence_state"] if item["fact_path"] == "contract.consent_status")
        result.append(
            {
                "evidence_id": "phase2-missing-consent-probe",
                "fact_path": state["fact_path"],
                "expected": "MISSING",
                "actual": "MISSING" if state["availability"] == "MISSING" else state["availability"],
                "passed": state["availability"] == "MISSING",
            }
        )
    return result


def _evidence_graph(
    world: Mapping[str, Any],
    inventory: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    classifications: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    nodes = [{"node_id": "matter:%s" % world["matter"]["matter_id"], "node_type": "MATTER"}]
    relationships = []
    for document in inventory["files"]:
        document_id = "document:%s" % document["path"]
        nodes.append({"node_id": document_id, "node_type": "DOCUMENT", "path": document["path"], "fingerprint": document["sha256"]})
        relationships.append({"type": "BELONGS_TO_MATTER", "from": document_id, "to": nodes[0]["node_id"]})
    for row in rows:
        fact_id = "fact:%s" % row["fact_path"]
        nodes.append({"node_id": fact_id, "node_type": "FACT", "fact_path": row["fact_path"], "value": row["expected"], "status": row["status"], "severity": row["severity"]})
        if row["support"]:
            span_id = "span:%s:%s" % (row["support"]["file"], row["fact_path"])
            nodes.append({"node_id": span_id, "node_type": "EVIDENCE_SPAN", **row["support"]["span"]})
            relationships.extend(
                [
                    {"type": "SPAN_IN_DOCUMENT", "from": span_id, "to": "document:%s" % row["support"]["file"]},
                    {"type": "SUPPORTS_FACT", "from": span_id, "to": fact_id},
                ]
            )
    for item in classifications:
        node_id = "availability:%s" % item["evidence_id"]
        nodes.append({"node_id": node_id, "node_type": "EVIDENCE_AVAILABILITY", **dict(item)})
        relationships.append({"type": "CLASSIFIES_EVIDENCE_FOR", "from": node_id, "to": "fact:%s" % item["fact_path"]})
    relationships.append({"type": "AMENDS", "from": "document:contracts/amendment-001.docx", "to": "document:contracts/material-services-agreement.docx"})
    relationships.extend(
        [
            {"type": "CORROBORATES", "from": "document:correspondence/consent-qa.eml", "to": "document:consents/consent-register.txt"},
            {"type": "APPROVES_TRANSACTION_FOR", "from": "document:corporate/board-minutes.pdf", "to": nodes[0]["node_id"]},
        ]
    )
    graph = {
        "artifact_type": "EvidenceGraph",
        "schema_version": 1,
        "matter_fingerprint": world["matter_fingerprint"],
        "nodes": nodes,
        "relationships": relationships,
    }
    set_fingerprint(graph, "evidence_graph_fingerprint")
    return graph


def ingest_document_world(
    world: Mapping[str, Any], root: str, render_manifest: Mapping[str, Any], phase2: Mapping[str, Any]
) -> Dict[str, Any]:
    """Read rendered bytes through C4-owned parsers and measure AR-002."""

    expected = {item["path"]: item["sha256"] for item in render_manifest["files"]}
    inventory = inventory_document_world(root, expected)
    observations, parsed = _extract_files(Path(root))
    rows, metrics = _compare(world, observations)
    quality = _document_quality(parsed)
    classifications = _evidence_classifications(world, rows, phase2)
    graph = _evidence_graph(world, inventory, rows, classifications)
    index = parsed.get("vdr-index.json", {}).get("value", {})
    indexed_hashes = {item.get("path"): item.get("sha256") for item in index.get("documents", [])}
    actual_hashes = {item["path"]: item["sha256"] for item in inventory["files"] if item["path"] != "vdr-index.json"}
    index_valid = index.get("matter_id") == world["matter"]["matter_id"] and indexed_hashes == actual_hashes
    file_types = {item["extension"] for item in inventory["files"]}
    parser_engines = sorted(
        {"zipfile-elementtree-docx", "zipfile-elementtree-xlsx", "email-parser", "json", "text-regex"}
        | {item.get("engine") for item in parsed.values() if item.get("engine")}
    )
    all_parse = len(parsed) == len(inventory["files"])
    classifications_ok = all(item["passed"] for item in classifications) and {"MISSING", "UNPRODUCED"} <= {
        item["actual"] for item in classifications
    }
    return {
        "ingestor": {
            "engine_id": INGESTOR_ID,
            "implementation": "matter.ingestion",
            "uses_model": False,
            "parser_engines": parser_engines,
            "ocr": {
                "adapter": "tesseract-cli",
                "available": bool(shutil.which("tesseract")),
                "image_files": sum(item["extension"] in {".png", ".jpg", ".jpeg", ".tif", ".tiff"} for item in inventory["files"]),
                "status": "NOT_REQUIRED" if not any(item["extension"] in {".png", ".jpg", ".jpeg", ".tif", ".tiff"} for item in inventory["files"]) else "AVAILABLE" if shutil.which("tesseract") else "BLOCKED",
            },
        },
        "inventory": inventory,
        "vdr_index_valid": index_valid,
        "file_types": sorted(file_types),
        "all_files_open_and_parse": all_parse,
        "observations": observations,
        "comparison": rows,
        "metrics": metrics,
        "document_quality": quality,
        "evidence_classifications": classifications,
        "classification_valid": classifications_ok,
        "evidence_graph": graph,
        "economics": {
            "files_attempted": len(inventory["files"]),
            "files_parsed": len(parsed),
            "render_extract_yield": len(parsed) / len(inventory["files"]) if inventory["files"] else 0.0,
            "total_bytes": sum(item["size_bytes"] for item in inventory["files"]),
            "estimated_variable_cost_usd": 0.0,
            "economically_viable": all_parse and sum(item["size_bytes"] for item in inventory["files"]) <= MAX_FILE_BYTES,
        },
    }
