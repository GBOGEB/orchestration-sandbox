"""gg_Engine W10: source-bound semantic edge admission and worker DAG gate.

Standard-library only. This validates an adapter's *claims*, not its parsing
correctness. No test result grants engineering acceptance authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

CONTRACT_VERSION = "gg-semantic-1.0"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DIRECTIONS = {"UNKNOWN", "SOURCE_TO_TARGET", "TARGET_TO_SOURCE", "BIDIRECTIONAL"}
STATES = {"UNRESOLVED", "CANDIDATE", "GOLDEN"}
DIRECTION_PROOFS = {"SVG_MARKER_START", "SVG_MARKER_END", "PPTX_HEAD_END", "PPTX_TAIL_END", "OWNER_VERIFIED_DIRECTION"}
WEAK_PROOFS = {"GEOMETRY_ONLY", "NEIGHBOR_ORDER", "PROXIMITY", "COLOR_ONLY"}
RELATIONSHIPS = {"UNKNOWN", "FLOW", "SIGNAL", "INTERLOCK", "ELECTRICAL", "THERMAL", "TOPOLOGY"}


@dataclass(frozen=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def _sha_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def _member(value: Any, allowed: Any) -> bool:
    """Set membership that fails closed on unhashable JSON values (lists, objects)."""
    return isinstance(value, str) and value in allowed


def validate_manifest(doc: Mapping[str, Any]) -> List[Finding]:
    """Fail closed on unsupported graph claims, keep unresolved observations."""
    found: List[Finding] = []

    def problem(code: str, loc: str, msg: str) -> None:
        found.append(Finding(code, loc, msg))

    if doc.get("contract_version") != CONTRACT_VERSION:
        problem("K01_CONTRACT", "$", "Unknown or missing semantic contract version")
    src = doc.get("source")
    if not isinstance(src, dict):
        problem("K02_SOURCE", "source", "Source provenance must be an object")
        src = {}
    source_sha = src.get("sha256")
    if not _sha_ok(source_sha):
        problem("K02_SOURCE", "source.sha256", "SHA-256 must be 64 lowercase hex characters")
    if not src.get("locator") or not isinstance(src.get("locator"), str):
        problem("K02_SOURCE", "source.locator", "Immutable or revision-specific source locator missing")
    if not src.get("producer"):
        problem("K02_SOURCE", "source.producer", "Named producer adapter missing")

    nodes = doc.get("nodes", [])
    edges = doc.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return found + [Finding("K03_TYPE", "$", "Nodes and edges must be arrays")]

    node_ids = set()
    for i, node in enumerate(nodes):
        loc = f"nodes[{i}]"
        if not isinstance(node, dict):
            problem("K03_NODE", loc, "Node must be an object")
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid.strip():
            problem("K03_NODE", loc, "Stable node id missing")
        elif nid in node_ids:
            problem("K04_DUPLICATE_NODE", loc, f"Duplicate node id: {nid}")
        else:
            node_ids.add(nid)
        if not isinstance(node.get("source_object_id"), str) or not node.get("source_object_id"):
            problem("K05_LOCATOR", loc, "Native/source-local object id missing")

    edge_ids = set()
    for i, edge in enumerate(edges):
        loc = f"edges[{i}]"
        if not isinstance(edge, dict):
            problem("K06_EDGE", loc, "Edge must be an object")
            continue
        eid = edge.get("id")
        if not isinstance(eid, str) or not eid:
            problem("K06_EDGE", loc, "Edge id missing")
        elif eid in edge_ids:
            problem("K06_DUPLICATE_EDGE", loc, f"Duplicate edge id: {eid}")
        else:
            edge_ids.add(eid)
        u, v = edge.get("source_id"), edge.get("target_id")
        if not (_member(u, node_ids) and _member(v, node_ids)):
            problem("K07_ENDPOINTS", loc, "Both endpoints must refer to existing nodes")
        if u == v and u is not None:
            problem("K07_SELF_LOOP", loc, "Self-loop requires separate explicit-review contract")
        state = edge.get("state")
        if not _member(state, STATES):
            problem("K08_STATE", loc, "Unknown edge review state")
        direction = edge.get("direction")
        if not _member(direction, DIRECTIONS):
            problem("K09_DIRECTION", loc, "Invalid direction")
        rel = edge.get("relationship")
        if not _member(rel, RELATIONSHIPS):
            problem("K10_RELATIONSHIP", loc, "Unsupported relationship taxonomy")
        evidence = edge.get("evidence", [])
        if not isinstance(evidence, list):
            problem("K11_EVIDENCE", loc, "Evidence must be a list")
            evidence = []
        types = {x["type"] for x in evidence if isinstance(x, dict) and isinstance(x.get("type"), str)}
        if not evidence and state != "UNRESOLVED":
            problem("K11_EVIDENCE", loc, "Candidate or golden edge requires evidence")
        for j, ev in enumerate(evidence):
            if not isinstance(ev, dict) or not ev.get("locator") or not ev.get("type"):
                problem("K11_EVIDENCE", f"{loc}.evidence[{j}]", "Typed evidence with locator required")
        if direction != "UNKNOWN" and not (types & DIRECTION_PROOFS):
            problem("K12_DIRECTION_PROOF", loc, "Direction claimed without marker, OOXML arrowhead or owner confirmation")
        if direction != "UNKNOWN" and not edge.get("explicit_endpoints", False):
            problem("K13_ANCHOR", loc, "Directional edge requires explicit anchored endpoints")
        if state == "UNRESOLVED":
            if not edge.get("unresolved_reason"):
                problem("K14_UNRESOLVED", loc, "Unresolved item must have a reason")
            if direction != "UNKNOWN":
                problem("K14_UNRESOLVED", loc, "Unresolved edge must not assert an authoritative direction")
        if rel != "UNKNOWN" and state != "UNRESOLVED":
            legend = edge.get("legend", {})
            if not isinstance(legend, dict) or not legend.get("verified") or not legend.get("locator"):
                problem("K15_LEGEND", loc, "Engineering relationship requires verified source legend")
        if state == "GOLDEN":
            approval = edge.get("approval", {})
            if not isinstance(approval, dict) or not all(approval.get(k) for k in ("decision_id", "authority", "approved_at")):
                problem("K16_AUTHORITY", loc, "Golden thread requires explicit owner decision, authority and date")
            elif approval.get("source_sha256") != source_sha:
                problem("K17_STALE_APPROVAL", loc, "Approval is not bound to this source SHA")
    return found


def receipt(doc: Any) -> Dict[str, Any]:
    """Always return a receipt; malformed input yields FAIL_CLOSED, never a traceback."""
    if isinstance(doc, Mapping):
        findings = validate_manifest(doc)
        nodes, edges, src = doc.get("nodes", []), doc.get("edges", []), doc.get("source")
    else:
        findings = [Finding("K03_TYPE", "$", "Manifest must be a JSON object")]
        nodes, edges, src = [], [], None
    # Count only validated arrays; K03_TYPE already reports any other value.
    nodes = nodes if isinstance(nodes, list) else []
    edges = edges if isinstance(edges, list) else []
    tally = Counter(e["state"] for e in edges if isinstance(e, dict) and isinstance(e.get("state"), str))
    normalized = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "contract_version": CONTRACT_VERSION,
        "input_digest_sha256": hashlib.sha256(normalized).hexdigest(),
        "source_sha256": src.get("sha256") if isinstance(src, dict) else None,
        "status": "PASS_CONTRACT_ONLY" if not findings else "FAIL_CLOSED",
        "counts": {"nodes": len(nodes), "edges": len(edges),
                   "candidate": tally["CANDIDATE"], "golden": tally["GOLDEN"],
                   "unresolved": tally["UNRESOLVED"], "findings": len(findings)},
        "findings": [f.as_dict() for f in findings],
        "disclaimer": "Contract PASS does not authorize engineering semantics, rendering fidelity, or merge admission",
    }


def validate_worker_dag(jobs: Sequence[Mapping[str, Any]]) -> List[Finding]:
    """Kahn's algorithm; separately validates dispatch DAG, not engineering flow."""
    out: List[Finding] = []
    seen = set()
    for i, job in enumerate(jobs):
        jid = job.get("id")
        if not isinstance(jid, str) or not jid or jid in seen:
            out.append(Finding("K18_JOB_ID", f"jobs[{i}]", "Job ID missing or duplicated"))
        seen.add(jid)
    graph = {j.get("id"): set(j.get("depends_on", [])) for j in jobs if j.get("id")}
    for jid, deps in graph.items():
        for dep in deps:
            if dep not in graph:
                out.append(Finding("K19_MISSING_DEP", jid, f"Missing dependency: {dep}"))
    if out:
        return out
    indegree = {jid: len(deps) for jid, deps in graph.items()}
    ready = sorted(jid for jid, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        jid = ready.pop(0)
        visited += 1
        for dependent in sorted(graph):
            if jid in graph[dependent]:
                graph[dependent].remove(jid)
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        ready.sort()
    if visited != len(graph):
        out.append(Finding("K20_CYCLE", "jobs", "Execution DAG has a cycle (blocked by Kahn)"))
    return out


def from_path(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="gg_Engine W10 semantic contract gate")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--jobs", type=Path)
    args = parser.parse_args()
    doc = from_path(args.manifest)
    report = receipt(doc)
    if args.jobs is not None:
        errs = validate_worker_dag(from_path(args.jobs)["jobs"])
        report["worker_dag"] = {"status": "PASS" if not errs else "FAIL_CLOSED", "findings": [e.as_dict() for e in errs]}
        if errs:
            report["status"] = "FAIL_CLOSED"
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return int(report["status"] != "PASS_CONTRACT_ONLY")


if __name__ == "__main__":
    raise SystemExit(main())
