import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from cache_keys import make_cache_key
from gg_contract import from_path
from parity_gate import compare_graphs

BASE=from_path(Path(__file__).with_name("fixture_accepted_candidate.json"))


class ParityAndCacheTests(unittest.TestCase):
    def crossformat(self):
        a=deepcopy(BASE)
        a["source"]["sha256"]="b"*64
        a["source"]["locator"]="synthetic://slide-1.pptx"
        a["source"]["producer"]="pptx-existing-adapter"
        for node in a["nodes"]:
            node["source_object_id"]="pptx:"+node["id"]
        a["edges"][0]["evidence"]=[{"type":"PPTX_TAIL_END","locator":"pptx:slide-1:connector-9"}]
        a["edges"][0]["legend"]={"verified":True,"locator":"pptx:slide-1:legend-2"}
        return a

    def codes(self,after):
        return {x["code"] for x in compare_graphs(BASE,after)["findings"]}

    def test_same_semantics_with_distinct_format_locators_passes(self):
        self.assertEqual(compare_graphs(BASE,self.crossformat())["status"],"PASS_SEMANTIC_PARITY_ONLY")

    def test_reversed_direction_is_failed(self):
        a=self.crossformat();a["edges"][0]["direction"]="TARGET_TO_SOURCE"
        self.assertIn("K26_TOPOLOGY_DRIFT",self.codes(a))

    def test_lost_node_is_failed(self):
        a=self.crossformat();a["nodes"].pop()
        self.assertIn("K22_LOST_NODE",self.codes(a))

    def test_lost_edge_is_failed(self):
        a=self.crossformat();a["edges"].pop()
        self.assertIn("K24_LOST_EDGE",self.codes(a))

    def test_new_ghost_edge_is_failed(self):
        a=self.crossformat();e=deepcopy(a["edges"][0]);e["id"]="ghost";a["edges"].append(e)
        self.assertIn("K25_NEW_EDGE",self.codes(a))

    def test_changed_meaning_is_failed(self):
        a=self.crossformat();a["edges"][0]["relationship"]="SIGNAL"
        self.assertIn("K27_SEMANTIC_DRIFT",self.codes(a))

    def test_review_state_promotion_is_failed(self):
        a=self.crossformat();a["edges"][0]["state"]="GOLDEN"
        self.assertIn("K28_REVIEW_DRIFT",self.codes(a))

    def test_non_array_fields_fail_closed_without_traceback(self):
        for side in ("before", "after"):
            for field in ("nodes", "edges"):
                for bad in (None, "x", 5, {"id": "n1"}):
                    with self.subTest(side=side, field=field, value=bad):
                        a, b = deepcopy(BASE), self.crossformat()
                        (a if side == "before" else b)[field] = bad
                        r = compare_graphs(a, b)
                        self.assertEqual(r["status"], "FAIL_CLOSED")
                        self.assertIn("K21_SOURCE_CONTRACT", {x["code"] for x in r["findings"]})

    def test_malformed_documents_fail_closed_without_traceback(self):
        no_id = self.crossformat(); no_id["nodes"].append({"source_object_id": "pptx:x"})
        bad_source = self.crossformat(); bad_source["source"] = "not-an-object"
        for bad in ([], None, no_id, bad_source):
            with self.subTest(value=bad):
                self.assertEqual(compare_graphs(BASE, bad)["status"], "FAIL_CLOSED")

    def test_cli_writes_fail_closed_parity_receipt_for_null_edges(self):
        bad = self.crossformat(); bad["edges"] = None
        with tempfile.TemporaryDirectory() as tmp:
            before, after, out = (Path(tmp) / n for n in ("before.json", "after.json", "receipt.json"))
            before.write_text(json.dumps(BASE), encoding="utf-8")
            after.write_text(json.dumps(bad), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("parity_gate.py")),
                                   str(before), str(after), "--receipt", str(out)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["status"], "FAIL_CLOSED")

    def test_cache_key_deterministic(self):
        a=make_cache_key("a"*64,"svg-v1","b"*64)
        self.assertEqual(a,make_cache_key("a"*64,"svg-v1","b"*64))

    def test_cache_invalidates_on_source_change(self):
        self.assertNotEqual(make_cache_key("a"*64,"svg-v1","b"*64),make_cache_key("c"*64,"svg-v1","b"*64))

    def test_cache_invalidates_on_legend_change(self):
        self.assertNotEqual(make_cache_key("a"*64,"svg-v1","b"*64),make_cache_key("a"*64,"svg-v1","c"*64))

    def test_cache_invalidates_on_adapter_change(self):
        self.assertNotEqual(make_cache_key("a"*64,"svg-v1","b"*64),make_cache_key("a"*64,"svg-v2","b"*64))

    def test_missing_legend_hash_fails(self):
        with self.assertRaises(ValueError):
            make_cache_key("a"*64,"svg-v1","")


if __name__=="__main__":
    unittest.main()
