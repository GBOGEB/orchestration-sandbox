"""W11 PPTX native adapter tests (synthetic OOXML only; not engineering evidence)."""
import unittest

import synthetic_fixtures as fx
from native_common import AdapterInputError
from pptx_adapter import read_pptx
from w10_bridge import receipt


def only_edge(doc):
    assert len(doc["edges"]) == 1, doc["edges"]
    return doc["edges"][0]


def evidence_types(edge):
    return {e["type"] for e in edge["evidence"]}


class PptxNativeAdapterTests(unittest.TestCase):
    def test_tail_arrow_anchored_connector_is_candidate_source_to_target(self):
        doc = read_pptx(fx.pptx_flow(), name="flow.pptx")
        edge = only_edge(doc)
        self.assertEqual((edge["source_id"], edge["target_id"]), ("node:P-101", "node:HX-201"))
        self.assertEqual((edge["state"], edge["direction"]), ("CANDIDATE", "SOURCE_TO_TARGET"))
        self.assertEqual(edge["native"]["orientation"], "AS_DRAWN")
        self.assertIn("PPTX_TAIL_END", evidence_types(edge))
        self.assertEqual(sum(e["type"] == "PPTX_CONNECTOR_ANCHOR" for e in edge["evidence"]), 2)
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_head_arrow_is_reoriented_not_guessed(self):
        edge = only_edge(read_pptx(fx.pptx_flow(reverse_drawing=True)))
        self.assertEqual((edge["source_id"], edge["target_id"]), ("node:P-101", "node:HX-201"))
        self.assertEqual(edge["direction"], "SOURCE_TO_TARGET")
        self.assertEqual(edge["native"]["orientation"], "REVERSED_FROM_DRAWING")
        self.assertIn("PPTX_HEAD_END", evidence_types(edge))

    def test_both_arrowheads_are_bidirectional_with_sorted_endpoints(self):
        edge = only_edge(read_pptx(fx.pptx_flow(head="stealth", tail="arrow")))
        self.assertEqual(edge["direction"], "BIDIRECTIONAL")
        self.assertEqual([edge["source_id"], edge["target_id"]], sorted([edge["source_id"], edge["target_id"]]))

    def test_no_arrowhead_keeps_direction_unknown_and_drawing_order_out(self):
        forward = only_edge(read_pptx(fx.pptx_flow(tail=None)))
        backward = only_edge(read_pptx(fx.pptx_flow(reverse_drawing=True, head=None)))
        self.assertEqual(forward["direction"], "UNKNOWN")
        self.assertEqual(forward["state"], "CANDIDATE")
        self.assertEqual((forward["source_id"], forward["target_id"]), (backward["source_id"], backward["target_id"]))

    def test_oval_and_diamond_ends_are_not_direction_proof(self):
        doc = read_pptx(fx.pptx_flow(head="oval", tail="diamond"))
        edge = only_edge(doc)
        self.assertEqual(edge["direction"], "UNKNOWN")
        self.assertEqual(evidence_types(edge), {"PPTX_CONNECTOR_ANCHOR", "PPTX_LINE_END_NON_ARROW"})
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_unbound_end_is_quarantined_not_inferred(self):
        doc = read_pptx(fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "HX-201"),
                                       fx.connector(9, "flow-001", 4, None, tail="triangle")]))
        self.assertEqual(doc["edges"], [])
        self.assertEqual(doc["nodes"], [])
        self.assertIn("a:endCxn missing", doc["quarantine"][0]["reason"])
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_binding_to_missing_shape_is_quarantined(self):
        doc = read_pptx(fx.pptx_bytes([fx.shape(4, "P-101"), fx.connector(9, "flow-001", 4, 77, tail="triangle")]))
        self.assertEqual(doc["edges"], [])
        self.assertIn("'77'", doc["quarantine"][0]["reason"])

    def test_self_loop_is_quarantined(self):
        doc = read_pptx(fx.pptx_bytes([fx.shape(4, "P-101"), fx.connector(9, "loop", 4, 4, tail="triangle")]))
        self.assertEqual(doc["edges"], [])
        self.assertIn("self-loop", doc["quarantine"][0]["reason"])

    def test_theme_inherited_arrowhead_is_resolved_with_theme_locator(self):
        lines = [fx.PLAIN_THEME_LINE,
                 '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:tailEnd type="triangle"/></a:ln>',
                 fx.PLAIN_THEME_LINE]
        data = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "HX-201"),
                              fx.connector(9, "flow-001", 4, 5, explicit_line=False, style_idx=2)], theme_lines=lines)
        edge = only_edge(read_pptx(data))
        self.assertEqual(edge["direction"], "SOURCE_TO_TARGET")
        tail = [e for e in edge["evidence"] if e["type"] == "PPTX_TAIL_END"][0]
        self.assertTrue(tail["locator"].startswith("pptx:ppt/theme/theme1.xml#"))

    def test_unresolvable_theme_inheritance_is_unresolved(self):
        data = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "HX-201"),
                              fx.connector(9, "flow-001", 4, 5, explicit_line=False)], include_theme=False)
        doc = read_pptx(data)
        edge = only_edge(doc)
        self.assertEqual((edge["state"], edge["direction"]), ("UNRESOLVED", "UNKNOWN"))
        self.assertIn("theme line style 1", edge["unresolved_reason"])
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_invisible_or_hidden_connector_is_unresolved(self):
        for kw, reason in (({"no_fill": True}, "a:noFill"), ({"hidden": True}, "hidden")):
            with self.subTest(kw=kw):
                edge = only_edge(read_pptx(fx.pptx_flow(**kw)))
                self.assertEqual((edge["state"], edge["direction"]), ("UNRESOLVED", "UNKNOWN"))
                self.assertIn(reason, edge["unresolved_reason"])

    def test_flip_is_recorded_but_does_not_change_direction(self):
        plain = only_edge(read_pptx(fx.pptx_flow()))
        flipped = only_edge(read_pptx(fx.pptx_flow(flip_h=True)))
        self.assertEqual(flipped["native"]["xfrm"].get("flipH"), "1")
        for key in ("source_id", "target_id", "direction", "state"):
            self.assertEqual(plain[key], flipped[key])

    def test_grouped_endpoint_keeps_group_path(self):
        data = fx.pptx_bytes([fx.group(20, "Skid A", [fx.shape(4, "P-101")]), fx.shape(5, "HX-201"),
                              fx.connector(9, "flow-001", 4, 5, tail="triangle")])
        doc = read_pptx(data)
        node = [n for n in doc["nodes"] if n["id"] == "node:P-101"][0]
        self.assertEqual(node["native"]["group_path"][0]["name"], "Skid A")
        self.assertEqual(node["native"]["group_path"][0]["xfrm"]["rot"], "5400000")

    def test_hidden_group_hides_endpoint(self):
        data = fx.pptx_bytes([fx.group(20, "Skid A", [fx.shape(4, "P-101")], hidden=True), fx.shape(5, "HX-201"),
                              fx.connector(9, "flow-001", 4, 5, tail="triangle")])
        edge = only_edge(read_pptx(data))
        self.assertEqual(edge["state"], "UNRESOLVED")
        self.assertIn("endpoint shape is hidden", edge["unresolved_reason"])

    def test_duplicate_shape_names_fail_closed_at_w10(self):
        data = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(5, "P-101"),
                              fx.connector(9, "flow-001", 4, 5, tail="triangle")])
        doc = read_pptx(data)
        self.assertIn("A02_DUPLICATE_TAG", {f["code"] for f in doc["adapter"]["findings"]})
        result = receipt(doc)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("K04_DUPLICATE_NODE", {f["code"] for f in result["findings"]})

    def test_duplicate_native_ids_are_never_bound(self):
        data = fx.pptx_bytes([fx.shape(4, "P-101"), fx.shape(4, "Ghost"), fx.shape(5, "HX-201"),
                              fx.connector(9, "flow-001", 4, 5, tail="triangle")])
        doc = read_pptx(data)
        self.assertEqual(doc["edges"], [])
        self.assertIn("A01_NATIVE_ID", {f["code"] for f in doc["adapter"]["findings"]})
        self.assertIn("missing or duplicated", doc["quarantine"][0]["reason"])

    def test_untagged_shape_gets_native_only_identity(self):
        data = fx.pptx_bytes([fx.shape(4, ""), fx.shape(5, "HX-201"), fx.connector(9, "", 4, 5, tail="triangle")])
        doc = read_pptx(data)
        self.assertIn("native:pptx:s1:4", {n["id"] for n in doc["nodes"]})
        self.assertEqual(only_edge(doc)["id"], "edge:native:pptx:s1:9")

    def test_slide_selection_and_bounds(self):
        data = fx.pptx_bytes([fx.shape(1, "x")], [fx.shape(4, "P-101"), fx.shape(5, "HX-201"),
                                                  fx.connector(9, "flow-001", 4, 5, tail="triangle")])
        self.assertEqual(read_pptx(data, slide=1)["edges"], [])
        self.assertEqual(only_edge(read_pptx(data, slide=2))["id"], "edge:flow-001")
        with self.assertRaises(AdapterInputError):
            read_pptx(data, slide=3)

    def test_unsafe_or_malformed_packages_are_refused(self):
        dtd = '<?xml version="1.0"?><!DOCTYPE p:sld [<!ENTITY x "y">]><p:sld/>'
        cases = {
            "not a zip": b"not a zip",
            "dtd in slide": fx.pptx_bytes([], extra={"ppt/slides/slide1.xml": dtd}),
            "strict ooxml": fx.pptx_bytes([], extra={"ppt/presentation.xml": '<presentation xmlns="urn:strict"/>'}),
        }
        for label, data in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(AdapterInputError):
                    read_pptx(data)

    def test_source_binding_uses_file_sha_and_basename_only(self):
        data = fx.pptx_flow()
        doc = read_pptx(data, name="C:/private/folder/flow.pptx")
        self.assertEqual(doc["source"]["sha256"], fx.sha256(data))
        self.assertEqual(doc["source"]["locator"], "native-pptx://flow.pptx#slide=1")


if __name__ == "__main__":
    unittest.main()
