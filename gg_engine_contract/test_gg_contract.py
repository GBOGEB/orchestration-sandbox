from copy import deepcopy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from gg_contract import from_path, validate_manifest, validate_worker_dag, receipt

ROOT = Path(__file__).resolve().parent
BASE = from_path(ROOT / "fixture_accepted_candidate.json")


def errors(doc):
    return {f.code for f in validate_manifest(doc)}


class ContractNegativeTests(unittest.TestCase):
    def test_verified_candidate_passes(self):
        self.assertEqual(errors(BASE), set())
        self.assertEqual(receipt(BASE)["status"], "PASS_CONTRACT_ONLY")

    def test_bad_source_sha_rejected(self):
        d = deepcopy(BASE); d["source"]["sha256"] = "abc"
        self.assertIn("K02_SOURCE", errors(d))

    def test_duplicate_node_rejected(self):
        d = deepcopy(BASE); d["nodes"].append(deepcopy(d["nodes"][0]))
        self.assertIn("K04_DUPLICATE_NODE", errors(d))

    def test_missing_endpoint_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["target_id"] = "missing"
        self.assertIn("K07_ENDPOINTS", errors(d))

    def test_neighbour_order_not_arrowhead(self):
        d = deepcopy(BASE); d["edges"][0]["evidence"] = [{"type":"NEIGHBOR_ORDER", "locator":"pptx:shape-3"}]
        self.assertIn("K12_DIRECTION_PROOF", errors(d))

    def test_geometry_only_not_arrowhead(self):
        d = deepcopy(BASE); d["edges"][0]["evidence"] = [{"type":"GEOMETRY_ONLY", "locator":"slide:7"}]
        self.assertIn("K12_DIRECTION_PROOF", errors(d))

    def test_no_anchor_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["explicit_endpoints"] = False
        self.assertIn("K13_ANCHOR", errors(d))

    def test_arrowhead_without_legend_cannot_claim_flow(self):
        d = deepcopy(BASE); d["edges"][0]["legend"] = {"verified": False}
        self.assertIn("K15_LEGEND", errors(d))

    def test_relationship_unknown_does_not_require_legend(self):
        d = deepcopy(BASE); d["edges"][0]["relationship"] = "UNKNOWN"; d["edges"][0].pop("legend")
        self.assertEqual(errors(d), set())

    def test_golden_requires_owner_decision(self):
        d = deepcopy(BASE); d["edges"][0]["state"] = "GOLDEN"
        self.assertIn("K16_AUTHORITY", errors(d))

    def test_stale_approval_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["state"] = "GOLDEN"
        d["edges"][0]["approval"] = {"decision_id":"D-1", "authority":"owner", "approved_at":"2026-11-12", "source_sha256":"b"*64}
        self.assertIn("K17_STALE_APPROVAL", errors(d))

    def test_source_bound_approval_contract_passes(self):
        d = deepcopy(BASE); d["edges"][0]["state"] = "GOLDEN"
        d["edges"][0]["approval"] = {"decision_id":"TEST-ONLY", "authority":"synthetic-owner", "approved_at":"2026-11-12", "source_sha256":"a"*64}
        self.assertEqual(errors(d), set())

    def test_unresolved_preserved(self):
        d = deepcopy(BASE); e = d["edges"][0]
        e["state"] = "UNRESOLVED"; e["direction"] = "UNKNOWN"; e["relationship"] = "UNKNOWN"
        e["evidence"] = []; e["explicit_endpoints"] = False
        e["unresolved_reason"] = "Detached arrow"
        self.assertEqual(errors(d), set())
        self.assertEqual(receipt(d)["counts"]["unresolved"], 1)

    def test_unresolved_without_reason_is_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["state"] = "UNRESOLVED"
        self.assertIn("K14_UNRESOLVED", errors(d))

    def test_unresolved_with_direction_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["state"] = "UNRESOLVED"
        d["edges"][0]["unresolved_reason"] = "uncertain"
        self.assertIn("K14_UNRESOLVED", errors(d))

    def test_duplicate_edge_rejected(self):
        d = deepcopy(BASE); d["edges"].append(deepcopy(d["edges"][0]))
        self.assertIn("K06_DUPLICATE_EDGE", errors(d))

    def test_empty_evidence_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["evidence"] = []
        self.assertIn("K11_EVIDENCE", errors(d))

    def test_no_native_source_id_rejected(self):
        d = deepcopy(BASE); d["nodes"][0]["source_object_id"] = ""
        self.assertIn("K05_LOCATOR", errors(d))

    def test_bad_taxonomy_rejected(self):
        d = deepcopy(BASE); d["edges"][0]["relationship"] = "FLOWZ"
        self.assertIn("K10_RELATIONSHIP", errors(d))

    def test_deterministic_receipt_digest(self):
        a = receipt(BASE); b = receipt(deepcopy(BASE))
        self.assertEqual(a, b)

    def test_non_array_graph_fields_fail_closed_with_receipt(self):
        for field in ("nodes", "edges"):
            for bad in (None, "x", 5, {"id": "n1"}):
                with self.subTest(field=field, value=bad):
                    d = deepcopy(BASE); d[field] = bad
                    r = receipt(d)
                    self.assertEqual(r["status"], "FAIL_CLOSED")
                    self.assertIn("K03_TYPE", {f["code"] for f in r["findings"]})
                    self.assertEqual(r["counts"][field], 0)

    def test_non_object_manifest_fails_closed_with_receipt(self):
        for bad in ([], None, "manifest"):
            with self.subTest(value=bad):
                r = receipt(bad)
                self.assertEqual(r["status"], "FAIL_CLOSED")
                self.assertEqual([f["code"] for f in r["findings"]], ["K03_TYPE"])

    def test_cli_writes_fail_closed_receipt_for_malformed_edges(self):
        d = deepcopy(BASE); d["edges"] = None
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad.json"
            out = Path(tmp) / "receipt.json"
            manifest.write_text(json.dumps(d), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ROOT / "gg_contract.py"), str(manifest),
                                   "--receipt", str(out)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["status"], "FAIL_CLOSED")


class ExecutionDagTests(unittest.TestCase):
    def test_scheduled_pipeline_is_acyclic(self):
        self.assertEqual(validate_worker_dag(from_path(ROOT / "worker_dag.json")["jobs"]), [])

    def test_cycle_blocked(self):
        jobs = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]
        self.assertIn("K20_CYCLE", {x.code for x in validate_worker_dag(jobs)})

    def test_missing_dependency_blocked(self):
        jobs = [{"id": "a", "depends_on": ["missing"]}]
        self.assertIn("K19_MISSING_DEP", {x.code for x in validate_worker_dag(jobs)})

    def test_duplicate_job_id_blocked(self):
        jobs = [{"id": "a", "depends_on": []}, {"id": "a", "depends_on": []}]
        self.assertIn("K18_JOB_ID", {x.code for x in validate_worker_dag(jobs)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
