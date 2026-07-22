"""B1: point-in-time source acquisition, normalization, and snapshots."""

from __future__ import annotations

import copy
import html
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from utils.artifacts import atomic_write_json, fingerprint, set_fingerprint, verify_fingerprint
from utils.errors import TruthError

from .common import iso_date, iso_datetime, optional_date, require, unique_ids


SOURCE_TYPES = {"OFFICIAL", "LICENSED", "PUBLIC_BENCHMARK", "SYNTHETIC"}
AUTHORITY_KINDS = {
    "STATUTE",
    "REGULATION",
    "COURT_RULE",
    "OPINION",
    "AGENCY_GUIDANCE",
    "CONTRACT",
    "PLAYBOOK",
}
COVERAGE_STATUSES = {"COVERED", "UNAVAILABLE", "OUT_OF_SCOPE"}
TEXT_MEDIA_TYPES = {"text/plain", "text/html", "application/xhtml+xml"}


class OcrExtractor(Protocol):
    """Injectable OCR boundary for sources that do not contain usable text."""

    def extract(self, payload: bytes, media_type: str) -> str:
        ...


class InMemorySourceConnector:
    def __init__(self, records: Iterable[Mapping[str, Any]]):
        self.records = {str(item["source_id"]): copy.deepcopy(dict(item)) for item in records}

    def acquire(self, source_id: str) -> Dict[str, Any]:
        try:
            return copy.deepcopy(self.records[source_id])
        except KeyError as exc:
            raise TruthError("unknown source %s" % source_id) from exc


