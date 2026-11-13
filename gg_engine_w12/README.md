# gg_Engine W12 — convergent native-object proof & review surfaces

**State:** `SYNTHETIC_NATIVE_ROUNDTRIP_CANDIDATE / REAL_OWNER_SOURCE_NOT_TESTED / DOW_DEPENDENCY_PINNED / NO_OWNER_AUTHORITY`.

## What exists

- `pilot.py` reuses **the actual merged W11** `read_svg` and `read_pptx` adapters. Its **limited fixture-only emitter** starts with SVG native bytes, parses an explicit anchored connector into W10 claims, rebuilds a PPTX OOXML package from that claim, parses it, rebuilds SVG, parses again, and compares two independent W10 semantic-parity checkpoints. The emitter refuses unfamiliar or ambiguous graphs, so it cannot be used as a general production binary converter.
- `dow_bridge.py` imports `DMAIC_V3.svg_engine` from **ABACUS PR #2745 exact SHA `eca6782f9850b61c083c25a03371a7be74aa0a98`**. The DOW owner implements native layer ingress, nested OCG PDF, independent CairoSVG/PyMuPDF fidelity checks. This bridge does not copy the engine or bypass ABACUS CI failures. It verifies `git rev-parse HEAD` before use.
- `viewer.py` creates an **offline clickable HTML** review surface with SVG/PPTX selection, controlled object IDs, source evidence, filter, explicit discrepancy list and native SVG/PDF links. The schematic layout is **not a geometry reconstruction**.
- `evidence_ingress.py` preserves read-only native DOCX paragraphs, XLSX sheet/row/cell/formula records, Visio Shape IDs, and PNG dimensions/sha. No OCR, no fuzzy matching, no status inference. `bind_explicit` only accepts exact SHA/native ID plus explicit rationale and `CANDIDATE_LINK`, and quarantines missing/stale/unauthorized links.
- Negative tests reject stale legend hashes, topology reversal, quarantined source edges, duplicate/unknown native IDs, OOXML zip traversal, formula evaluation claims, HTML script breakout and unauthorized authority promotions.

## Proof tiers

| Check | Meaning |
|---|---|
| W10 `PASS_CONTRACT_ONLY` | The manifest is structurally consistent, **not authoritative** |
| W11 `PASS_SEMANTIC_PARITY_ONLY` | Same identified objects/edges/relationship/direction across two synthetically rebuilt native-byte representations |
| DOW `PASS_REVIEW_ONLY` | A nested-OCG PDF renders and the DOW SVG-fidelity ladder reports no FAIL (when run against the exact pinned external ABACUS engine) |
| HTML static/interaction checks | Navigability and presentation only |
| PowerPoint / Inkscape native-open | **Not claimed** until those tools validate the generated files |
| Actual owner source / engineer-reviewed legend | **NOT RUN**: cannot be substituted by fixtures |
| Independent DOW review | **NOT YET PERFORMED** by an independent reviewer; author tests alone do not count |
| GOLDEN / engineering SSOT | **HOLD** |

## Run locally from repository root

```bash
python -m unittest discover -s gg_engine_w12 -p 'test_*.py' -v
python gg_engine_w12/pilot.py --out w12-out
# To run the *existing* DOW layered PDF engine on a checkout pinned to the exact SHA:
python gg_engine_w12/pilot.py --out w12-out --abacus-root /path/to/ABACUS_checkout
```

To inspect: open `w12-out/index.html` in a browser; click the objects. The output ZIP `w12-out/gg_engine_w12_demo.zip` includes all source binaries, HTML, JSON receipts, and optionally DOW-created PDF + flat baseline.

## Independent acceptance lanes and next controlled scale

- **Lane A**: W11 source adapters and limited OOXML/SVG producer; one writer to native files.
- **Lane B (DOW independent)**: adversarial source/quarantine tests written separately; avoid common oracles and prove negatives before review.
- **Lane C (KB/KEB)**: hashes, manifest, exact-head CI and reviewer signatures; release held on red upstream gates.
- **Lane D (DOCX/XLSX)**: owner-source ID/row crosswalk on a private SSOT, never promote semantic meaning from keyword similarity.
- **Lane E (VSDX/PNG)**: native Visio shape trees and raster-only residual/oracle.
- **Scale proof W13**: compare 10 / 50 / 200 real binary records (p50/p95, peak RAM, invariants, failure signatures, cache efficiency) *after* at least one actual owner source pair has independent visual and semantic acceptance.

The safe next owner boundary is real inputs plus source-specific legends and professional native application review. This PR supplies the reproducible mechanism, not acceptance.
