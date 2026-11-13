"""W11 integration: schema pin, legend authority, cross-format parity, determinism, CLI.

Every result here is synthetic. A PASS means the adapters and the reused W10
gates agree on synthetic inputs; it is not engineering acceptance.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from pathlib import Path

import pptx_adapter
import schema_pin
import svg_adapter
import synthetic_fixtures as fx
from native_common import NO_LEGEND_SHA256, QUALIFICATION
from pptx_adapter import read_pptx
from svg_adapter import read_svg
from w10_bridge import compare_graphs, receipt


class SchemaPinTests(unittest.TestCase):
    def test_current_w10_vocabulary_matches_pin(self):
        self.assertEqual(schema_pin.assert_schema_pinned(), schema_pin.PINNED_SCHEMA_SHA256)

    def test_vocabulary_drift_is_refused(self):
        vocab = schema_pin.schema_vocabulary()
        vocab["relationships"] = vocab["relationships"] + ["HYDRAULIC"]
        with self.assertRaises(schema_pin.SchemaDrift):
            schema_pin.assert_schema_pinned(vocab)

    def test_both_adapters_record_the_pin(self):
        for doc in (read_pptx(fx.pptx_flow()), read_svg(fx.svg_flow())):
            self.assertEqual(doc["adapter"]["schema_sha256"], schema_pin.PINNED_SCHEMA_SHA256)


class LegendAuthorityTests(unittest.TestCase):
    def test_no_legend_means_no_relationship(self):
        doc = read_pptx(fx.pptx_flow())
        self.assertEqual(doc["edges"][0]["relationship"], "UNKNOWN")
        self.assertEqual(doc["adapter"]["legend"], {"status": "ABSENT", "sha256": NO_LEGEND_SHA256, "findings": []})

    def test_verified_bound_legend_assigns_relationship(self):
        data = fx.pptx_flow()
        edge = read_pptx(data, legend=fx.pptx_legend(data))["edges"][0]
        self.assertEqual(edge["relationship"], "FLOW")
        self.assertEqual(edge["legend"]["locator"], "pptx:s1:12")

    def test_rejected_legends_never_apply(self):
        data = fx.pptx_flow()
        cases = {
            "L03_STALE_LEGEND": fx.pptx_legend(fx.pptx_flow(color="FF0000")),
            "L04_UNVERIFIED": fx.pptx_legend(data, verified=False),
            "L05_LEGEND_OBJECT": fx.pptx_legend(data, legend_object_id="pptx:s1:99"),
            "L02_FORMAT": fx.pptx_legend(data, format="svg"),
            "L07_MARKERS": fx.pptx_legend(data, arrowhead_markers=["ArrowEnd"]),
            "L06_RULE": fx.pptx_legend(data, relationships=[{"match": {}, "relationship": "FLOW"}]),
        }
        for code, legend in cases.items():
            with self.subTest(code=code):
                doc = read_pptx(data, legend=legend)
                self.assertEqual(doc["adapter"]["legend"]["status"], "REJECTED")
                self.assertIn(code, {f["code"] for f in doc["adapter"]["legend"]["findings"]})
                self.assertEqual(doc["edges"][0]["relationship"], "UNKNOWN")
                self.assertNotIn("legend", doc["edges"][0])

    def test_missing_owner_fields_are_unverified(self):
        data = fx.pptx_flow()
        legend = fx.pptx_legend(data)
        del legend["decision_id"]
        doc = read_pptx(data, legend=legend)
        self.assertIn("L04_UNVERIFIED", {f["code"] for f in doc["adapter"]["legend"]["findings"]})

    def test_conflicting_legend_rules_are_unresolved(self):
        data = fx.pptx_flow()
        legend = fx.pptx_legend(data, relationships=[
            {"match": {"line_color": "srgb:0000FF"}, "relationship": "FLOW"},
            {"match": {"line_dash": "INHERITED"}, "relationship": "SIGNAL"},
        ])
        edge = read_pptx(data, legend=legend)["edges"][0]
        self.assertEqual((edge["state"], edge["relationship"]), ("UNRESOLVED", "UNKNOWN"))
        self.assertIn("legend rules disagree", edge["unresolved_reason"])

    def test_adapters_never_promote_authority(self):
        pptx = fx.pptx_flow()
        svg = fx.svg_flow()
        docs = [read_pptx(pptx), read_pptx(pptx, legend=fx.pptx_legend(pptx)),
                read_svg(svg), read_svg(svg, legend=fx.svg_legend(svg))]
        for doc in docs:
            self.assertTrue({e["state"] for e in doc["edges"]} <= {"CANDIDATE", "UNRESOLVED"})
            self.assertTrue(all("approval" not in e for e in doc["edges"]))
            self.assertEqual(doc["adapter"]["qualification"], QUALIFICATION)
            self.assertEqual(doc["adapter"]["qualification"]["owner_acceptance"], "HOLD")


class CrossFormatParityTests(unittest.TestCase):
    def pair(self, **pptx_kw):
        svg = fx.svg_flow()
        pptx = fx.pptx_flow(**pptx_kw)
        return read_svg(svg, legend=fx.svg_legend(svg)), read_pptx(pptx, legend=fx.pptx_legend(pptx))

    def test_same_meaning_drawn_in_opposite_order_passes_w10_parity(self):
        svg_doc, pptx_doc = self.pair(reverse_drawing=True)
        self.assertEqual(receipt(svg_doc)["status"], "PASS_CONTRACT_ONLY")
        self.assertEqual(receipt(pptx_doc)["status"], "PASS_CONTRACT_ONLY")
        result = compare_graphs(svg_doc, pptx_doc)
        self.assertEqual(result["status"], "PASS_SEMANTIC_PARITY_ONLY", result["findings"])
        self.assertNotEqual(result["before_source_sha256"], result["after_source_sha256"])

    def test_reversed_arrow_fails_w10_parity(self):
        svg_doc, pptx_doc = self.pair(tail=None, head="triangle")
        result = compare_graphs(svg_doc, pptx_doc)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("K26_TOPOLOGY_DRIFT", {f["code"] for f in result["findings"]})

    def test_relationship_drift_fails_w10_parity(self):
        svg = fx.svg_flow()
        pptx = fx.pptx_flow()
        legend = fx.pptx_legend(pptx, relationships=[{"match": {"line_color": "srgb:0000FF"}, "relationship": "SIGNAL"}])
        result = compare_graphs(read_svg(svg, legend=fx.svg_legend(svg)), read_pptx(pptx, legend=legend))
        self.assertIn("K27_SEMANTIC_DRIFT", {f["code"] for f in result["findings"]})

    def test_lost_connector_fails_w10_parity(self):
        svg_doc, _ = self.pair()
        data = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "HX-201"), fx.shape(12, "Legend")])
        result = compare_graphs(svg_doc, read_pptx(data))
        self.assertIn("K24_LOST_EDGE", {f["code"] for f in result["findings"]})


class DeterminismAndCacheTests(unittest.TestCase):
    def test_output_is_byte_identical_across_runs(self):
        pptx, svg = fx.pptx_flow(), fx.svg_flow()
        for read, data in ((read_pptx, pptx), (read_svg, svg)):
            first = json.dumps(read(data), sort_keys=True)
            second = json.dumps(read(deepcopy(data)), sort_keys=True)
            self.assertEqual(first, second)

    def test_cache_key_binds_source_legend_and_adapter(self):
        data = fx.pptx_flow()
        base = read_pptx(data)["adapter"]["cache_key"]
        self.assertNotEqual(base, read_pptx(fx.pptx_flow(color="FF0000"))["adapter"]["cache_key"])
        self.assertNotEqual(base, read_pptx(data, legend=fx.pptx_legend(data))["adapter"]["cache_key"])
        original = pptx_adapter.ADAPTER_VERSION
        try:
            pptx_adapter.ADAPTER_VERSION = "0.1.1"
            self.assertNotEqual(base, read_pptx(data)["adapter"]["cache_key"])
        finally:
            pptx_adapter.ADAPTER_VERSION = original


class CliTests(unittest.TestCase):
    def test_cli_writes_manifest_and_w10_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "flow.pptx").write_bytes(fx.pptx_flow())
            (tmp / "flow.svg").write_bytes(fx.svg_flow())
            code = pptx_adapter.main([str(tmp / "flow.pptx"), "--out", str(tmp / "p.json"),
                                      "--contract-receipt", str(tmp / "p_receipt.json")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((tmp / "p_receipt.json").read_text(encoding="utf-8"))["status"], "PASS_CONTRACT_ONLY")
            code = svg_adapter.main([str(tmp / "flow.svg"), "--out", str(tmp / "s.json")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((tmp / "s.json").read_text(encoding="utf-8"))["source"]["locator"],
                             "native-svg://flow.svg")

    def test_cli_exit_codes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dup = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "P-101"),
                                 fx.connector(9, "flow-001", 4, 5, tail="triangle")])
            (tmp / "dup.pptx").write_bytes(dup)
            (tmp / "bad.svg").write_bytes(b'<!DOCTYPE svg [<!ENTITY a "b">]><svg/>')
            self.assertEqual(pptx_adapter.main([str(tmp / "dup.pptx"), "--out", str(tmp / "d.json"),
                                                "--contract-receipt", str(tmp / "d_receipt.json")]), 1)
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(svg_adapter.main([str(tmp / "bad.svg")]), 2)
            self.assertEqual(json.loads(err.getvalue())["status"], "INPUT_REFUSED")
            self.assertNotIn(str(tmp), err.getvalue())


if __name__ == "__main__":
    unittest.main()
