"""W11 native PPTX reader: OOXML shapes, connectors, connection sites and line ends.

It reads one slide of a transitional-OOXML package with the standard library.
An edge is claimed only for a connector (``p:cxnSp``) whose two ends are bound
with ``a:stCxn``/``a:endCxn`` to existing, uniquely identified shapes.
Direction comes only from arrowhead line ends (``a:headEnd``/``a:tailEnd`` of
type triangle, stealth or arrow), either explicit on the connector or resolved
from the theme line style its ``p:style/a:lnRef`` points to. ``headEnd`` sits at
the ``stCxn`` end and ``tailEnd`` at the ``endCxn`` end, so flips and rotation do
not change the reading; they are recorded as native context only. Geometry,
proximity and neighbour order never bind an endpoint or orient an edge.
"""
from __future__ import annotations

import argparse
import io
import posixpath
import zipfile
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

ADAPTER_NAME = "gg-w11-pptx-native-adapter"
ADAPTER_VERSION = "0.1.0"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"p": P, "a": A}
ARROW_LINE_ENDS = {"triangle", "stealth", "arrow"}
NON_ARROW_LINE_ENDS = {"diamond", "oval"}
NV_PATH = {
    "sp": "p:nvSpPr/p:cNvPr",
    "cxnSp": "p:nvCxnSpPr/p:cNvPr",
    "pic": "p:nvPicPr/p:cNvPr",
    "graphicFrame": "p:nvGraphicFramePr/p:cNvPr",
    "grpSp": "p:nvGrpSpPr/p:cNvPr",
}
XFRM_PATH = {
    "sp": "p:spPr/a:xfrm",
    "cxnSp": "p:spPr/a:xfrm",
    "pic": "p:spPr/a:xfrm",
    "graphicFrame": "p:xfrm",
    "grpSp": "p:grpSpPr/a:xfrm",
}
MAX_PARTS = 10000
MAX_PART_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class _Package:
    """Read-only view of an OPC package; parts are parsed lazily and size-capped."""

    def __init__(self, data: bytes) -> None:
        try:
            self._zip = zipfile.ZipFile(io.BytesIO(data))
            infos = self._zip.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            raise AdapterInputError("pptx: not a ZIP/OPC package") from exc
        if len(infos) > MAX_PARTS:
            raise AdapterInputError("pptx: too many package parts")
        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
            raise AdapterInputError("pptx: declared uncompressed size too large")
        self._names = {i.filename for i in infos}
        self._xml: Dict[str, ET.Element] = {}

    def has(self, part: str) -> bool:
        return part in self._names

    def xml(self, part: str) -> ET.Element:
        if part not in self._xml:
            if part not in self._names:
                raise AdapterInputError(f"pptx: missing part {part}")
            info = self._zip.getinfo(part)
            if info.file_size > MAX_PART_BYTES:
                raise AdapterInputError(f"pptx: part {part} too large")
            try:
                data = self._zip.read(info)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
                raise AdapterInputError(f"pptx: part {part} unreadable ({exc.__class__.__name__})") from exc
            self._xml[part] = parse_xml(data, f"pptx:{part}")
        return self._xml[part]

    def rels(self, part: str) -> List[Tuple[str, str, str]]:
        """(rId, relationship kind, resolved part name) for internal relationships of ``part``."""
        folder, name = posixpath.split(part)
        rels_part = posixpath.join(folder, "_rels", name + ".rels")
        if not self.has(rels_part):
            return []
        out = []
        for rel in self.xml(rels_part):
            if local_name(rel.tag) != "Relationship" or rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            resolved = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
            out.append((rel.get("Id", ""), rel.get("Type", "").rsplit("/", 1)[-1], resolved))
        return out

    def related(self, part: str, kind: str) -> List[str]:
        return [target for _, rel_kind, target in self.rels(part) if rel_kind == kind]


def _slides(pkg: _Package) -> List[str]:
    office = pkg.related("", "officeDocument")
    pres = office[0] if len(office) == 1 else "ppt/presentation.xml"
    root = pkg.xml(pres)
    if root.tag != f"{{{P}}}presentation":
        raise AdapterInputError("pptx: not transitional PresentationML (Strict OOXML is not read in this slice)")
    targets = {rid: (kind, target) for rid, kind, target in pkg.rels(pres)}
    slides = []
    for sld in root.iterfind("p:sldIdLst/p:sldId", NS):
        kind, target = targets.get(sld.get(f"{{{R}}}id", ""), ("", ""))
        if kind != "slide" or not pkg.has(target):
            raise AdapterInputError("pptx: slide list entry does not resolve to a slide part")
        slides.append(target)
    return slides


