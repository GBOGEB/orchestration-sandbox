"""W12 read-only native evidence ingress. Never derives engineering truth.

DOCX/XLSX/VSDX/PNG preserve their native locators, exact binary hashes, and
verbatim text. Any semantic link requires an explicit source-bound binding.
"""
from __future__ import annotations
import hashlib
import io
import json
import posixpath
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAX_FILES = 4000
MAX_FILE = 12 * 1024 * 1024
MAX_TOTAL = 80 * 1024 * 1024
DTD = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.I)
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
X = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PKG_R = '{http://schemas.openxmlformats.org/package/2006/relationships}'
V = '{http://schemas.microsoft.com/office/visio/2012/main}'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_xml(data):
    if DTD.search(data) or b'\x00' in data or len(data) > MAX_FILE:
        raise ValueError('XML_UNSAFE_OR_TOO_LARGE')
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError('XML_MALFORMED') from exc


def unzip_safe(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    infos = z.infolist()
    if len(infos) > MAX_FILES or sum(x.file_size for x in infos) > MAX_TOTAL:
        raise ValueError('OOXML_ARCHIVE_LIMIT')
    names = [x.filename for x in infos]
    if len(names) != len(set(names)):
        raise ValueError('OOXML_DUPLICATE_PART')
    for x in infos:
        parts = x.filename.split('/')
        if x.file_size > MAX_FILE or x.filename.startswith('/') or '\\' in x.filename or '..' in parts:
            raise ValueError('OOXML_UNSAFE_PART')
        if x.compress_size == 0 and x.file_size > 0:
            raise ValueError('OOXML_COMPRESSION_ANOMALY')
    return z


def result(fmt, data, items, findings=()):
    return {'schema':'gg-evidence-1.0','format':fmt,'source_sha256':sha(data),
            'status':'EVIDENCE_ONLY_NOT_AUTHORITY','objects':items,'findings':list(findings),
            'object_count':len(items)}


def read_docx(data):
    with unzip_safe(data) as z:
        if 'word/document.xml' not in z.namelist():
            raise ValueError('DOCX_DOCUMENT_MISSING')
        root = parse_xml(z.read('word/document.xml'))
    items = []
    for i, p in enumerate(root.iter(W+'p'), 1):
        txt = ''.join(n.text or '' for n in p.iter(W+'t'))
        if txt.strip():
            items.append({'source_object_id':f'docx:paragraph:{i}', 'text':txt,
                          'classification':'SOURCE_VERBATIM', 'semantic_id':None})
    return result('docx',data,items)


def _sheet_target(name):
    if name.startswith('/xl/'):
        name = name[1:]
    elif name.startswith('xl/'):
        pass
    else:
        name = 'xl/'+name
    name = posixpath.normpath(name)
    if not name.startswith('xl/') or '..' in name.split('/'):
        raise ValueError('XLSX_RELATION_PATH')
    return name


def read_xlsx(data):
    with unzip_safe(data) as z:
        allnames = set(z.namelist())
        if 'xl/workbook.xml' not in allnames or 'xl/_rels/workbook.xml.rels' not in allnames:
            raise ValueError('XLSX_WORKBOOK_MISSING')
        wb = parse_xml(z.read('xl/workbook.xml'))
        rels = parse_xml(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.get('Id'):r.get('Target') for r in rels.findall(PKG_R+'Relationship')
                  if r.get('TargetMode') != 'External'}
        strings = []
        if 'xl/sharedStrings.xml' in allnames:
            ss = parse_xml(z.read('xl/sharedStrings.xml'))
            strings = [''.join(t.text or '' for t in si.iter(X+'t')) for si in ss.findall(X+'si')]
        items = []
        sheets = wb.find(X+'sheets')
        if sheets is None:
            return result('xlsx',data,[])
        for sn, sheet in enumerate(sheets.findall(X+'sheet'),1):
            relid = sheet.get(R+'id')
            if relid not in relmap:
                raise ValueError('XLSX_SHEET_REL_MISSING')
            part = _sheet_target(relmap[relid])
            if part not in allnames:
                raise ValueError('XLSX_SHEET_MISSING')
            root = parse_xml(z.read(part))
            data_node = root.find(X+'sheetData')
            if data_node is None:
                continue
            for row in data_node.findall(X+'row'):
                cells = {}
                formulas = {}
                for cell in row.findall(X+'c'):
                    addr = cell.get('r')
                    if not addr:
                        raise ValueError('XLSX_CELL_ADDRESS_MISSING')
                    f, val = cell.find(X+'f'), cell.find(X+'v')
                    inline = cell.find(X+'is')
                    if f is not None:
                        formulas[addr] = f.text or ''
                        cells[addr] = 'FORMULA_NOT_RECALCULATED'
                    elif cell.get('t') == 'inlineStr' and inline is not None:
                        cells[addr] = ''.join(x.text or '' for x in inline.iter(X+'t'))
                    elif cell.get('t') == 's' and val is not None:
                        n=int(val.text or '-1')
                        if n < 0 or n >= len(strings):
                            raise ValueError('XLSX_SHARED_STRING_RANGE')
                        cells[addr]=strings[n]
                    else:
                        cells[addr] = val.text if val is not None else ''
                if cells:
                    sheet_name = sheet.get('name') or f'Sheet{sn}'
                    items.append({'source_object_id':f'xlsx:{sheet_name}:row:{row.get("r")}',
                                  'sheet':sheet_name,'cells':cells,'formulas':formulas,
                                  'classification':'SOURCE_VERBATIM_WITH_UNEVALUATED_FORMULAS',
                                  'semantic_id':None})
    return result('xlsx',data,items)


def read_vsdx(data):
    items = []
    with unzip_safe(data) as z:
        pages = sorted(p for p in z.namelist()
                       if re.fullmatch(r'visio/pages/page\d+\.xml',p))
        for page in pages:
            root = parse_xml(z.read(page))
            seen=set()
            for shape in root.iter():
                if shape.tag.split('}')[-1]!='Shape':
                    continue
                native = shape.get('ID')
                if native is None:
                    continue
                if native in seen:
                    raise ValueError('VSDX_DUPLICATE_SHAPE_ID')
                seen.add(native)
                items.append({'source_object_id':f'vsdx:{page}:shape:{native}',
                              'name':shape.get('NameU') or shape.get('Name') or '',
                              'direction':'UNKNOWN','classification':'UNRESOLVED_NO_CONNECTOR_AUTHORITY'})
    return result('vsdx',data,items)


def read_png(data):
    if len(data)<33 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[12:16]!=b'IHDR':
        raise ValueError('PNG_INVALID_SIGNATURE')
    width,height=struct.unpack('>II',data[16:24])
    if not (0<width<=100000 and 0<height<=100000):
        raise ValueError('PNG_INVALID_DIMENSIONS')
    return result('png',data,[{'source_object_id':'png:canvas', 'width_px':width,
            'height_px':height,'direction':'UNKNOWN',
            'classification':'RASTER_ONLY_NO_SEMANTIC_AUTHORITY'}])


def bind_explicit(graph, evidence, bindings):
    """Do not match by same-looking text, ID token, geometry or colour."""
    valid_graph_ids = {n.get('id') for n in graph.get('nodes',[])} | \
                      {e.get('id') for e in graph.get('edges',[])}
    valid_evidence = {o['source_object_id'] for o in evidence.get('objects',[])}
    used=set()
    links=[]
    quarantine=[]
    for i, b in enumerate(bindings):
        pair = (b.get('semantic_id'),b.get('source_object_id'))
        problems=[]
        if pair in used:
            problems.append('DUPLICATE_BINDING')
        used.add(pair)
        if b.get('semantic_id') not in valid_graph_ids:
            problems.append('UNKNOWN_SEMANTIC_ID')
        if b.get('source_object_id') not in valid_evidence:
            problems.append('UNKNOWN_NATIVE_ID')
        if b.get('source_sha256')!=evidence.get('source_sha256'):
            problems.append('STALE_EVIDENCE_SHA')
        if not isinstance(b.get('reason'),str) or not b['reason'].strip():
            problems.append('MISSING_LINK_RATIONALE')
        if b.get('state')!='CANDIDATE_LINK':
            problems.append('UNAUTHORIZED_LINK_PROMOTION')
        if problems:
            quarantine.append({'binding_index':i,'reasons':problems})
        else:
            links.append({'semantic_id':pair[0],'source_object_id':pair[1],
                          'source_sha256':evidence['source_sha256'],'evidence_format':evidence['format'],
                          'reason':b['reason'],'state':'CANDIDATE_LINK'})
    return {'status':'PASS_WITH_QUARANTINE' if quarantine else 'PASS_TRACE_ONLY',
            'links':links,'quarantine':quarantine,
            'disclaimer':'Traceability links are candidate review objects, not contract compliance or engineering acceptance'}
