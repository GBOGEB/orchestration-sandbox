"""W12 offline HTML review regressions; no engineering authority inferred."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from viewer import render

SHA='a'*64
DOC={'contract_version':'gg-semantic-1.0','source':{'sha256':SHA},
     'nodes':[{'id':'node:P-101','label':'<script>alert(1)</script>','source_object_id':'svg:id-1'}],
     'edges':[]}
PARITY={'status':'PASS_SEMANTIC_PARITY_ONLY','nodes_before':1,'nodes_after':1,'edges_before':0,'edges_after':0,'findings':[]}


class ViewerTests(unittest.TestCase):
    def test_html_offline_and_interactive(self):
        x=render({'svg':DOC,'pptx':DOC},PARITY)
        self.assertIn('id="search"',x);self.assertIn('id="diagram"',x)
        self.assertIn('id="object-list"',x);self.assertIn('id="format"',x)
        self.assertNotIn('<script src=',x)

    def test_json_script_breakout_escaped(self):
        x=render({'svg':DOC,'pptx':DOC},PARITY)
        self.assertNotIn('<script>alert(1)</script>',x)
        self.assertIn('\\u003cscript\\u003e',x)

    def test_output_deterministic(self):
        self.assertEqual(render({'svg':DOC,'pptx':DOC},PARITY),render({'svg':DOC,'pptx':DOC},PARITY))

    def test_source_hash_present(self):
        self.assertIn(SHA,render({'svg':DOC,'pptx':DOC},PARITY))

    def test_source_schema_required(self):
        d=dict(DOC,contract_version='bad')
        with self.assertRaisesRegex(ValueError,'SCHEMA_MISMATCH'):render({'svg':d,'pptx':DOC},PARITY)

    def test_missing_source_hash_rejected(self):
        d=dict(DOC,source={})
        with self.assertRaisesRegex(ValueError,'SHA_MISSING'):render({'svg':d,'pptx':DOC},PARITY)

    def test_native_review_only_label(self):
        x=render({'svg':DOC,'pptx':DOC},PARITY)
        self.assertIn('not recovered native geometry',x)
        self.assertIn('NOT granted',x)

    def test_search_accessible(self):
        x=render({'svg':DOC,'pptx':DOC},PARITY)
        self.assertIn('aria-label="Filter semantic objects"',x)
        self.assertIn('role="region"',x)


if __name__=='__main__':unittest.main()