def _theme_line_styles(pkg: _Package, slide_part: str) -> Optional[Tuple[str, List[ET.Element]]]:
    """Follow slide -> layout -> master -> theme; None if any hop is missing or ambiguous."""
    part = slide_part
    for kind in ("slideLayout", "slideMaster", "theme"):
        nxt = pkg.related(part, kind)
        if len(nxt) != 1 or not pkg.has(nxt[0]):
            return None
        part = nxt[0]
    styles = pkg.xml(part).find("a:themeElements/a:fmtScheme/a:lnStyleLst", NS)
    if styles is None:
        return None
    return part, styles.findall("a:ln", NS)


def _xfrm(el: ET.Element, kind: str) -> Dict[str, str]:
    x = el.find(XFRM_PATH[kind], NS)
    if x is None:
        return {}
    out = {k: x.get(k, "") for k in ("rot", "flipH", "flipV") if x.get(k) is not None}
    off, ext = x.find("a:off", NS), x.find("a:ext", NS)
    if off is not None:
        out["off"] = ",".join((off.get("x", ""), off.get("y", "")))
    if ext is not None:
        out["ext"] = ",".join((ext.get("cx", ""), ext.get("cy", "")))
    return out


def _text(el: ET.Element) -> str:
    body = el.find("p:txBody", NS)
    if body is None:
        return ""
    paragraphs = ["".join(t.text or "" for t in para.iter(f"{{{A}}}t")) for para in body.findall("a:p", NS)]
    return "\n".join(p for p in paragraphs if p).strip()


def _objects(sp_tree: ET.Element) -> List[Dict[str, Any]]:
    """Every addressable object on the slide, with its group path and inherited visibility."""
    out: List[Dict[str, Any]] = []

    def walk(container: ET.Element, groups: List[Dict[str, Any]], hidden: bool) -> None:
        for child in container:
            kind = local_name(child.tag)
            if kind == "AlternateContent":
                out.append({"kind": kind})
                continue
            if kind not in NV_PATH:
                continue
            cnv = child.find(NV_PATH[kind], NS)
            is_hidden = hidden or (cnv is not None and cnv.get("hidden") in ("1", "true"))
            out.append({"kind": kind, "element": child, "cnv": cnv, "groups": list(groups), "hidden": is_hidden})
            if kind == "grpSp":
                ref = {"id": cnv.get("id") if cnv is not None else None,
                       "name": cnv.get("name") if cnv is not None else None,
                       "xfrm": _xfrm(child, "grpSp")}
                walk(child, groups + [ref], is_hidden)

    walk(sp_tree, [], False)
    return out


def _line_signature(ln: Optional[ET.Element]) -> Dict[str, str]:
    """Literal native line style, for matching against an owner-held legend record."""
    color, dash = "INHERITED", "INHERITED"
    if ln is not None:
        fill = ln.find("a:solidFill", NS)
        if fill is not None and len(fill):
            c = fill[0]
            prefix = {"srgbClr": "srgb:", "schemeClr": "scheme:", "prstClr": "preset:", "sysClr": "system:"}
            val = c.get("val", "")
            color = prefix.get(local_name(c.tag), local_name(c.tag) + ":") + (val.upper() if local_name(c.tag) == "srgbClr" else val)
        elif ln.find("a:noFill", NS) is not None:
            color = "none"
        d = ln.find("a:prstDash", NS)
        if d is not None:
            dash = d.get("val", "solid")
    return {"line_color": color, "line_dash": dash}


