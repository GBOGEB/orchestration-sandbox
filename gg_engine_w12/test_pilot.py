"""W12 author integration assertions; native binary source is SYNTHETIC ONLY."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import pilot
from pilot import emit_pptx,emit_svg,run,supported_flow,archive
from w10_bridge import compare_graphs
from svg_adapter import read_svg
from pptx_adapter import read_pptx
import synthetic_fixtures as fx


def initial():
    data=fx.svg_flow()
    return read_svg(data,legend=fx.svg_legend(data))


class RoundtripTests(unittest.TestCase):
    def test_svg_to_pptx_back_to_svg_parity(self):
        src=initial()
        pptx=emit_pptx(src)
        back=read_pptx(pptx,legend=fx.pptx_legend(pptx))
        self.assertEqual(compare_graphs(src,back)['status'],'PASS_SEMANTIC_PARITY_ONLY')
        new_svg=emit_svg(back)
        rev=read_svg(new_svg,legend=fx.svg_legend(new_svg))
        self.assertEqual(compare_graphs(back,rev)['status'],'PASS_SEMANTIC_PARITY_ONLY')

    def test_no_production_emitter_for_unresolved(self):
        d=initial();d['edges'][0]['state']='UNRESOLVED';d['edges'][0]['direction']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'EMITTER_UNSUPPORTED'):supported_flow(d)

    def test_no_production_emitter_for_extra_edge(self):
        d=initial();d['edges'].append(deepcopy(d['edges'][0]))
        with self.assertRaisesRegex(ValueError,'EMITTER_UNSUPPORTED'):emit_pptx(d)

    def test_quarantined_edge_blocks_emission(self):
        d=initial();d['quarantine']=[{'reason':'source ambiguity'}]
        with self.assertRaisesRegex(ValueError,'EMITTER_UNSUPPORTED'):emit_svg(d)

    def test_source_bytes_stored_and_no_golden(self):
        with tempfile.TemporaryDirectory() as t:
            x=run(t)
            self.assertEqual(x['graph_source_to_pptx'],'PASS_SEMANTIC_PARITY_ONLY')
            self.assertEqual(x['graph_pptx_to_svg'],'PASS_SEMANTIC_PARITY_ONLY')
            self.assertEqual(x['owner_acceptance'],'HOLD')
            self.assertEqual(x['dow'],'DEFERRED_NOT_INSTALLED')
            self.assertEqual(json.loads((Path(t)/'roundtrip_claim.json').read_text())['edges'][0]['state'],'CANDIDATE')
            with zipfile.ZipFile(Path(t)/'from_svg.pptx') as z:
                self.assertIn('ppt/slides/slide1.xml',z.namelist())

    def test_layout_keeps_semantic_native_ids_with_readable_positions(self):
        from xml.etree import ElementTree as ET
        from zipfile import ZipFile
        from io import BytesIO
        source = pilot._layout_svg(fx.svg_flow())
        self.assertIn(b'id="layer1"', source)
        self.assertIn(b'id="layer2"', source)
        self.assertIn(b'inkscape:connection-start="#p101"', source)
        self.assertIn(b'inkscape:connection-end="#hx201"', source)
        self.assertIn(b'd="M 125,65 L 275,65"', source)
        self.assertIn(b'transform="translate(20,135)"', source)
        self.assertIn(b'font-family="DejaVu Sans"', source)
        out = emit_pptx(initial())
        with ZipFile(BytesIO(out)) as z:
            slide = ET.fromstring(z.read('ppt/slides/slide1.xml'))
        ns = {'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
              'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        where = {}
        for element in slide.findall('.//p:sp', ns):
            native = element.find('p:nvSpPr/p:cNvPr', ns)
            if native is None:continue
            off = element.find('p:spPr/a:xfrm/a:off',ns)
            ext = element.find('p:spPr/a:xfrm/a:ext',ns)
            where[native.get('id')] = (int(off.get('x')), int(off.get('y')),
                                      int(ext.get('cx')), int(ext.get('cy')))
        self.assertEqual(len(where), 3)
        self.assertEqual(where['4'], (1000000,2100000,1600000,750000))
        self.assertEqual(where['5'], (6000000,2100000,2000000,750000))
        self.assertEqual(where['12'],(1000000,4500000,3800000,850000))
        self.assertGreater(where['5'][0], where['4'][0]+where['4'][2])
        self.assertGreater(where['12'][1], where['4'][1]+where['4'][3])
        self.assertEqual(read_pptx(out,legend=fx.pptx_legend(out))['edges'][0]['state'], 'CANDIDATE')

    def test_layout_fixture_drift_refused(self):
        with self.assertRaisesRegex(ValueError,'SYNTHETIC_FIXTURE_LAYOUT_DRIFT'):
            pilot._layout_svg(b'<svg/>')

    def test_deterministic_zip_rebuild(self):
        with tempfile.TemporaryDirectory() as t:
            run(t)
            a=hashlib.sha256((Path(t)/'gg_engine_w12_demo.zip').read_bytes()).hexdigest()
            b=archive(t,Path(t)/'gg_engine_w12_demo.zip')['zip_sha256']
            self.assertEqual(a,b)
            with zipfile.ZipFile(Path(t)/'gg_engine_w12_demo.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertIn('index.html',z.namelist())

    def test_negative_reversed_native_arrow_does_not_pass(self):
        src=initial()
        pptx=fx.pptx_flow(head='triangle',tail=None)
        altered=read_pptx(pptx,legend=fx.pptx_legend(pptx))
        self.assertEqual(compare_graphs(src,altered)['status'],'FAIL_CLOSED')

    def test_stale_legend_is_not_applied(self):
        src=initial()
        pptx=fx.pptx_flow()
        stale=fx.pptx_legend(pptx)
        stale['source_sha256']='0'*64
        parsed=read_pptx(pptx,legend=stale)
        self.assertEqual(parsed['adapter']['legend']['status'],'REJECTED')
        self.assertEqual(parsed['edges'][0]['relationship'],'UNKNOWN')

    def test_missing_dow_checkout_is_rejected(self):
        from dow_bridge import verify_checkout
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'DOW_ENGINE_MISSING'):verify_checkout(t)


if __name__=='__main__':unittest.main()