class HttpSourceConnector:
    """Small official-source HTTP connector with an explicit host allowlist."""

    def __init__(self, allowed_hosts: Sequence[str], timeout_seconds: int = 20, max_bytes: int = 10_000_000):
        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def acquire_url(self, metadata: Mapping[str, Any]) -> Dict[str, Any]:
        uri = str(require(metadata.get("uri"), "source.uri"))
        parsed = urlparse(uri)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in self.allowed_hosts:
            raise TruthError("source URI is outside the HTTPS host allowlist")
        request = Request(uri, headers={"User-Agent": "valere-truth/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec: allowlisted HTTPS only
            final = urlparse(response.geturl())
            if final.scheme != "https" or (final.hostname or "").lower() not in self.allowed_hosts:
                raise TruthError("source redirect escaped the HTTPS host allowlist")
            payload = response.read(self.max_bytes + 1)
            if len(payload) > self.max_bytes:
                raise TruthError("source exceeds acquisition size limit")
            media_type = response.headers.get_content_type()
        result = copy.deepcopy(dict(metadata))
        result["payload"] = payload
        result["media_type"] = media_type
        result.setdefault("acquired_at", datetime.now(timezone.utc).isoformat())
        return result

    def acquire(self, source_id: str) -> Dict[str, Any]:
        raise TruthError("HTTP acquisition requires metadata; call acquire_url")


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def normalize_citation(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    normalized = re.sub(r"\s*§\s*", " § ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_docket(value: str) -> str:
    return re.sub(r"\s+", "-", str(value or "").strip().upper())


def extract_text(record: Mapping[str, Any], ocr: Optional[OcrExtractor] = None) -> str:
    if isinstance(record.get("content"), str):
        raw = record["content"]
    else:
        payload = record.get("payload")
        if not isinstance(payload, (bytes, bytearray)):
            raise TruthError("source requires string content or byte payload")
        media_type = str(record.get("media_type") or "application/octet-stream").split(";")[0]
        if media_type in TEXT_MEDIA_TYPES:
            raw = bytes(payload).decode(str(record.get("encoding") or "utf-8"), errors="strict")
        elif ocr is not None:
            raw = ocr.extract(bytes(payload), media_type)
        else:
            raise TruthError("binary source %s requires an OCR/text extractor" % media_type)
    media_type = str(record.get("media_type") or "text/plain").split(";")[0]
    if media_type in {"text/html", "application/xhtml+xml"}:
        parser = _VisibleTextParser()
        parser.feed(raw)
        raw = html.unescape("".join(parser.parts))
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise TruthError("source extraction produced no text")
    return text


def section_text(text: str) -> List[Dict[str, Any]]:
    """Split normalized text into stable paragraph/heading spans."""

    spans: List[Dict[str, Any]] = []
    cursor = 0
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    for index, chunk in enumerate(chunks):
        start = text.find(chunk, cursor)
        end = start + len(chunk)
        cursor = end
        heading = bool(re.match(r"^(?:§|SECTION\b|ARTICLE\b|[IVX]+\.)", chunk, re.IGNORECASE))
        span = {
            "span_id": "span-%04d" % (index + 1),
            "kind": "SECTION" if heading else "PARAGRAPH",
            "start": start,
            "end": end,
            "text": chunk,
        }
        span["content_fingerprint"] = fingerprint(chunk)
        spans.append(span)
    if not spans:
        raise TruthError("source parser produced no spans")
    return spans


def normalize_source(record: Mapping[str, Any], ocr: Optional[OcrExtractor] = None) -> Dict[str, Any]:
    source_id = str(require(record.get("source_id"), "source.source_id"))
    source_type = str(require(record.get("source_type"), "%s.source_type" % source_id)).upper()
    kind = str(require(record.get("authority_kind"), "%s.authority_kind" % source_id)).upper()
    if source_type not in SOURCE_TYPES:
        raise TruthError("%s has unsupported source_type %s" % (source_id, source_type))
    if kind not in AUTHORITY_KINDS:
        raise TruthError("%s has unsupported authority_kind %s" % (source_id, kind))
    text = extract_text(record, ocr=ocr)
    effective = iso_date(record.get("effective_date"), "%s.effective_date" % source_id)
    amended = optional_date(record.get("amended_date"), "%s.amended_date" % source_id)
    repealed = optional_date(record.get("repealed_date"), "%s.repealed_date" % source_id)
    if repealed and repealed < effective:
        raise TruthError("%s repealed_date precedes effective_date" % source_id)
    acquired = iso_datetime(record.get("acquired_at"), "%s.acquired_at" % source_id)
    uri = str(require(record.get("uri"), "%s.uri" % source_id))
    parsed_uri = urlparse(uri)
    if parsed_uri.scheme not in {"https", "file", "urn"}:
        raise TruthError("%s source URI must be https, file, or urn" % source_id)
    normalized = {
        "source_id": source_id,
        "source_type": source_type,
        "authority_kind": kind,
        "title": str(require(record.get("title"), "%s.title" % source_id)),
        "uri": uri,
        "jurisdiction": str(require(record.get("jurisdiction"), "%s.jurisdiction" % source_id)),
        "issuing_body": str(require(record.get("issuing_body"), "%s.issuing_body" % source_id)),
        "court_level": record.get("court_level"),
        "citation": normalize_citation(str(record.get("citation") or "")),
        "docket": normalize_docket(str(record.get("docket") or "")),
        "effective_date": effective.isoformat(),
        "amended_date": amended.isoformat() if amended else None,
        "repealed_date": repealed.isoformat() if repealed else None,
        "published_at": str(record.get("published_at") or effective.isoformat()),
        "acquired_at": acquired.isoformat(),
        "media_type": str(record.get("media_type") or "text/plain"),
        "official": bool(record.get("official", source_type == "OFFICIAL")),
        "test_fixture": bool(record.get("test_fixture", False)),
        "content": text,
        "spans": section_text(text),
    }
    normalized["content_fingerprint"] = fingerprint(text)
    normalized["record_fingerprint"] = fingerprint(normalized)
    return normalized


def validate_coverage_register(entries: Iterable[Mapping[str, Any]], source_ids: Iterable[str]) -> List[Dict[str, Any]]:
    source_set = set(source_ids)
    result: List[Dict[str, Any]] = []
    topics = set()
    for index, raw in enumerate(entries):
        entry = copy.deepcopy(dict(raw))
        topic = str(require(entry.get("topic"), "coverage[%d].topic" % index))
        if topic in topics:
            raise TruthError("duplicate coverage topic %s" % topic)
        topics.add(topic)
        status = str(require(entry.get("status"), "coverage[%d].status" % index)).upper()
        if status not in COVERAGE_STATUSES:
            raise TruthError("unsupported coverage status %s" % status)
        evidence = list(entry.get("source_ids", []))
        missing = sorted(set(evidence) - source_set)
        if missing:
            raise TruthError("coverage topic %s references missing sources: %s" % (topic, ", ".join(missing)))
        if status == "COVERED" and not evidence:
            raise TruthError("covered topic %s needs source evidence" % topic)
        if status != "COVERED" and not str(entry.get("reason") or "").strip():
            raise TruthError("%s topic %s needs an explicit reason" % (status, topic))
        result.append({"topic": topic, "status": status, "source_ids": evidence, "reason": entry.get("reason")})
    if not result:
        raise TruthError("coverage register cannot be empty")
    return sorted(result, key=lambda item: item["topic"])


def validate_parse_metrics(metrics: Mapping[str, Any]) -> Dict[str, Any]:
    sample_size = int(metrics.get("sample_size", 0))
    precision = float(metrics.get("precision", -1))
    recall = float(metrics.get("recall", -1))
    if sample_size < 1 or not (0 <= precision <= 1) or not (0 <= recall <= 1):
        raise TruthError("parse metrics require sample_size > 0 and precision/recall in [0,1]")
    minimum = float(metrics.get("minimum", 0.95))
    return {
        "sample_size": sample_size,
        "precision": precision,
        "recall": recall,
        "minimum": minimum,
        "passed": precision >= minimum and recall >= minimum,
    }


class AuthoritySnapshotBuilder:
    def __init__(self, ocr: Optional[OcrExtractor] = None):
        self.ocr = ocr

    def build(
        self,
        records: Iterable[Mapping[str, Any]],
        as_of: date,
        coverage: Iterable[Mapping[str, Any]],
        parse_metrics: Mapping[str, Any],
        freshness_sla_days: int,
        scope_binding: str,
    ) -> Dict[str, Any]:
        normalized = [normalize_source(item, ocr=self.ocr) for item in records]
        documents = unique_ids(normalized, "source_id", "sources")
        if freshness_sla_days < 0:
            raise TruthError("freshness_sla_days cannot be negative")
        active_ids: List[str] = []
        freshness: List[Dict[str, Any]] = []
        for source_id, document in documents.items():
            effective = iso_date(document["effective_date"], "%s.effective_date" % source_id)
            repealed = optional_date(document.get("repealed_date"), "%s.repealed_date" % source_id)
            acquired = iso_datetime(document["acquired_at"], "%s.acquired_at" % source_id).date()
            age = (as_of - acquired).days
            status = "NOT_YET_EFFECTIVE" if effective > as_of else "REPEALED" if repealed and repealed <= as_of else "EFFECTIVE"
            document["as_of_status"] = status
            if status == "EFFECTIVE":
                active_ids.append(source_id)
            exempt = document["source_type"] == "SYNTHETIC"
            freshness.append(
                {
                    "source_id": source_id,
                    "age_days": age,
                    "sla_days": freshness_sla_days,
                    "exempt_synthetic": exempt,
                    "passed": exempt or (0 <= age <= freshness_sla_days),
                }
            )
        coverage_register = validate_coverage_register(coverage, documents)
        parsing = validate_parse_metrics(parse_metrics)
        body = {
            "artifact_type": "AuthoritySnapshot",
            "schema_version": 1,
            "as_of": as_of.isoformat(),
            "scope_binding": str(require(scope_binding, "scope_binding")),
            "documents": sorted(documents.values(), key=lambda item: item["source_id"]),
            "active_source_ids": sorted(active_ids),
            "coverage_register": coverage_register,
            "freshness": freshness,
            "parse_quality": parsing,
            "test_fixture": any(item["test_fixture"] for item in documents.values()),
        }
        body["gates"] = {
            "freshness_sla_met": all(item["passed"] for item in freshness),
            "parse_quality_met": parsing["passed"],
            "coverage_explicit": bool(coverage_register),
            "content_hashed": all(item.get("content_fingerprint") for item in documents.values()),
        }
        body["ready"] = all(body["gates"].values())
        body["reproducible"] = True
        set_fingerprint(body, "snapshot_id")
        return body


class SnapshotStore:
    """Append-only file store for immutable snapshot replay."""

    def __init__(self, root: str):
        self.root = Path(root)

    def append(self, snapshot: Mapping[str, Any]) -> Path:
        snapshot_id = str(require(snapshot.get("snapshot_id"), "snapshot.snapshot_id"))
        if not verify_fingerprint(dict(snapshot), "snapshot_id"):
            raise TruthError("snapshot fingerprint mismatch")
        destination = self.root / (snapshot_id.replace(":", "-") + ".json")
        if destination.exists():
            raise TruthError("snapshot %s already exists; immutable snapshots cannot be overwritten" % snapshot_id)
        atomic_write_json(str(destination), dict(snapshot))
        return destination

    def replay(self, snapshots: Iterable[Mapping[str, Any]], as_of: date) -> Dict[str, Any]:
        eligible = [item for item in snapshots if iso_date(item.get("as_of"), "snapshot.as_of") <= as_of]
        if not eligible:
            raise TruthError("no authority snapshot exists at or before %s" % as_of.isoformat())
        selected = max(eligible, key=lambda item: (item["as_of"], item["snapshot_id"]))
        if not verify_fingerprint(dict(selected), "snapshot_id"):
            raise TruthError("stored snapshot failed integrity verification")
        return copy.deepcopy(dict(selected))
