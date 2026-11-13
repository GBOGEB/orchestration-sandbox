"""Format-neutral helpers shared by the W11 SVG and PPTX native adapters.

Nothing here decides engineering meaning. It hashes inputs, refuses unsafe XML,
applies an owner-held legend record only when it is verified and bound to the
exact source bytes, orients an edge only from arrowhead evidence, and assembles
a W10 ``gg-semantic-1.0`` manifest. Adapters never emit GOLDEN.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from schema_pin import assert_schema_pinned
from w10_bridge import CONTRACT_VERSION, RELATIONSHIPS, make_cache_key, receipt

LEGEND_RECORD_VERSION = "gg-legend-0.1"
NO_LEGEND_SHA256 = hashlib.sha256(b"").hexdigest()
NODE_POLICY = "CONNECTOR_ENDPOINTS_ONLY"
QUALIFICATION = {
    "dow_independent_review": "NOT_RUN",
    "keb_receipt": "NOT_ISSUED",
    "owner_acceptance": "HOLD",
}
DISCLAIMER = (
    "Native adapter output is a CANDIDATE graph claim read from native objects. It is not "
    "engineering acceptance, DOW qualification, a KEB receipt or owner approval, and it never emits GOLDEN."
)
_DTD = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)


class AdapterInputError(ValueError):
    """The input was refused before any graph claim was produced (fail closed)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def parse_xml(data: bytes, where: str) -> ET.Element:
    """Parse UTF-8/ASCII XML that declares no DTD; entity expansion is refused, never trusted."""
    if b"\x00" in data:
        raise AdapterInputError(f"{where}: only UTF-8 or ASCII-compatible XML is read")
    if _DTD.search(data):
        raise AdapterInputError(f"{where}: DTD or entity declaration refused")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise AdapterInputError(f"{where}: not well-formed XML ({exc})") from exc


