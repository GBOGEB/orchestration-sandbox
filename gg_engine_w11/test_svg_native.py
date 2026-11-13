"""W11 SVG native adapter tests (synthetic SVG only; not engineering evidence)."""
import unittest

import synthetic_fixtures as fx
from native_common import AdapterInputError
from svg_adapter import read_svg
from w10_bridge import receipt


def only_edge(doc):
    assert len(doc["edges"]) == 1, doc["edges"]
    return doc["edges"][0]


def codes(doc):
    return {f["code"] for f in doc["adapter"]["findings"]}


class SvgNativeAdapterTests(unittest.TestCase):
    def test_marker_without_legend_keeps_direction_unknown(self):
        doc = read_svg(fx.svg_flow())
        edge = only_edge(doc)
        self.assertEqual((edge["state"], edge["direction"]), ("CANDIDATE", "UNKNOWN"))
        self.assertIn("SVG_MARKER_UNCLASSIFIED", {e["type"] for e in edge["evidence"]})
        self.assertIn("A05_MARKER_UNCLASSIFIED", codes(doc))
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_legend_classified_end_marker_orients_edge(self):
        data = fx.svg_flow()
        doc = read_svg(data, legend=fx.svg_legend(data))
        edge = only_edge(doc)
        self.assertEqual((edge["source_id"], edge["target_id"]), ("node:P-101", "node:HX-201"))
        self.assertEqual((edge["direction"], edge["relationship"]), ("SOURCE_TO_TARGET", "FLOW"))
        self.assertEqual(edge["legend"]["locator"], "svg:legend-001")
        self.assertIn("SVG_MARKER_END", {e["type"] for e in edge["evidence"]})
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_start_marker_is_reoriented(self):
        data = fx.svg_flow(reverse_drawing=True)
        edge = only_edge(read_svg(data, legend=fx.svg_legend(data)))
        self.assertEqual((edge["source_id"], edge["target_id"]), ("node:P-101", "node:HX-201"))
        self.assertEqual(edge["native"]["orientation"], "REVERSED_FROM_DRAWING")

    def test_marker_not_classified_as_arrowhead_is_not_direction_proof(self):
        data = fx.svg_flow(marker_end="Dot")
        edge = only_edge(read_svg(data, legend=fx.svg_legend(data)))
        self.assertEqual(edge["direction"], "UNKNOWN")

    def test_unbound_connector_is_quarantined_not_inferred_by_proximity(self):
        data = fx.svg_doc(fx.svg_shape("p101", "P-101"), fx.svg_shape("hx201", "HX-201"),
                          fx.svg_connector("flow001", "flow-001", "p101", None, marker_end="ArrowEnd"))
        doc = read_svg(data, legend=fx.svg_legend(data))
        self.assertEqual(doc["edges"], [])
        self.assertIn("connection-end missing", doc["quarantine"][0]["reason"])

    def test_stylesheet_makes_connectors_unresolved(self):
        data = fx.svg_doc(fx.svg_shape("p101", "P-101"), fx.svg_shape("hx201", "HX-201"),
                          fx.svg_connector("flow001", "flow-001", "p101", "hx201", marker_end="ArrowEnd"),
                          stylesheet="path { marker-end: none; }")
        doc = read_svg(data, legend=fx.svg_legend(data))
        edge = only_edge(doc)
        self.assertEqual((edge["state"], edge["direction"], edge["relationship"]), ("UNRESOLVED", "UNKNOWN", "UNKNOWN"))
        self.assertIn("A04_STYLESHEET", codes(doc))
        self.assertEqual(receipt(doc)["status"], "PASS_CONTRACT_ONLY")

    def test_hidden_layer_and_invisible_stroke_are_unresolved(self):
        cases = {
            "hidden layer": fx.svg_flow(layer_style="display:none"),
            "no stroke": fx.svg_flow(stroke="none"),
            "zero stroke opacity": fx.svg_flow(extra_style="stroke-opacity:0"),
        }
        for label, data in cases.items():
            with self.subTest(label=label):
                edge = only_edge(read_svg(data, legend=fx.svg_legend(data)))
                self.assertEqual((edge["state"], edge["direction"]), ("UNRESOLVED", "UNKNOWN"))

    def test_marker_inherited_from_group_is_read(self):
        data = fx.svg_doc(fx.svg_shape("p101", "P-101"), fx.svg_shape("hx201", "HX-201"),
                          '<g id="wrap" style="marker-end:url(#ArrowEnd)">'
                          + fx.svg_connector("flow001", "flow-001", "p101", "hx201") + "</g>")
        edge = only_edge(read_svg(data, legend=fx.svg_legend(data)))
        self.assertEqual(edge["direction"], "SOURCE_TO_TARGET")

    def test_arrowhead_on_marker_mid_is_unresolved(self):
        data = fx.svg_flow(marker_end=None, extra_style="marker-mid:url(#ArrowEnd)")
        edge = only_edge(read_svg(data, legend=fx.svg_legend(data)))
        self.assertEqual(edge["state"], "UNRESOLVED")
        self.assertIn("marker-mid", edge["unresolved_reason"])

    def test_layers_and_transforms_are_preserved(self):
        doc = read_svg(fx.svg_flow())
        node = [n for n in doc["nodes"] if n["id"] == "node:P-101"][0]
        self.assertEqual(node["native"]["layers"], [{"id": "layer1", "label": "Process"}])
        self.assertEqual([t["transform"] for t in node["native"]["transforms"]], ["translate(10,0)", "translate(0,40)"])
        self.assertEqual(node["label"], "P-101")
        self.assertEqual(only_edge(doc)["native"]["layers"][0]["label"], "Process")

    def test_label_and_title_disagreement_is_ambiguous(self):
        data = fx.svg_doc(fx.svg_shape("p101", "P-101", title="P-102"), fx.svg_shape("hx201", "HX-201"),
                          fx.svg_connector("flow001", "flow-001", "p101", "hx201"))
        doc = read_svg(data)
        node = [n for n in doc["nodes"] if n["source_object_id"] == "svg:p101"][0]
        self.assertEqual((node["id"], node["identity"]), ("native:svg:p101", "AMBIGUOUS_TAG"))
        self.assertIn("A03_AMBIGUOUS_TAG", codes(doc))

    def test_duplicate_element_ids_are_never_bound(self):
        data = fx.svg_doc(fx.svg_shape("p101", "P-101"), fx.svg_shape("p101", "Ghost"), fx.svg_shape("hx201", "HX-201"),
                          fx.svg_connector("flow001", "flow-001", "p101", "hx201"))
        doc = read_svg(data)
        self.assertEqual(doc["edges"], [])
        self.assertIn("A01_NATIVE_ID", codes(doc))

    def test_unsafe_or_wrong_documents_are_refused(self):
        cases = {
            "entity expansion": b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]><svg>&a;</svg>',
            "utf-16": '<svg xmlns="http://www.w3.org/2000/svg"/>'.encode("utf-16"),
            "not svg": b"<html/>",
            "not xml": b"<svg",
        }
        for label, data in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(AdapterInputError):
                    read_svg(data)


if __name__ == "__main__":
    unittest.main()
