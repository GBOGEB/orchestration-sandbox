"""W11 native SVG reader: Inkscape connectors, layers, transforms and markers.

An edge is claimed only for a connector whose two ends are bound with
``inkscape:connection-start``/``inkscape:connection-end`` to existing, uniquely
identified objects. Markers are graphics, not semantics: a marker orients an
edge only when an owner-verified legend record lists that marker id as an
arrowhead (an arrowhead points at the end it is drawn on). Without that record
the marker is kept as unclassified evidence and the direction stays UNKNOWN.
Stylesheets (``<style>``) are not evaluated, so every connector in a document
that has one is UNRESOLVED. Layers and transforms are recorded, never used to
bind or orient an edge.
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from native_common import (
    AdapterInputError,
    assemble,
    build_edge,
    emit,
    finding,
    legend_status,
    load_json,
    local_name,
    match_relationship,
    parse_xml,
    refuse,
    sha256_bytes,
)

ADAPTER_NAME = "gg-w11-svg-native-adapter"
ADAPTER_VERSION = "0.1.0"
INK = "http://www.inkscape.org/namespaces/inkscape"
INK_LABEL = f"{{{INK}}}label"
INK_CONNECTOR = f"{{{INK}}}connector-type"
INK_START = f"{{{INK}}}connection-start"
INK_END = f"{{{INK}}}connection-end"
MAX_BYTES = 20 * 1024 * 1024
_URL = re.compile(r"""^url\(\s*['"]?#([^'")\s]+)['"]?\s*\)$""")
_SHORT_HEX = re.compile(r"^#[0-9a-f]{3}$")


def _style(el: ET.Element) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for decl in (el.get("style") or "").split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip().lower()] = value.strip()
    return out


def _own(el: ET.Element, prop: str) -> Optional[str]:
    """Value set on this element: style declarations beat presentation attributes."""
    style = _style(el)
    if prop in style:
        return style[prop]
    if prop.startswith("marker-") and "marker" in style:
        return style["marker"]
    value = el.get(prop)
    return value.strip() if value is not None else None


def _effective(chain: Sequence[ET.Element], prop: str) -> Optional[str]:
    """Inherited property value along root..self (for stroke, markers, visibility)."""
    for el in reversed(chain):
        value = _own(el, prop)
        if value is not None and value != "inherit":
            return value
    return None


def _zero(value: Optional[str]) -> bool:
    if value is None:
        return False
    try:
        number = float(value[:-1]) / 100 if value.endswith("%") else float(value)
    except ValueError:
        return False
    return number == 0


def _hidden(chain: Sequence[ET.Element]) -> Optional[str]:
    for el in chain:
        if _own(el, "display") == "none":
            return "display:none on itself or an ancestor (hidden layer or group)"
        if _zero(_own(el, "opacity")):
            return "opacity 0 on itself or an ancestor"
    if _effective(chain, "visibility") in ("hidden", "collapse"):
        return "visibility hidden"
    return None


def _color(value: Optional[str]) -> str:
    if value is None:
        return "none"  # SVG initial value of stroke
    value = value.strip().lower()
    if _SHORT_HEX.fullmatch(value):
        value = "#" + "".join(c * 2 for c in value[1:])
    return value


def _marker_ref(value: Optional[str]) -> Tuple[Optional[str], bool]:
    """(marker id or None, malformed?)."""
    if value is None or value == "none":
        return None, False
    match = _URL.match(value)
    return (match.group(1), False) if match else (None, True)


def _tag(el: ET.Element) -> Tuple[str, Optional[str], bool]:
    """(semantic tag, tag source, ambiguous?) from inkscape:label and <title>."""
    label = (el.get(INK_LABEL) or "").strip()
    title_el = next((c for c in el if local_name(c.tag) == "title"), None)
    title = (title_el.text or "").strip() if title_el is not None else ""
    if label and title and label != title:
        return "", None, True
    if label:
        return label, "inkscape:label", False
    if title:
        return title, "title", False
    return "", None, False


def _layers(chain: Sequence[ET.Element]) -> List[Dict[str, Optional[str]]]:
    return [{"id": el.get("id"), "label": el.get(INK_LABEL)} for el in chain
            if el.get(f"{{{INK}}}groupmode") == "layer"]


def _transforms(chain: Sequence[ET.Element]) -> List[Dict[str, Optional[str]]]:
    return [{"id": el.get("id"), "transform": el.get("transform")} for el in chain if el.get("transform")]


def _text(el: ET.Element) -> str:
    texts = [" ".join("".join(t.itertext()).split()) for t in el.iter() if local_name(t.tag) == "text"]
    return " ".join(t for t in texts if t).strip()


def read_svg(data: bytes, *, name: str = "input.svg", legend: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return a W10 manifest of CANDIDATE/UNRESOLVED claims for one SVG document."""
    if len(data) > MAX_BYTES:
        raise AdapterInputError("svg: file too large")
    source_sha = sha256_bytes(data)
    root = parse_xml(data, "svg")
    if local_name(root.tag) != "svg":
        raise AdapterInputError("svg: root element is not <svg>")
    parents = {child: parent for parent in root.iter() for child in parent}

    def chain(el: ET.Element) -> List[ET.Element]:
        out = [el]
        while out[-1] in parents:
            out.append(parents[out[-1]])
        return list(reversed(out))

    by_id: Dict[str, List[ET.Element]] = {}
    for el in root.iter():
        if el.get("id"):
            by_id.setdefault(el.get("id"), []).append(el)
    findings: List[Dict[str, str]] = [
        finding("A01_NATIVE_ID", "svg:" + ident, f"id is used by {len(els)} elements; none of them is bound")
        for ident, els in sorted(by_id.items()) if len(els) > 1
    ]
    stylesheet = any(local_name(el.tag) == "style" and (el.text or "").strip() for el in root.iter())
    if stylesheet:
        findings.append(finding("A04_STYLESHEET", "svg", "<style> present; CSS is not evaluated, so connectors are UNRESOLVED"))
    legend_info = legend_status(legend, fmt="svg", source_sha256=source_sha,
                                native_ids=["svg:" + i for i, els in by_id.items() if len(els) == 1])
    arrowheads = set(legend_info["arrowhead_markers"])
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    quarantine: List[Dict[str, Any]] = []

    def node_id(el: ET.Element) -> str:
        sid = "svg:" + el.get("id", "")
        if sid not in nodes:
            tag, source, ambiguous = _tag(el)
            if ambiguous:
                findings.append(finding("A03_AMBIGUOUS_TAG", sid, "inkscape:label and <title> disagree; native id used"))
            el_chain = chain(el)
            node: Dict[str, Any] = {
                "id": "node:" + tag if tag else "native:" + sid,
                "source_object_id": sid,
                "identity": "AMBIGUOUS_TAG" if ambiguous else ("TAGGED" if tag else "NATIVE_ONLY"),
                "native": {"element": local_name(el.tag), "layers": _layers(el_chain),
                           "transforms": _transforms(el_chain), "hidden": bool(_hidden(el_chain)),
                           "tag_source": source},
            }
            if tag:
                node["tag"] = tag
            text = _text(el)
            if text:
                node["label"] = text
            nodes[sid] = node
        return nodes[sid]["id"]

    connectors = [el for el in root.iter()
                  if el.get(INK_CONNECTOR) is not None or el.get(INK_START) is not None or el.get(INK_END) is not None]
    for position, el in enumerate(connectors):
        cid = el.get("id")
        if not cid or len(by_id.get(cid, [])) != 1:
            sid = "svg:" + cid if cid else f"svg:#connector-{position}"
            quarantine.append({"source_object_id": sid, "locator": sid, "reason": "connector has no unique id"})
            continue
        sid = "svg:" + cid
        ends: Dict[str, ET.Element] = {}
        problems: List[str] = []
        for which, attr in (("connection-start", INK_START), ("connection-end", INK_END)):
            ref = el.get(attr)
            targets = by_id.get(ref[1:], []) if ref and ref.startswith("#") else []
            if not ref:
                problems.append(f"inkscape:{which} missing: end not bound to an object (never inferred from geometry or proximity)")
            elif len(targets) != 1:
                problems.append(f"inkscape:{which} {ref!r} is missing or duplicated")
            elif targets[0].get(INK_CONNECTOR) is not None:
                problems.append(f"inkscape:{which} binds to another connector; connector chains are not read in this slice")
            else:
                ends[which] = targets[0]
        if not problems and ends["connection-start"] is ends["connection-end"]:
            problems.append("self-loop: both ends bind to the same object (needs a separate review contract)")
        if problems:
            quarantine.append({"source_object_id": sid, "locator": sid, "reason": "; ".join(problems)})
            continue
        start, end = ends["connection-start"], ends["connection-end"]
        el_chain = chain(el)
        unresolved: List[str] = []
        if stylesheet:
            unresolved.append("document has a <style> stylesheet; effective markers, stroke and visibility are not evaluated")
        hidden = _hidden(el_chain)
        if hidden:
            unresolved.append("connector hidden: " + hidden)
        if _hidden(chain(start)) or _hidden(chain(end)):
            unresolved.append("an endpoint object is hidden")
        stroke = _color(_effective(el_chain, "stroke"))
        if stroke == "none" or _zero(_effective(el_chain, "stroke-opacity")):
            unresolved.append("connector has no visible stroke")
        evidence: List[Dict[str, Any]] = [
            {"type": "SVG_CONNECTOR_ANCHOR", "locator": sid + "@inkscape:connection-start", "target": "svg:" + start.get("id", "")},
            {"type": "SVG_CONNECTOR_ANCHOR", "locator": sid + "@inkscape:connection-end", "target": "svg:" + end.get("id", "")},
        ]
        arrows: Dict[str, Dict[str, Any]] = {}
        unclassified = False
        for prop, proof in (("marker-start", "SVG_MARKER_START"), ("marker-end", "SVG_MARKER_END"), ("marker-mid", None)):
            raw = _effective(el_chain, prop)
            marker, malformed = _marker_ref(raw)
            where = f"{sid}@{prop}"
            if malformed:
                unresolved.append(f"{prop} value {raw!r} is not a local url(#id) reference")
                continue
            if marker is None:
                continue
            found = by_id.get(marker, [])
            if len(found) != 1 or local_name(found[0].tag) != "marker":
                unresolved.append(f"{prop} refers to {marker!r}, which is not a unique <marker>")
            elif marker in arrowheads and proof is None:
                unresolved.append("arrowhead on marker-mid: direction along a multi-segment path is not read in this slice")
            elif marker in arrowheads:
                arrows[prop] = {"type": proof, "locator": where, "marker_id": marker}
            elif proof is not None:
                evidence.append({"type": "SVG_MARKER_UNCLASSIFIED", "locator": where, "marker_id": marker})
                unclassified = True
        if unclassified and not legend_info["applied"]:
            findings.append(finding("A05_MARKER_UNCLASSIFIED", sid,
                                    "marker present but no applied legend classifies it; direction left UNKNOWN"))
        signature = {"stroke": stroke, "stroke-dasharray": (_effective(el_chain, "stroke-dasharray") or "none").strip()}
        relationship, ambiguity = match_relationship(legend_info, signature)
        if ambiguity:
            unresolved.append(ambiguity)
        tag, _, ambiguous = _tag(el)
        if ambiguous:
            findings.append(finding("A03_AMBIGUOUS_TAG", sid, "inkscape:label and <title> disagree; native id used"))
        edges.append(build_edge(
            edge_id="edge:" + tag if tag else "edge:native:" + sid,
            connector_id=sid,
            start=node_id(start),
            end=node_id(end),
            start_arrow=arrows.get("marker-start"),
            end_arrow=arrows.get("marker-end"),
            evidence=evidence,
            relationship=relationship,
            legend=legend_info,
            unresolved=unresolved,
            native={"start": "svg:" + start.get("id", ""), "end": "svg:" + end.get("id", ""),
                    "connector_type": el.get(INK_CONNECTOR), "layers": _layers(el_chain),
                    "transforms": _transforms(el_chain), "line_style": signature},
        ))
    return assemble(
        fmt="svg",
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        source_sha256=source_sha,
        locator=f"native-svg://{Path(name).name}",
        nodes=nodes.values(),
        edges=edges,
        quarantine=quarantine,
        legend=legend_info,
        findings=findings,
        native={"connectors_seen": len(connectors), "stylesheet": stylesheet, "view_box": root.get("viewBox")},
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="gg_Engine W11 native SVG adapter (CANDIDATE claims only)")
    ap.add_argument("svg", type=Path)
    ap.add_argument("--legend", type=Path, help="owner-held legend record (JSON) bound to this file's SHA-256")
    ap.add_argument("--out", type=Path, help="write the manifest here instead of stdout")
    ap.add_argument("--contract-receipt", type=Path, help="also run the W10 contract gate and write its receipt")
    args = ap.parse_args(argv)
    try:
        legend = load_json(args.legend) if args.legend else None
        doc = read_svg(args.svg.read_bytes(), name=args.svg.name, legend=legend)
    except AdapterInputError as exc:
        return refuse(exc)
    except OSError as exc:
        return refuse(AdapterInputError(f"svg: cannot read {args.svg.name} ({exc.__class__.__name__})"))
    return emit(doc, args.out, args.contract_receipt)


if __name__ == "__main__":
    raise SystemExit(main())
