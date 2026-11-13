# gg_Engine W11 — native PPTX and SVG adapters (first slice)

**Status:** `W11_ADAPTERS_STAGED / SYNTHETIC_TESTED / REAL_SOURCE_UNTESTED / DOW_NOT_RUN / KEB_NOT_ISSUED / OWNER_ACCEPTANCE_HOLD`

These two standard-library readers turn native drawing objects into W10 `gg-semantic-1.0` graph claims. Their output goes through the **unchanged** W10 gates: `gg_contract.validate_manifest`/`receipt` and `parity_gate.compare_graphs`. A pass means the adapters and the W10 gates agree on synthetic inputs. It is **not** engineering acceptance, DOW qualification, a KEB receipt or owner approval.

W10 (`gg_engine_contract/`, `dist/gg_engine_w10_source.zip`) is not modified. W11 imports the W10 gates through `w10_bridge.py` and never copies them.

## What the adapters claim, and from what

| | PPTX (`pptx_adapter.py`) | SVG (`svg_adapter.py`) |
|---|---|---|
| Edge exists | `p:cxnSp` with `a:stCxn` **and** `a:endCxn` bound to unique shapes | element with `inkscape:connection-start` **and** `-end` bound to unique objects |
| Direction | `a:headEnd`/`a:tailEnd` of type `triangle`, `stealth` or `arrow`. Explicit, or resolved through `p:style/a:lnRef` to the theme line style | `marker-start`/`marker-end` (inherited properties included) **only if** an owner-verified legend record lists the marker id as an arrowhead |
| Not direction | `oval`/`diamond` ends, flips, rotation, group transforms, geometry, neighbour order | unclassified markers, layer order, transforms, geometry, proximity |
| Relationship | only from an owner-verified legend record bound to the file's SHA-256 (`line_color`, `line_dash`) | same (`stroke`, `stroke-dasharray`) |
| Node identity | `p:cNvPr/@name` → `node:<name>`, otherwise `native:<id>` | `inkscape:label` or `<title>` → `node:<tag>`; if they disagree, `AMBIGUOUS_TAG` and the native id is used |
| Kept as context | slide, group path, `a:xfrm`, connection-site index, line style | layer path, transform chain, connector type, stroke style |

Arrow evidence orients an edge: a head-end arrow reverses the drawn order (`REVERSED_FROM_DRAWING`). With no arrowhead, or with arrowheads at both ends, the endpoints are sorted so that drawing order never becomes a direction claim.

## Fail-closed behaviour

- **Quarantine (not in `edges`):** unbound ends, ends bound to a missing, duplicated or connector object, self-loops, connectors with a duplicated native id.
- **`UNRESOLVED` with a reason:** theme inheritance that does not resolve, unknown line-end types, hidden or invisible connectors or endpoints, an SVG `<style>` sheet (CSS is not evaluated), malformed or missing markers, an arrowhead on `marker-mid`, and legend rules that disagree.
- **W10 `FAIL_CLOSED`:** duplicate semantic tags reach the contract as duplicate node or edge ids (`K04`/`K06`). This is deliberate, because identity ambiguity must block.
- **Refused input (exit 2):** any DTD or entity declaration, non-UTF-8 XML, Strict OOXML, oversized parts or packages, missing parts, and a root element that is not `<svg>`.
- **Never emitted:** `GOLDEN`, `approval`, and any qualification other than `NOT_RUN` / `NOT_ISSUED` / `HOLD`.
- **Schema pin:** `schema_pin.py` hashes the W10 vocabulary. If W10 changes it, both adapters stop until someone re-pins it in a reviewed change.

## Legend record (owner-held, optional)

Without a legend record, every relationship is `UNKNOWN` and SVG direction is `UNKNOWN`. A record is applied only when every check below passes. Otherwise it is `REJECTED` with `L01`–`L07` findings and has no effect:

```json
{
  "legend_record_version": "gg-legend-0.1",
  "format": "pptx",
  "source_sha256": "<sha256 of the exact .pptx/.svg bytes>",
  "legend_object_id": "pptx:s1:12",
  "verified": true,
  "verified_by": "<owner>",
  "decision_id": "<owner decision id>",
  "verified_at": "<date>",
  "relationships": [{"match": {"line_color": "srgb:0000FF"}, "relationship": "FLOW"}],
  "arrowhead_markers": []
}
```

`arrowhead_markers` is SVG-only. The adapter checks these fields but cannot authenticate who verified the record. That confirmation stays with the owner.

## Run from the repository root (Python 3.9+)

```bash
python -m unittest discover -s gg_engine_contract -p 'test_*.py' -v
python -m unittest discover -s gg_engine_w11 -p 'test_*.py' -v
python gg_engine_w11/pptx_adapter.py drawing.pptx --slide 1 --legend legend.json --out pptx_claim.json --contract-receipt pptx_receipt.json
python gg_engine_w11/svg_adapter.py drawing.svg --legend legend.json --out svg_claim.json --contract-receipt svg_receipt.json
python gg_engine_contract/parity_gate.py svg_claim.json pptx_claim.json --receipt parity_receipt.json
```

Exit codes: `0` claim written (and W10 `PASS_CONTRACT_ONLY` if requested), `1` W10 `FAIL_CLOSED`, `2` input refused. Locators carry the file's basename only, never a local path.

## Known gaps in this slice

- Only synthetic, in-memory fixtures (`synthetic_fixtures.py`). They hold just the parts the adapters read and have not been opened in PowerPoint or Inkscape.
- No real native-to-native round trip yet; W13-scale stays blocked until one passes the oracle.
- Not read: Strict OOXML, `mc:AlternateContent`, connector-to-connector chains, theme colour resolution (scheme colours are matched literally), CSS, `<use>` clones, multi-slide diagrams, SVG producers other than Inkscape connectors.
- Node policy is `CONNECTOR_ENDPOINTS_ONLY`, so isolated objects are not claimed.
- Python 3.9 is grammar-checked locally. It runs only in CI.

See `HANDOVER.md` for lanes, independence rules and next steps.
