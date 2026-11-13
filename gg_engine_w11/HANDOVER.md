# Receiving-agent handover — W11 native adapters

## Base and containment

- Branched from `handover/gg-engine-w10-semantic-contract-v0p2` at `8af69a99d60ca4fd131cb5827e134099a3e70c34`.
- W11 does not touch `gg_engine_contract/` or `dist/`. The W11 workflow rebuilds the W10 ZIP and byte-compares it with whatever `dist/` holds on the PR merge ref. The W10 lane owns that ZIP and its hash, which changed when the W10 review fixes landed.
- Public-safe: generic code and synthetic fixtures only. No private drawings, project names, repository pins or credentials.
- **Do not merge, and do not treat these synthetic results as engineering acceptance.** Keep the PR draft until exact-head CI is green on 3.9 and 3.12, an independent DOW review has run, and the owner has decided.

## What W11 delivered (first slice)

| HANDOVER W10 item | W11 state |
|---|---|
| 1. SVG reader adapter: preserve native layer identity, transforms, legend, ambiguity | `svg_adapter.py`: Inkscape connector bindings; layers and transforms recorded; legend through an owner record; ambiguity as `UNRESOLVED`, quarantine or `AMBIGUOUS_TAG` |
| 2. PPTX reader adapter: native shape and connector ids; actual OOXML arrowhead and anchoring evidence before any orientation claim | `pptx_adapter.py`: `stCxn`/`endCxn` anchoring, `headEnd`/`tailEnd` arrow types, explicit or theme-resolved |
| Shared graph schema pinned before combined integration | `schema_pin.py`: pinned W10 vocabulary digest; both adapters refuse to run on drift |
| One writer per output path, deterministic cache keys, quarantine for unsupported or ambiguous edges | sorted, byte-stable output; `cache_keys.make_cache_key(source, producer, legend)`; `quarantine[]` |

Evidence: 50 W11 author tests on synthetic fixtures plus the 36 unchanged W10 tests (py3.12 local). Three mutation probes were caught: stale legend accepted, `oval` treated as an arrow, and drawing order leaking into unknown edges. Py3.9 is grammar-checked only until CI runs.

## Independence and authority (unchanged from W10)

- **W12-DOW stays independent of this adapter writer.** The tests here are author tests, not DOW. A separate reviewer should write the DOW challenge set against these adapters: false crossings, reversed arrows, stale legend hashes, duplicate native ids, missing labels and unsupported authority promotions. They should not reuse `synthetic_fixtures.py` as their only oracle.
- **KEB receipt:** not issued. Adapter output carries `keb_receipt: NOT_ISSUED`.
- **Owner authority:** adapters never emit `GOLDEN` or `approval`. Legend records are owner-held, and the adapter checks their fields but does not authenticate the verifier.

## DAG position

```
W0-census -> W1A-svg (this) ─┐
          -> W1B-pptx (this) ┴-> W2-graph -> W3A-dow-negative (independent) ─┐
                                          -> W3B-render (after source-contract acceptance) ┴-> W4-keb-receipt -> W5-scale
```

W2-graph (combined integration) can start because the schema is now pinned. W13-scale stays blocked until at least one **real** native-to-native round trip passes the oracle.

## Next steps (suggested)

1. A real round trip: one owner-provided SVG and PPTX pair with an owner legend record → both adapters → `parity_gate.py`. Record source hashes, adapter versions, legend SHA, the CI run URL and the reviewer.
2. Open fixtures in PowerPoint and Inkscape. Replace or extend the in-memory fixtures with files saved by the real tools, and record the tool versions.
3. Fill the read gaps as the owner's sources require: `mc:AlternateContent`, theme colour resolution, connector chains, CSS (or a pinned no-CSS export profile), and non-Inkscape SVG producers.
4. Output adapters (HANDOVER item 4): structural, semantic and visual parity, each measured separately.
5. Release review (item 5) before any GOLDEN promotion.

## Suggested target status

`W11_ADAPTERS_STAGED / SYNTHETIC_TESTED / REAL_SOURCE_UNTESTED / DOW_NOT_RUN / KEB_NOT_ISSUED / OWNER_ACCEPTANCE_HOLD`
