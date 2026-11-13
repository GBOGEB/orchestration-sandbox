"""Independent read-only evidence ingress regressions, all synthetic bytes."""
import io
import struct
import sys
import unittest
import zlib
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent))
from evidence_ingress import (bind_explicit,read_docx,read_png,read_vsdx,read_xlsx,sha,
                             unzip_safe,parse_xml)


def packed(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for n,v in files.items():
            z.writestr(n,v)
    return out.getvalue()


def docx():
    return packed({'word/document.xml':'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>REQ-007 text</w:t></w:r></w:p><w:p><w:r><w:t>Action unresolved</w:t></w:r></w:p></w:body></w:document>'})


def xlsx():
    return packed({
     'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="RTM" sheetId="1" r:id="rId1"/></sheets></workbook>',
     'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="ignored"/></Relationships>',
     'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row><row r="2"><c r="A2" t="s"><v>0</v></c><c r="B2"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>',
     'xl/sharedStrings.xml':'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>REQ-007</t></si></sst>'})


def visio():
    return packed({'visio/pages/page1.xml':'<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main"><Shapes><Shape ID="7" NameU="Valve"/><Shape ID="8" NameU="Pump"/></Shapes></PageContents>'})


def png():
    def block(name,content):
        return struct.pack('>I',len(content))+name+content+struct.pack('>I',zlib.crc32(name+content)&0xffffffff)
    raw=b'\x00\xff\x00\x00\xff'
    return b'\x89PNG\r\n\x1a\n'+block(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+block(b'IDAT',zlib.compress(raw))+block(b'IEND',b'')


class EvidenceIngressTests(unittest.TestCase):
    def test_docx_source_verbatim(self):
        r=read_docx(docx());self.assertEqual(r['object_count'],2)
        self.assertEqual(r['objects'][0]['text'],'REQ-007 text')
        self.assertEqual(r['objects'][1]['semantic_id'],None)

    def test_docx_does_not_infer_requirements(self):
        r=read_docx(docx());self.assertTrue(all(x['classification']=='SOURCE_VERBATIM' for x in r['objects']))

    def test_docx_refuses_missing_member(self):
        with self.assertRaisesRegex(ValueError,'DOCUMENT_MISSING'):read_docx(packed({'word/foo.xml':'a'}))

    def test_xlsx_shared_strings_native_rows(self):
        r=read_xlsx(xlsx());self.assertEqual(r['object_count'],2)
        self.assertEqual(r['objects'][1]['cells']['A2'],'REQ-007')
        self.assertEqual(r['objects'][1]['source_object_id'],'xlsx:RTM:row:2')

    def test_xlsx_formula_not_silently_recalculated(self):
        r=read_xlsx(xlsx());self.assertEqual(r['objects'][1]['cells']['B2'],'FORMULA_NOT_RECALCULATED')
        self.assertEqual(r['objects'][1]['formulas']['B2'],'1+1')

    def test_xlsx_missing_native_sheet_blocked(self):
        d=packed({'xl/workbook.xml':'<workbook/>','xl/_rels/workbook.xml.rels':'<Relationships/>'})
        self.assertEqual(read_xlsx(d)['object_count'],0)

    def test_xlsx_duplicate_part_rejected(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('a','1');z.writestr('a','2')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_PART'):unzip_safe(buf.getvalue())

    def test_zip_path_traversal_refused(self):
        with self.assertRaisesRegex(ValueError,'UNSAFE_PART'):unzip_safe(packed({'../evil':'yes'}))

    def test_xml_dtd_refused(self):
        with self.assertRaisesRegex(ValueError,'UNSAFE'):parse_xml(b'<!DOCTYPE root [<!ENTITY x "abc">]><root/>')

    def test_visio_only_records_objects(self):
        r=read_vsdx(visio());self.assertEqual(r['object_count'],2)
        self.assertEqual(r['objects'][0]['direction'],'UNKNOWN')

    def test_visio_duplicate_native_id_blocked(self):
        v=visio();with_same=b'<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main"><Shapes><Shape ID="1"/><Shape ID="1"/></Shapes></PageContents>'
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SHAPE_ID'):
            read_vsdx(packed({'visio/pages/page1.xml':with_same}))

    def test_png_shape_not_semantics(self):
        r=read_png(png());self.assertEqual(r['objects'][0]['width_px'],1)
        self.assertEqual(r['objects'][0]['classification'],'RASTER_ONLY_NO_SEMANTIC_AUTHORITY')

    def test_png_invalid_refused(self):
        with self.assertRaisesRegex(ValueError,'PNG_INVALID'):read_png(b'not an image')

    def test_bound_explicit_accepted_as_candidate_only(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        a={'semantic_id':'node:REQ-007','source_object_id':'docx:paragraph:1',
           'source_sha256':e['source_sha256'],'reason':'review crosswalk','state':'CANDIDATE_LINK'}
        x=bind_explicit(g,e,[a]);self.assertEqual(x['status'],'PASS_TRACE_ONLY')
        self.assertEqual(x['links'][0]['state'],'CANDIDATE_LINK')

    def test_stale_sha_is_quarantined(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        a={'semantic_id':'node:REQ-007','source_object_id':'docx:paragraph:1',
           'source_sha256':'0'*64,'reason':'x','state':'CANDIDATE_LINK'}
        self.assertIn('STALE_EVIDENCE_SHA',bind_explicit(g,e,[a])['quarantine'][0]['reasons'])

    def test_fuzzy_text_never_auto_links(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        self.assertEqual(bind_explicit(g,e,[])['links'],[])

    def test_unknown_native_id_is_quarantined(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        a={'semantic_id':'node:REQ-007','source_object_id':'docx:paragraph:99',
           'source_sha256':e['source_sha256'],'reason':'x','state':'CANDIDATE_LINK'}
        self.assertIn('UNKNOWN_NATIVE_ID',bind_explicit(g,e,[a])['quarantine'][0]['reasons'])

    def test_authority_promotion_is_denied(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        a={'semantic_id':'node:REQ-007','source_object_id':'docx:paragraph:1',
           'source_sha256':e['source_sha256'],'reason':'x','state':'GOLDEN'}
        self.assertIn('UNAUTHORIZED_LINK_PROMOTION',bind_explicit(g,e,[a])['quarantine'][0]['reasons'])

    def test_duplicate_explicit_link_quarantined(self):
        e=read_docx(docx());g={'nodes':[{'id':'node:REQ-007'}],'edges':[]}
        a={'semantic_id':'node:REQ-007','source_object_id':'docx:paragraph:1',
           'source_sha256':e['source_sha256'],'reason':'x','state':'CANDIDATE_LINK'}
        self.assertIn('DUPLICATE_BINDING',bind_explicit(g,e,[a,a])['quarantine'][0]['reasons'])


if __name__=='__main__':unittest.main()