def local_name(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def finding(code: str, location: str, message: str) -> Dict[str, str]:
    return {"code": code, "location": location, "message": message}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AdapterInputError(f"legend record {path.name}: unreadable JSON ({exc.__class__.__name__})") from exc


def legend_status(record: Any, *, fmt: str, source_sha256: str, native_ids: Iterable[str]) -> Dict[str, Any]:
    """Apply an owner-held legend record only if it is versioned, verified and bound to this source.

    The adapter checks the record's fields; it cannot authenticate who verified it.
    That confirmation stays with the owner.
    """
    if record is None:
        return {"status": "ABSENT", "sha256": NO_LEGEND_SHA256, "applied": False, "locator": None,
                "rules": [], "arrowhead_markers": [], "findings": []}
    sha = sha256_bytes(canonical_json(record))
    problems: List[Dict[str, str]] = []

    def bad(code: str, message: str) -> None:
        problems.append(finding(code, "legend", message))

    if not isinstance(record, Mapping):
        bad("L01_VERSION", "Legend record must be a JSON object")
        record = {}
    if record.get("legend_record_version") != LEGEND_RECORD_VERSION:
        bad("L01_VERSION", f"Legend record version must be {LEGEND_RECORD_VERSION}")
    if record.get("format") != fmt:
        bad("L02_FORMAT", f"Legend record format must be {fmt}")
    if record.get("source_sha256") != source_sha256:
        bad("L03_STALE_LEGEND", "Legend record is not bound to this source SHA-256")
    owner_fields = ("verified_by", "decision_id", "verified_at")
    if record.get("verified") is not True or not all(isinstance(record.get(k), str) and record.get(k) for k in owner_fields):
        bad("L04_UNVERIFIED", "Legend record lacks owner verification (verified, verified_by, decision_id, verified_at)")
    legend_object = record.get("legend_object_id")
    if legend_object not in set(native_ids):
        bad("L05_LEGEND_OBJECT", "Legend object id is not a unique native object in this source")
    rules: List[Dict[str, Any]] = []
    raw_rules = record.get("relationships", [])
    if not isinstance(raw_rules, list):
        bad("L06_RULE", "relationships must be a list")
        raw_rules = []
    allowed = set(RELATIONSHIPS) - {"UNKNOWN"}
    for i, rule in enumerate(raw_rules):
        match = rule.get("match") if isinstance(rule, Mapping) else None
        ok = (isinstance(match, Mapping) and bool(match)
              and all(isinstance(k, str) and isinstance(v, str) for k, v in match.items())
              and rule.get("relationship") in allowed)
        if ok:
            rules.append({"match": dict(match), "relationship": rule["relationship"]})
        else:
            bad("L06_RULE", f"relationships[{i}] needs a non-empty string match and a known relationship")
    markers = record.get("arrowhead_markers", [])
    if not isinstance(markers, list) or not all(isinstance(m, str) and m for m in markers):
        bad("L07_MARKERS", "arrowhead_markers must be a list of marker ids")
        markers = []
    if fmt != "svg" and markers:
        bad("L07_MARKERS", "arrowhead_markers applies to SVG only; PPTX arrowheads are native line-end types")
    applied = not problems
    return {
        "status": "APPLIED" if applied else "REJECTED",
        "sha256": sha,
        "applied": applied,
        "locator": legend_object if applied else None,
        "rules": rules if applied else [],
        "arrowhead_markers": sorted(set(markers)) if applied else [],
        "findings": problems,
    }


def match_relationship(legend: Mapping[str, Any], signature: Mapping[str, str]) -> Tuple[str, Optional[str]]:
    """Return (relationship, ambiguity reason). No applied legend means UNKNOWN, never a guess."""
    if not legend.get("applied"):
        return "UNKNOWN", None
    hits = sorted({r["relationship"] for r in legend["rules"]
                   if all(signature.get(k) == v for k, v in r["match"].items())})
    if not hits:
        return "UNKNOWN", None
    if len(hits) > 1:
        return "UNKNOWN", "legend rules disagree for this line style: " + ", ".join(hits)
    return hits[0], None


def build_edge(*, edge_id: str, connector_id: str, start: str, end: str,
               start_arrow: Optional[Dict[str, Any]], end_arrow: Optional[Dict[str, Any]],
               evidence: Sequence[Dict[str, Any]], relationship: str, legend: Mapping[str, Any],
               unresolved: Sequence[str], native: Mapping[str, Any]) -> Dict[str, Any]:
    """Build one W10 edge from a connector bound at both ends.

    ``start``/``end`` are node ids in drawing order. Only arrowhead evidence
    orients the edge. With no arrowhead, or with both, the endpoints are sorted
    so drawing order cannot leak in as a direction claim.
    """
    proof = [e for e in (start_arrow, end_arrow) if e]
    if unresolved:
        (a, b), direction, orientation = sorted((start, end)), "UNKNOWN", "UNORIENTED_SORTED"
    elif start_arrow and end_arrow:
        (a, b), direction, orientation = sorted((start, end)), "BIDIRECTIONAL", "UNORIENTED_SORTED"
    elif end_arrow:
        (a, b), direction, orientation = (start, end), "SOURCE_TO_TARGET", "AS_DRAWN"
    elif start_arrow:
        (a, b), direction, orientation = (end, start), "SOURCE_TO_TARGET", "REVERSED_FROM_DRAWING"
    else:
        (a, b), direction, orientation = sorted((start, end)), "UNKNOWN", "UNORIENTED_SORTED"
    state = "UNRESOLVED" if unresolved else "CANDIDATE"
    rel = "UNKNOWN" if unresolved else relationship
    edge: Dict[str, Any] = {
        "id": edge_id,
        "source_id": a,
        "target_id": b,
        "state": state,
        "direction": direction,
        "relationship": rel,
        "explicit_endpoints": True,
        "evidence": sorted([dict(e) for e in list(evidence) + proof], key=lambda e: (e["type"], e["locator"])),
        "native": dict(native, connector=connector_id, orientation=orientation),
    }
    if unresolved:
        edge["unresolved_reason"] = "; ".join(unresolved)
    if rel != "UNKNOWN":
        edge["legend"] = {"verified": True, "locator": legend["locator"], "record_sha256": legend["sha256"]}
    return edge


def duplicate_findings(items: Iterable[Mapping[str, Any]], code: str, what: str) -> List[Dict[str, str]]:
    seen: Dict[str, int] = {}
    for item in items:
        seen[item["id"]] = seen.get(item["id"], 0) + 1
    return [finding(code, ident, f"{count} {what} share this id; the W10 contract will fail closed")
            for ident, count in sorted(seen.items()) if count > 1]


def assemble(*, fmt: str, adapter_name: str, adapter_version: str, source_sha256: str, locator: str,
             nodes: Iterable[Dict[str, Any]], edges: Iterable[Dict[str, Any]],
             quarantine: Iterable[Dict[str, Any]], legend: Mapping[str, Any],
             findings: Iterable[Dict[str, str]], native: Mapping[str, Any]) -> Dict[str, Any]:
    schema_sha = assert_schema_pinned()
    producer = f"{adapter_name}/{adapter_version}"
    node_list = sorted(nodes, key=lambda n: (n["id"], n["source_object_id"]))
    edge_list = sorted(edges, key=lambda e: (e["id"], e["native"]["connector"]))
    all_findings = list(findings)
    all_findings += duplicate_findings(node_list, "A02_DUPLICATE_TAG", "nodes")
    all_findings += duplicate_findings(edge_list, "A02_DUPLICATE_TAG", "edges")
    return {
        "contract_version": CONTRACT_VERSION,
        "source": {"sha256": source_sha256, "locator": locator, "producer": producer},
        "nodes": node_list,
        "edges": edge_list,
        "quarantine": sorted(quarantine, key=lambda q: (q["source_object_id"], q["reason"])),
        "adapter": {
            "format": fmt,
            "producer": producer,
            "schema_sha256": schema_sha,
            "cache_key": make_cache_key(source_sha256, producer, legend["sha256"], CONTRACT_VERSION),
            "legend": {"status": legend["status"], "sha256": legend["sha256"], "findings": legend["findings"]},
            "findings": sorted(all_findings, key=lambda f: (f["code"], f["location"], f["message"])),
            "native": dict(native),
            "node_policy": NODE_POLICY,
            "qualification": dict(QUALIFICATION),
            "disclaimer": DISCLAIMER,
        },
    }


def emit(doc: Mapping[str, Any], out: Optional[Path], contract_receipt: Optional[Path]) -> int:
    """Write the manifest; optionally run the unchanged W10 contract gate on it."""
    payload = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if out is None:
        sys.stdout.write(payload)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    if contract_receipt is None:
        return 0
    report = receipt(doc)
    contract_receipt.parent.mkdir(parents=True, exist_ok=True)
    contract_receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return int(report["status"] != "PASS_CONTRACT_ONLY")


def refuse(exc: AdapterInputError) -> int:
    sys.stderr.write(json.dumps({"status": "INPUT_REFUSED", "error": str(exc)}, sort_keys=True) + "\n")
    return 2
