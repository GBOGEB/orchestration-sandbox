"""Synthetic native fixtures for the W11 tests, built in memory.

These are minimal OOXML packages and Inkscape-style SVG documents that contain
only the parts the adapters read. They are not validated against PowerPoint or
Inkscape, they are not real engineering drawings, and nothing produced from
them is engineering evidence.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence

FIXED_DATE = (2026, 11, 13, 0, 0, 0)
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NS_DECL = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
           'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
EMPTY_TREE = ('<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
              "<p:grpSpPr/>{shapes}</p:spTree>")
PLAIN_THEME_LINE = '<a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
CONTENT_TYPES = (
    XML_DECL + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/ppt/presentation.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
    "</Types>"
)
SYNTHETIC_OWNER = {"verified": True, "verified_by": "synthetic-owner-fixture",
                   "decision_id": "SYNTHETIC-LEGEND-0001", "verified_at": "2026-11-13"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip(parts: Dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            archive.writestr(info, parts[name].encode("utf-8"))
    return buf.getvalue()


def _rels(*rels: Sequence[str]) -> str:
    body = "".join(f'<Relationship Id="{rid}" Type="{REL_TYPE}{kind}" Target="{target}"/>'
                   for rid, kind, target in rels)
    return f'{XML_DECL}<Relationships xmlns="{REL_NS}">{body}</Relationships>'


def shape(cid: int, name: str, text: str = "", *, hidden: bool = False) -> str:
    hid = ' hidden="1"' if hidden else ""
    body = f"<p:txBody><a:bodyPr/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody>" if text else ""
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{cid}" name="{name}"{hid}/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="457200"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>{body}</p:sp>')


def connector(cid: int, name: str, start: Optional[int], end: Optional[int], *, head: Optional[str] = None,
              tail: Optional[str] = None, color: Optional[str] = "0000FF", dash: Optional[str] = None,
              no_fill: bool = False, explicit_line: bool = True, style_idx: Optional[int] = 1,
              flip_h: bool = False, hidden: bool = False) -> str:
    hid = ' hidden="1"' if hidden else ""
    st = f'<a:stCxn id="{start}" idx="3"/>' if start is not None else ""
    en = f'<a:endCxn id="{end}" idx="1"/>' if end is not None else ""
    flip = ' flipH="1"' if flip_h else ""
    if no_fill:
        fill = "<a:noFill/>"
    elif color:
        fill = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
    else:
        fill = ""
    dash_el = f'<a:prstDash val="{dash}"/>' if dash else ""
    head_el = f'<a:headEnd type="{head}"/>' if head else ""
    tail_el = f'<a:tailEnd type="{tail}"/>' if tail else ""
    line = f'<a:ln w="12700">{fill}{dash_el}{head_el}{tail_el}</a:ln>' if explicit_line else ""
    style = (f'<p:style><a:lnRef idx="{style_idx}"><a:schemeClr val="accent1"/></a:lnRef>'
             '<a:fillRef idx="0"><a:schemeClr val="accent1"/></a:fillRef>'
             '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
             '<a:fontRef idx="minor"><a:schemeClr val="tx1"/></a:fontRef></p:style>') if style_idx is not None else ""
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{cid}" name="{name}"{hid}/><p:cNvCxnSpPr>{st}{en}</p:cNvCxnSpPr>'
            f'<p:nvPr/></p:nvCxnSpPr><p:spPr><a:xfrm{flip}><a:off x="914400" y="228600"/><a:ext cx="914400" cy="0"/>'
            f'</a:xfrm><a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>{line}</p:spPr>{style}</p:cxnSp>')


def group(cid: int, name: str, children: Iterable[str], *, hidden: bool = False) -> str:
    hid = ' hidden="1"' if hidden else ""
    inner = "".join(children)
    return (f'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{cid}" name="{name}"{hid}/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm rot="5400000"><a:off x="0" y="0"/><a:ext cx="10" cy="10"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="10" cy="10"/></a:xfrm></p:grpSpPr>{inner}</p:grpSp>')


def theme_xml(lines: Iterable[str]) -> str:
    joined = "".join(lines)
    return (f'{XML_DECL}<a:theme {NS_DECL} name="Synthetic"><a:themeElements><a:fmtScheme name="Synthetic">'
            f"<a:fillStyleLst/><a:lnStyleLst>{joined}</a:lnStyleLst><a:effectStyleLst/><a:bgFillStyleLst/>"
            "</a:fmtScheme></a:themeElements></a:theme>")


def pptx_bytes(*slides: Iterable[str], theme_lines: Optional[List[str]] = None, include_theme: bool = True,
               extra: Optional[Dict[str, str]] = None) -> bytes:
    """A minimal transitional PresentationML package with one part per slide."""
    slides = slides or ([],)
    lines = [PLAIN_THEME_LINE] * 3 if theme_lines is None else theme_lines
    slide_ids = "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 2}"/>' for i in range(len(slides)))
    parts = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": _rels(("rId1", "officeDocument", "ppt/presentation.xml")),
        "ppt/presentation.xml": (
            f'{XML_DECL}<p:presentation {NS_DECL}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
            f'</p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst><p:sldSz cx="9144000" cy="6858000"/>'
            '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>'),
        "ppt/_rels/presentation.xml.rels": _rels(
            ("rId1", "slideMaster", "slideMasters/slideMaster1.xml"),
            *[(f"rId{i + 2}", "slide", f"slides/slide{i + 1}.xml") for i in range(len(slides))]),
        "ppt/slideLayouts/slideLayout1.xml": (
            f'{XML_DECL}<p:sldLayout {NS_DECL}><p:cSld>{EMPTY_TREE.format(shapes="")}</p:cSld></p:sldLayout>'),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _rels(("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")),
        "ppt/slideMasters/slideMaster1.xml": (
            f'{XML_DECL}<p:sldMaster {NS_DECL}><p:cSld>{EMPTY_TREE.format(shapes="")}</p:cSld></p:sldMaster>'),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _rels(
            ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"), ("rId2", "theme", "../theme/theme1.xml")),
        "ppt/theme/theme1.xml": theme_xml(lines),
    }
    for i, shapes in enumerate(slides):
        tree = EMPTY_TREE.format(shapes="".join(shapes))
        parts[f"ppt/slides/slide{i + 1}.xml"] = f"{XML_DECL}<p:sld {NS_DECL}><p:cSld>{tree}</p:cSld></p:sld>"
        parts[f"ppt/slides/_rels/slide{i + 1}.xml.rels"] = _rels(("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"))
    if not include_theme:
        del parts["ppt/theme/theme1.xml"]
    parts.update(extra or {})
    return _zip(parts)


def pptx_flow(*, reverse_drawing: bool = False, **connector_kw: Any) -> bytes:
    """P-101 -> HX-201 drawn as one connector, plus a legend box (cNvPr 12)."""
    kw: Dict[str, Any] = {"tail": "triangle"}
    if reverse_drawing:
        kw = {"head": "triangle"}
    kw.update(connector_kw)
    start, end = (5, 4) if reverse_drawing else (4, 5)
    return pptx_bytes([
        shape(4, "P-101", "P-101"),
        shape(5, "HX-201", "HX-201"),
        connector(9, "flow-001", start, end, **kw),
        shape(12, "Legend", "Blue line = FLOW"),
    ])


SVG_OPEN = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="400" height="200" viewBox="0 0 400 200">')
MARKER_DEFS = (
    '<defs>'
    '<marker id="ArrowEnd" orient="auto" markerWidth="8" markerHeight="8" refX="8" refY="4"><path d="M0,0 L8,4 L0,8 z"/></marker>'
    '<marker id="ArrowStart" orient="auto-start-reverse" markerWidth="8" markerHeight="8" refX="8" refY="4">'
    '<path d="M0,0 L8,4 L0,8 z"/></marker>'
    '<marker id="Dot" markerWidth="6" markerHeight="6" refX="3" refY="3"><circle cx="3" cy="3" r="3"/></marker>'
    "</defs>"
)


def svg_shape(eid: str, label: Optional[str], text: str = "", *, title: Optional[str] = None, style: str = "",
              transform: Optional[str] = None) -> str:
    lab = f' inkscape:label="{label}"' if label else ""
    st = f' style="{style}"' if style else ""
    tr = f' transform="{transform}"' if transform else ""
    ttl = f"<title>{title}</title>" if title is not None else ""
    txt = f'<text x="5" y="20">{text}</text>' if text else ""
    return (f'<g id="{eid}"{lab}{st}{tr}>{ttl}'
            f'<rect x="0" y="0" width="60" height="30" style="fill:#ffffff;stroke:#000000"/>{txt}</g>')


def svg_connector(eid: str, label: Optional[str], start: Optional[str], end: Optional[str], *,
                  marker_start: Optional[str] = None, marker_end: Optional[str] = None, stroke: str = "#00f",
                  extra_style: str = "") -> str:
    lab = f' inkscape:label="{label}"' if label else ""
    st = f' inkscape:connection-start="#{start}"' if start else ""
    en = f' inkscape:connection-end="#{end}"' if end else ""
    style = [f"stroke:{stroke}", "fill:none"]
    if marker_start:
        style.append(f"marker-start:url(#{marker_start})")
    if marker_end:
        style.append(f"marker-end:url(#{marker_end})")
    if extra_style:
        style.append(extra_style)
    joined = ";".join(style)
    return (f'<path id="{eid}"{lab} d="M 60,15 L 200,15" style="{joined}" '
            f'inkscape:connector-type="polyline"{st}{en}/>')


def svg_doc(*body: str, stylesheet: Optional[str] = None, layer_style: str = "") -> bytes:
    css = f"<style>{stylesheet}</style>" if stylesheet else ""
    lst = f' style="{layer_style}"' if layer_style else ""
    inner = "".join(body)
    return (f'{SVG_OPEN}{css}{MARKER_DEFS}<g id="layer1" inkscape:groupmode="layer" inkscape:label="Process" '
            f'transform="translate(10,0)"{lst}>{inner}</g>'
            f'<g id="layer2" inkscape:groupmode="layer" inkscape:label="Legend">'
            f'{svg_shape("legend-001", "Legend", "Blue line = FLOW")}</g></svg>').encode("utf-8")


def svg_flow(*, reverse_drawing: bool = False, layer_style: str = "", **connector_kw: Any) -> bytes:
    """P-101 -> HX-201 drawn as one Inkscape connector, plus a legend group."""
    kw: Dict[str, Any] = {"marker_start": "ArrowStart"} if reverse_drawing else {"marker_end": "ArrowEnd"}
    kw.update(connector_kw)
    start, end = ("hx201", "p101") if reverse_drawing else ("p101", "hx201")
    return svg_doc(
        svg_shape("p101", "P-101", "P-101", transform="translate(0,40)"),
        svg_shape("hx201", "HX-201", "HX-201", transform="translate(200,40)"),
        svg_connector("flow001", "flow-001", start, end, **kw),
        layer_style=layer_style,
    )


def legend_record(fmt: str, source: bytes, defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """A synthetic owner-held legend record; ``overrides`` replace any field."""
    record: Dict[str, Any] = {"legend_record_version": "gg-legend-0.1", "format": fmt,
                              "source_sha256": sha256(source)}
    record.update(SYNTHETIC_OWNER)
    record.update(defaults)
    record.update(overrides)
    return record


def pptx_legend(source: bytes, **overrides: Any) -> Dict[str, Any]:
    return legend_record("pptx", source, {
        "legend_object_id": "pptx:s1:12",
        "relationships": [{"match": {"line_color": "srgb:0000FF"}, "relationship": "FLOW"}],
    }, overrides)


def svg_legend(source: bytes, **overrides: Any) -> Dict[str, Any]:
    return legend_record("svg", source, {
        "legend_object_id": "svg:legend-001",
        "relationships": [{"match": {"stroke": "#0000ff"}, "relationship": "FLOW"}],
        "arrowhead_markers": ["ArrowEnd", "ArrowStart"],
    }, overrides)
