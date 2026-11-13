"""Cross-format semantic parity gate; native locators may differ, meaning may not."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from gg_contract import Finding, from_path, validate_manifest


def _by_id(graph: Any, field: str) -> dict:
    """Index array entries by string id. Malformed values are already K21 findings,
    so they are skipped here instead of raising (fail closed, never a traceback)."""
    value = graph.get(field, []) if isinstance(graph, Mapping) else []
    if not isinstance(value, list):
        return {}
    return {v["id"]: v for v in value if isinstance(v, dict) and isinstance(v.get("id"), str)}


def _source_sha(graph: Any) -> str:
    src = graph.get("source") if isinstance(graph, Mapping) else None
    sha = src.get("sha256", "") if isinstance(src, dict) else ""
    return sha if isinstance(sha, str) else ""


def compare_graphs(before: Any, after: Any) -> dict:
    """Structural/semantic invariant comparison, not pixel/fidelity comparison."""
    findings = []
    for label, graph in (("before", before), ("after", after)):
        if not isinstance(graph, Mapping):
            findings.append(Finding("K21_SOURCE_CONTRACT", f"{label}.$", "K03_TYPE: Manifest must be a JSON object"))
            continue
        for item in validate_manifest(graph):
            findings.append(Finding("K21_SOURCE_CONTRACT", f"{label}.{item.location}", item.code + ": " + item.message))
    bn, an = _by_id(before, "nodes"), _by_id(after, "nodes")
    be, ae = _by_id(before, "edges"), _by_id(after, "edges")
    if set(bn) - set(an):
        findings.append(Finding("K22_LOST_NODE", "nodes", f"Missing semantic nodes: {sorted(set(bn)-set(an))}"))
    if set(an) - set(bn):
        findings.append(Finding("K23_NEW_NODE", "nodes", f"Unexpected semantic nodes: {sorted(set(an)-set(bn))}"))
    if set(be) - set(ae):
        findings.append(Finding("K24_LOST_EDGE", "edges", f"Missing semantic edges: {sorted(set(be)-set(ae))}"))
    if set(ae) - set(be):
        findings.append(Finding("K25_NEW_EDGE", "edges", f"Unexpected semantic edges: {sorted(set(ae)-set(be))}"))
    for eid in sorted(set(be) & set(ae)):
        for field in ("source_id", "target_id", "direction"):
            if be[eid].get(field) != ae[eid].get(field):
                findings.append(Finding("K26_TOPOLOGY_DRIFT", f"edges.{eid}.{field}",
                                        f"changed {be[eid].get(field)} -> {ae[eid].get(field)}"))
        if be[eid].get("relationship") != ae[eid].get("relationship"):
            findings.append(Finding("K27_SEMANTIC_DRIFT", f"edges.{eid}.relationship", "Meaning changed between formats"))
        if be[eid].get("state") != ae[eid].get("state"):
            findings.append(Finding("K28_REVIEW_DRIFT", f"edges.{eid}.state", "Review state changed between formats"))
    hashes = [_source_sha(g) for g in (before, after)]
    joined = json.dumps({"input_sha256":hashes,"nodes":sorted(bn),"edges":sorted(be)},sort_keys=True).encode()
    return {"status": "PASS_SEMANTIC_PARITY_ONLY" if not findings else "FAIL_CLOSED",
            "comparison_sha256": hashlib.sha256(joined).hexdigest(),
            "before_source_sha256": hashes[0], "after_source_sha256":hashes[1],
            "nodes_before":len(bn), "nodes_after":len(an),
            "edges_before":len(be), "edges_after":len(ae),
            "findings":[v.as_dict() for v in findings],
            "disclaimer":"Does not assess pixel rendering, style fidelity, or engineering approval"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before",type=Path)
    ap.add_argument("after",type=Path)
    ap.add_argument("--receipt",type=Path)
    args=ap.parse_args()
    out=compare_graphs(from_path(args.before),from_path(args.after))
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n"
    if args.receipt:
        args.receipt.write_text(payload,encoding="utf-8")
    print(payload,end="")
    return int(out["status"] != "PASS_SEMANTIC_PARITY_ONLY")


if __name__ == "__main__":
    raise SystemExit(main())
