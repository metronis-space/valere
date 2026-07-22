"""C3: deterministic document/VDR rendering with field provenance."""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence
from xml.sax.saxutils import escape

from utils.artifacts import atomic_write_json
from utils.errors import MatterError


RENDERER_ID = "c3-stdlib-ooxml-pdf-v1"
MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf",
    ".eml": "message/rfc822",
    ".json": "application/json",
    ".txt": "text/plain",
}
FILES = {
    "contracts/material-services-agreement.docx": "CONTRACT",
    "contracts/amendment-001.docx": "AMENDMENT",
    "corporate/board-minutes.pdf": "BOARD_MATERIAL",
    "financial/capitalization-funds-flow.xlsx": "SPREADSHEET",
    "correspondence/consent-qa.eml": "CORRESPONDENCE",
    "consents/consent-register.txt": "CONSENT_NOTICE",
    "disclosure/disclosure-schedule.docx": "DISCLOSURE_SCHEDULE",
    "compliance/policy-incident-log.json": "POLICY_LOG",
    "regulatory/litigation-regulatory.txt": "REGULATORY_RECORD",
    "noise/office-notice.txt": "DISTRACTOR",
    "vdr-index.json": "VDR_INDEX",
}


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _zip_bytes(members: Mapping[str, str]) -> bytes:
    descriptor, temporary = tempfile.mkstemp(suffix=".zip")
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(members):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, members[name].encode("utf-8"))
        return Path(temporary).read_bytes()
    finally:
        Path(temporary).unlink(missing_ok=True)


def _docx_bytes(paragraphs: Sequence[tuple[str, str]]) -> bytes:
    body = []
    for style, text in paragraphs:
        ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style if style else ""
        body.append(
            '<w:p>%s<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (ppr, escape(text))
        )
    body.append(
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>%s</w:body></w:document>' % "".join(body)
    )
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="240"/><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:color w:val="0B2545"/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="2E74B5"/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Signature"><w:name w:val="Signature"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr><w:rPr><w:i/></w:rPr></w:style>
</w:styles>"""
    return _zip_bytes(
        {
            "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>""",
            "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""",
            "word/_rels/document.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>""",
            "word/document.xml": document,
            "word/styles.xml": styles,
        }
    )


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell_xml(reference: str, cell: Any) -> str:
    style = 0
    formula = None
    value = cell
    if isinstance(cell, dict):
        value, style, formula = cell.get("value"), cell.get("style", 0), cell.get("formula")
    attrs = ' r="%s" s="%s"' % (reference, style)
    if formula:
        return '<c%s><f>%s</f><v>%s</v></c>' % (attrs, escape(formula), value)
    if isinstance(value, bool):
        return '<c%s t="b"><v>%d</v></c>' % (attrs, value)
    if isinstance(value, (int, float)):
        return '<c%s><v>%s</v></c>' % (attrs, value)
    return '<c%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (attrs, escape(str(value)))