def read_pptx(data: bytes, *, slide: int = 1, name: str = "input.pptx",
              legend: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return a W10 manifest of CANDIDATE/UNRESOLVED claims for one slide."""
    source_sha = sha256_bytes(data)
    pkg = _Package(data)
    slides = _slides(pkg)
    if not 1 <= slide <= len(slides):
        raise AdapterInputError(f"pptx: slide {slide} is not in 1..{len(slides)}")
    part = slides[slide - 1]
    tree = pkg.xml(part).find("p:cSld/p:spTree", NS)
    if tree is None:
        raise AdapterInputError(f"pptx:{part}: no p:spTree")
    slide_tag = f"s{slide}"
    findings: List[Dict[str, str]] = []
    quarantine: List[Dict[str, Any]] = []
    by_id: Dict[str, List[Dict[str, Any]]] = {}
    for obj in _objects(tree):
        if obj["kind"] == "AlternateContent":
            findings.append(finding("A06_MARKUP_COMPATIBILITY", f"pptx:{part}",
                                    "mc:AlternateContent present; shapes inside it are not read in this slice"))
            continue
        cid = obj["cnv"].get("id") if obj["cnv"] is not None else None
        if not cid:
            findings.append(finding("A01_NATIVE_ID", f"pptx:{part}", obj["kind"] + " without p:cNvPr/@id"))
            continue
        obj.update(cid=cid, sid=f"pptx:{slide_tag}:{cid}", name=(obj["cnv"].get("name") or "").strip())
        by_id.setdefault(cid, []).append(obj)
    for cid, objs in sorted(by_id.items()):
        if len(objs) > 1:
            findings.append(finding("A01_NATIVE_ID", f"pptx:{slide_tag}:{cid}",
                                    f"cNvPr id {cid} is used by {len(objs)} objects; none of them is bound"))
            quarantine.extend({"source_object_id": f"pptx:{slide_tag}:{cid}", "locator": f"pptx:{part}#cNvPr={cid}",
                               "reason": "connector has a duplicated native cNvPr id"}
                              for o in objs if o["kind"] == "cxnSp")
    unique = {cid: objs[0] for cid, objs in by_id.items() if len(objs) == 1}
    legend_info = legend_status(legend, fmt="pptx", source_sha256=source_sha,
                                native_ids=[o["sid"] for o in unique.values()])
    theme_cache: Dict[str, Optional[Tuple[str, List[ET.Element]]]] = {}

    def theme() -> Optional[Tuple[str, List[ET.Element]]]:
        if "v" not in theme_cache:
            theme_cache["v"] = _theme_line_styles(pkg, part)
        return theme_cache["v"]

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def node_id(obj: Dict[str, Any]) -> str:
        if obj["sid"] not in nodes:
            tag = obj["name"]
            node: Dict[str, Any] = {
                "id": "node:" + tag if tag else "native:" + obj["sid"],
                "source_object_id": obj["sid"],
                "identity": "TAGGED" if tag else "NATIVE_ONLY",
                "native": {"kind": obj["kind"], "group_path": obj["groups"], "hidden": obj["hidden"],
                           "xfrm": _xfrm(obj["element"], obj["kind"]), "tag_source": "p:cNvPr/@name" if tag else None},
            }
            if tag:
                node["tag"] = tag
            text = _text(obj["element"])
            if text:
                node["label"] = text
            nodes[obj["sid"]] = node
        return nodes[obj["sid"]]["id"]

    for obj in sorted(unique.values(), key=lambda o: o["sid"]):
        if obj["kind"] != "cxnSp":
            continue
        el, loc = obj["element"], f"pptx:{part}#cNvPr={obj['cid']}"
        ends: Dict[str, Tuple[Dict[str, Any], Optional[str]]] = {}
        problems: List[str] = []
        for which in ("stCxn", "endCxn"):
            ref = el.find(f"p:nvCxnSpPr/p:cNvCxnSpPr/a:{which}", NS)
            target = by_id.get(ref.get("id", ""), []) if ref is not None else []
            if ref is None:
                problems.append(f"a:{which} missing: end not bound to a shape (never inferred from geometry)")
            elif len(target) != 1:
                problems.append(f"a:{which} refers to cNvPr id {ref.get('id')!r}, which is missing or duplicated")
            elif target[0]["kind"] == "cxnSp":
                problems.append(f"a:{which} binds to another connector; connector chains are not read in this slice")
            else:
                ends[which] = (target[0], ref.get("idx"))
        if not problems and ends["stCxn"][0] is ends["endCxn"][0]:
            problems.append("self-loop: both ends bind to the same shape (needs a separate review contract)")
        if problems:
            quarantine.append({"source_object_id": obj["sid"], "locator": loc, "reason": "; ".join(problems)})
            continue
        (start, start_site), (end, end_site) = ends["stCxn"], ends["endCxn"]
        unresolved: List[str] = []
        evidence: List[Dict[str, Any]] = [
            {"type": "PPTX_CONNECTOR_ANCHOR", "locator": loc + "/a:stCxn", "target": start["sid"], "site_idx": start_site},
            {"type": "PPTX_CONNECTOR_ANCHOR", "locator": loc + "/a:endCxn", "target": end["sid"], "site_idx": end_site},
        ]
        arrows: Dict[str, Dict[str, Any]] = {}
        ln = el.find("p:spPr/a:ln", NS)
        ln_ref = el.find("p:style/a:lnRef", NS)
        try:
            style_idx = int(ln_ref.get("idx", "0")) if ln_ref is not None else 0
        except ValueError:
            style_idx = 0
            unresolved.append("p:style/a:lnRef/@idx is not an integer")
        for end_name, proof in (("headEnd", "PPTX_HEAD_END"), ("tailEnd", "PPTX_TAIL_END")):
            explicit = ln.find(f"a:{end_name}", NS) if ln is not None else None
            if explicit is not None:
                kind, where = explicit.get("type", "none"), f"{loc}/p:spPr/a:ln/a:{end_name}"
            elif style_idx > 0:
                resolved = theme()
                if resolved is None or style_idx > len(resolved[1]):
                    unresolved.append(f"a:{end_name} is inherited from theme line style {style_idx}, which does not resolve")
                    continue
                inherited = resolved[1][style_idx - 1].find(f"a:{end_name}", NS)
                kind = inherited.get("type", "none") if inherited is not None else "none"
                where = f"pptx:{resolved[0]}#a:lnStyleLst/a:ln[{style_idx}]/a:{end_name}"
            else:
                continue  # no explicit end and no style reference: the OOXML default is no decoration
            if kind in ARROW_LINE_ENDS:
                arrows[end_name] = {"type": proof, "locator": where, "line_end_type": kind}
            elif kind in NON_ARROW_LINE_ENDS:
                evidence.append({"type": "PPTX_LINE_END_NON_ARROW", "locator": where, "line_end_type": kind})
            elif kind != "none":
                unresolved.append(f"a:{end_name} type {kind!r} is not a known line-end type")
        if obj["hidden"]:
            unresolved.append("connector is hidden (p:cNvPr/@hidden on itself or a parent group)")
        if start["hidden"] or end["hidden"]:
            unresolved.append("an endpoint shape is hidden")
        if ln is not None and ln.find("a:noFill", NS) is not None:
            unresolved.append("connector line has a:noFill and is not visible")
        signature = _line_signature(ln)
        relationship, ambiguity = match_relationship(legend_info, signature)
        if ambiguity:
            unresolved.append(ambiguity)
        edges.append(build_edge(
            edge_id="edge:" + obj["name"] if obj["name"] else "edge:native:" + obj["sid"],
            connector_id=obj["sid"],
            start=node_id(start),
            end=node_id(end),
            start_arrow=arrows.get("headEnd"),
            end_arrow=arrows.get("tailEnd"),
            evidence=evidence,
            relationship=relationship,
            legend=legend_info,
            unresolved=unresolved,
            native={"start": start["sid"], "end": end["sid"], "group_path": obj["groups"],
                    "xfrm": _xfrm(el, "cxnSp"), "line_style": signature},
        ))
    return assemble(
        fmt="pptx",
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        source_sha256=source_sha,
        locator=f"native-pptx://{Path(name).name}#slide={slide}",
        nodes=nodes.values(),
        edges=edges,
        quarantine=quarantine,
        legend=legend_info,
        findings=findings,
        native={"slide": slide, "slide_part": part, "slide_count": len(slides),
                "theme_part": (theme_cache.get("v") or (None,))[0]},
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="gg_Engine W11 native PPTX adapter (CANDIDATE claims only)")
    ap.add_argument("pptx", type=Path)
    ap.add_argument("--slide", type=int, default=1, help="1-based slide number in presentation order")
    ap.add_argument("--legend", type=Path, help="owner-held legend record (JSON) bound to this file's SHA-256")
    ap.add_argument("--out", type=Path, help="write the manifest here instead of stdout")
    ap.add_argument("--contract-receipt", type=Path, help="also run the W10 contract gate and write its receipt")
    args = ap.parse_args(argv)
    try:
        legend = load_json(args.legend) if args.legend else None
        doc = read_pptx(args.pptx.read_bytes(), slide=args.slide, name=args.pptx.name, legend=legend)
    except AdapterInputError as exc:
        return refuse(exc)
    except OSError as exc:
        return refuse(AdapterInputError(f"pptx: cannot read {args.pptx.name} ({exc.__class__.__name__})"))
    return emit(doc, args.out, args.contract_receipt)


if __name__ == "__main__":
    raise SystemExit(main())