def _xlsx_bytes(sheets: Mapping[str, Sequence[Sequence[Any]]]) -> bytes:
    members: Dict[str, str] = {}
    workbook_sheets = []
    relationships = []
    overrides = []
    for sheet_index, (name, rows) in enumerate(sheets.items(), 1):
        workbook_sheets.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(name), sheet_index, sheet_index))
        relationships.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (sheet_index, sheet_index))
        overrides.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % sheet_index)
        widths = [min(32, max(12, max((len(str(row[column])) for row in rows if column < len(row)), default=12) + 2)) for column in range(max(map(len, rows)))]
        columns = "".join('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i, i, width) for i, width in enumerate(widths, 1))
        row_xml = []
        for row_index, row in enumerate(rows, 1):
            cells = "".join(_cell_xml("%s%d" % (_column_name(column), row_index), cell) for column, cell in enumerate(row, 1))
            row_xml.append('<row r="%d">%s</row>' % (row_index, cells))
        members["xl/worksheets/sheet%d.xml" % sheet_index] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            '<cols>%s</cols><sheetData>%s</sheetData></worksheet>' % (columns, "".join(row_xml))
        )
    style_id = len(sheets) + 1
    relationships.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % style_id)
    members.update(
        {
            "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>%s</Types>' % "".join(overrides),
            "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>%s</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>' % "".join(workbook_sheets),
            "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % "".join(relationships),
            "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0;[Red](&quot;$&quot;#,##0);-"/></numFmts><fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font><font><color rgb="FF0000FF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B2545"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="2"><border/><border><bottom style="thin"><color rgb="FF8090A0"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>""",
        }
    )
    return _zip_bytes(members)


def _pdf_bytes(lines: Sequence[str]) -> bytes:
    def literal(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 18 Tf", "72 742 Td", "(%s) Tj" % literal(lines[0]), "/F1 11 Tf"]
    for line in lines[1:]:
        commands.extend(["0 -24 Td", "(%s) Tj" % literal(line)])
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(b"%d 0 obj\n" % index + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets[1:]:
        output.extend(b"%010d 00000 n \n" % offset)
    output.extend(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return bytes(output)


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def render_document_world(world: Mapping[str, Any], output_dir: str) -> Dict[str, Any]:
    """Render the bounded Phase 3 VDR; refuse unknown stale files."""

    root = Path(output_dir)
    existing = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()} if root.exists() else set()
    if existing - set(FILES):
        raise MatterError("render target contains unknown files: %s" % ", ".join(sorted(existing - set(FILES))))
    root.mkdir(parents=True, exist_ok=True)
    entities = {item["entity_id"]: item["name"] for item in world["entities"]}
    contract = world["contracts"][0]
    amendment = contract["amendments"][0]
    consent = world["consents"][0]
    transaction = world["transaction"]
    cap = world["capitalization"][0]
    ownership = next(item for item in world["ownership"] if item["owner_id"] == "seller")

    contract_paragraphs = [
        ("Title", "MATERIAL SERVICES AGREEMENT"),
        ("", "Document ID: %s | Version: 1 | Status: CURRENT" % contract["contract_id"]),
        ("Heading1", "Parties and Commercial Terms"),
        ("", "Target Party: %s" % entities["target"]),
        ("", "Counterparty: %s" % entities["counterparty"]),
        ("", "Annual Contract Value: USD %d" % contract["annual_value"]["amount"]),
        ("Heading1", "Defined Terms"),
        ("", 'Defined Term: "Change of Control" means a merger or transfer of control.'),
        ("Heading1", "Section 1.1 Change of Control"),
        ("", "A merger or transfer of control requires the Counterparty's prior written consent. See Section 2.1."),
        ("Heading1", "Section 2.1 Consent Evidence"),
        ("", "Consent must be recorded before Closing unless the requirement is expressly waived."),
        ("Signature", "Signed for Synthetic Target Inc.: /s/ Alex Target"),
        ("Signature", "Signed for Synthetic SaaS Vendor Inc.: /s/ Casey Counterparty"),
    ]
    amendment_paragraphs = [
        ("Title", "AMENDMENT NO. 1"),
        ("", "Document ID: %s | Amends: %s | Status: CURRENT" % (amendment["amendment_id"], contract["contract_id"])),
        ("", "Effective Date: %s" % amendment["effective_date"]),
        ("", "Order: %d" % amendment["order"]),
        ("Heading1", "Operative Terms"),
        ("", "Section 1.1 and Section 2.1 of contract-001 remain unchanged and in full force."),
        ("Signature", "Signed for Synthetic Target Inc.: /s/ Alex Target"),
        ("Signature", "Signed for Synthetic SaaS Vendor Inc.: /s/ Casey Counterparty"),
    ]
    disclosure_paragraphs = [
        ("Title", "DISCLOSURE SCHEDULE"),
        ("", "Document ID: disclosure-schedule-001 | Status: CURRENT"),
        ("Heading1", "Assets and Obligations"),
        ("", "Software Asset Value: USD %d" % world["assets"][0]["value"]["amount"]),
        ("", "Accounts Payable Liability: USD %d" % world["liabilities"][0]["value"]["amount"]),
        ("", "Debt Principal: USD %d" % world["debts"][0]["principal"]["amount"]),
        ("", "Lien Status: %s" % world["liens"][0]["status"]),
        ("Heading1", "Personnel, Litigation and Regulation"),
        ("", "Employee employee-001 Status: %s" % world["employees"][0]["status"]),
        ("", "Litigation Status: %s" % world["litigation"][0]["status"]),
        ("", "Regulatory Status: %s" % world["regulatory"][0]["status"]),
    ]
    _atomic_bytes(root / "contracts/material-services-agreement.docx", _docx_bytes(contract_paragraphs))
    _atomic_bytes(root / "contracts/amendment-001.docx", _docx_bytes(amendment_paragraphs))
    _atomic_bytes(root / "disclosure/disclosure-schedule.docx", _docx_bytes(disclosure_paragraphs))

    sheets = {
        "Capitalization": [
            [{"value": "Entity", "style": 1}, {"value": "Security", "style": 1}, {"value": "Units", "style": 1}, {"value": "Value USD", "style": 1}],
            [cap["entity_id"], cap["security"], {"value": cap["units"], "style": 3}, {"value": cap["value"], "style": 2}],
        ],
        "Ownership": [
            [{"value": "Owner", "style": 1}, {"value": "Owned Entity", "style": 1}, {"value": "Percentage", "style": 1}],
            [ownership["owner_id"], ownership["owned_id"], ownership["percentage"]],
        ],
        "Funds Flow": [
            [{"value": "Item", "style": 1}, {"value": "Amount USD", "style": 1}],
            ["Enterprise Value", {"value": cap["value"], "style": 2}],
            ["Less: Debt", {"value": world["debts"][0]["principal"]["amount"], "style": 2}],
            ["Net Consideration", {"value": cap["value"] - world["debts"][0]["principal"]["amount"], "style": 4, "formula": "B2-B3"}],
        ],
        "Financials": [
            [{"value": "Metric", "style": 1}, {"value": "Amount USD", "style": 1}],
            ["Software Assets", {"value": world["assets"][0]["value"]["amount"], "style": 2}],
            ["Accounts Payable", {"value": world["liabilities"][0]["value"]["amount"], "style": 2}],
            ["Debt Principal", {"value": world["debts"][0]["principal"]["amount"], "style": 2}],
            ["Annual Contract Value", {"value": contract["annual_value"]["amount"], "style": 2}],
        ],
    }
    _atomic_bytes(root / "financial/capitalization-funds-flow.xlsx", _xlsx_bytes(sheets))

    board_lines = [
        "BOARD OF DIRECTORS - WRITTEN CONSENT",
        "Document ID: board-consent-001",
        "Target: %s" % entities["target"],
        "Transaction Structure: %s" % transaction["structure"],
        "Signing Date: %s" % transaction["timeline"]["signing"],
        "Closing Date: %s" % transaction["timeline"]["closing"],
        "RESOLVED: The merger is approved, subject to required third-party consents.",
        "Authorized Signatory: /s/ Jordan Director",
        "Status: CURRENT",
    ]
    _atomic_bytes(root / "corporate/board-minutes.pdf", _pdf_bytes(board_lines))

    message = EmailMessage()
    message["From"] = "seller@example.invalid"
    message["To"] = "buyer@example.invalid"
    message["Subject"] = "Project Phase 3 - contract-001 consent Q&A"
    message["Message-ID"] = "<phase3-consent-qa@example.invalid>"
    message.set_content(
        "Contract ID: contract-001\n"
        "Question: Has the change-of-control consent been obtained?\n"
        "Answer: No executed consent has been received.\n"
        "Formal Notice Status: NOT_SENT\n"
        "This correspondence is a status response, not an executed consent.\n"
    )
    _atomic_bytes(root / "correspondence/consent-qa.eml", message.as_bytes())

    consent_lines = [
        "CONSENT REGISTER",
        "Contract ID: contract-001",
        "Consent Status: %s" % consent["state"],
        "Notice Status: %s" % consent["notice_state"],
        "Approval Status: %s" % consent["approval_state"],
        "Waiver Status: UNKNOWN" if consent["waived"] is None else "Waiver Status: %s" % consent["waived"],
        "Executed Consent File: UNPRODUCED",
    ]
    _atomic_bytes(root / "consents/consent-register.txt", ("\n".join(consent_lines) + "\n").encode())
    atomic_write_json(
        str(root / "compliance/policy-incident-log.json"),
        {
            "document_id": "policy-log-001",
            "classification": "SYNTHETIC",
            "personal_data": False,
            "incidents": [],
            "legal_hold": False,
            "status": "CURRENT",
        },
    )
    _atomic_bytes(
        root / "regulatory/litigation-regulatory.txt",
        (
            "REGULATORY AND LITIGATION RECORD\n"
            "Entity ID: target\n"
            "Litigation Status: %s\n"
            "Regulatory Status: %s\n"
            "Record Status: CURRENT\n"
        )
        .replace("%s", world["litigation"][0]["status"], 1)
        .replace("%s", world["regulatory"][0]["status"], 1)
        .encode(),
    )
    _atomic_bytes(
        root / "noise/office-notice.txt",
        b"OFFICE NOTICE\nThe synthetic office will be closed Friday at 5 PM.\nNo contract or transaction terms are stated here.\n",
    )

    indexed = []
    for relative, family in FILES.items():
        if relative == "vdr-index.json":
            continue
        path = root / relative
        indexed.append(
            {
                "path": relative,
                "family": family,
                "media_type": MEDIA_TYPES[path.suffix],
                "sha256": _hash(path),
                "size_bytes": path.stat().st_size,
                "status": "CURRENT",
            }
        )
    atomic_write_json(
        str(root / "vdr-index.json"),
        {"artifact_type": "VDRIndex", "schema_version": 1, "matter_id": world["matter"]["matter_id"], "documents": indexed},
    )

    provenance = [
        ("contract.target_party", entities["target"], "HIGH", "contracts/material-services-agreement.docx", "paragraph:3"),
        ("contract.counterparty", entities["counterparty"], "HIGH", "contracts/material-services-agreement.docx", "paragraph:4"),
        ("contract.change_control_clause", True, "CRITICAL", "contracts/material-services-agreement.docx", "paragraph:9"),
        ("contract.consent_required", True, "CRITICAL", "contracts/material-services-agreement.docx", "paragraph:9"),
        ("contract.annual_value_usd", contract["annual_value"]["amount"], "HIGH", "contracts/material-services-agreement.docx", "paragraph:5"),
        ("contract.amendment.order", amendment["order"], "HIGH", "contracts/amendment-001.docx", "paragraph:3"),
        ("contract.amendment.effective_date", amendment["effective_date"], "HIGH", "contracts/amendment-001.docx", "paragraph:2"),
        ("transaction.structure", transaction["structure"], "HIGH", "corporate/board-minutes.pdf", "page:1,line:4"),
        ("transaction.signing", transaction["timeline"]["signing"], "HIGH", "corporate/board-minutes.pdf", "page:1,line:5"),
        ("transaction.closing", transaction["timeline"]["closing"], "CRITICAL", "corporate/board-minutes.pdf", "page:1,line:6"),
        ("contract.consent_status", consent["state"], "CRITICAL", "consents/consent-register.txt", "line:3"),
        ("contract.notice_status", consent["notice_state"], "HIGH", "consents/consent-register.txt", "line:4"),
        ("contract.approval_status", consent["approval_state"], "HIGH", "consents/consent-register.txt", "line:5"),
        ("contract.consent_waived", consent["waived"], "HIGH", "consents/consent-register.txt", "line:6"),
        ("capitalization.units", cap["units"], "MEDIUM", "financial/capitalization-funds-flow.xlsx", "Capitalization!C2"),
        ("capitalization.value_usd", cap["value"], "MEDIUM", "financial/capitalization-funds-flow.xlsx", "Capitalization!D2"),
        ("ownership.seller_target_percentage", ownership["percentage"], "MEDIUM", "financial/capitalization-funds-flow.xlsx", "Ownership!C2"),
        ("assets.software_value_usd", world["assets"][0]["value"]["amount"], "MEDIUM", "disclosure/disclosure-schedule.docx", "paragraph:3"),
        ("liabilities.accounts_payable_usd", world["liabilities"][0]["value"]["amount"], "MEDIUM", "disclosure/disclosure-schedule.docx", "paragraph:4"),
        ("debts.principal_usd", world["debts"][0]["principal"]["amount"], "MEDIUM", "disclosure/disclosure-schedule.docx", "paragraph:5"),
        ("liens.status", world["liens"][0]["status"], "LOW", "disclosure/disclosure-schedule.docx", "paragraph:6"),
        ("employees.employee-001.status", world["employees"][0]["status"], "LOW", "disclosure/disclosure-schedule.docx", "paragraph:8"),
        ("litigation.status", world["litigation"][0]["status"], "LOW", "regulatory/litigation-regulatory.txt", "line:3"),
        ("regulatory.status", world["regulatory"][0]["status"], "MEDIUM", "regulatory/litigation-regulatory.txt", "line:4"),
    ]
    return {
        "renderer": {"engine_id": RENDERER_ID, "implementation": "matter.rendering", "uses_model": False},
        "files": indexed + [
            {
                "path": "vdr-index.json",
                "family": "VDR_INDEX",
                "media_type": "application/json",
                "sha256": _hash(root / "vdr-index.json"),
                "size_bytes": (root / "vdr-index.json").stat().st_size,
                "status": "CURRENT",
            }
        ],
        "provenance": [
            {"fact_path": fact, "expected": value, "severity": severity, "file": file, "locator": locator}
            for fact, value, severity, file, locator in provenance
        ],
        "quality": {
            "defined_term": '"Change of Control"',
            "cross_reference": "Section 2.1",
            "contract_signatures": 2,
            "amendment_signatures": 2,
            "funds_flow_formula": "B2-B3",
            "funds_flow_expected": cap["value"] - world["debts"][0]["principal"]["amount"],
        },
    }
