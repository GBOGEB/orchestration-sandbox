# Receiving agent: W12 -> W13 handover

- **Owner modules reused:** `gg_engine_contract/` (W10), `gg_engine_w11/` (W11), `DMAIC_V3/svg_engine` at pinned ABACUS SHA (W2 PDF engine). No duplicated parser or authority source.
- **Native sequence:** source SVG bytes -> W11 SVG manifest -> limited controlled PPTX emitter -> W11 PPTX manifest -> limited controlled SVG emitter -> W11 SVG manifest -> W10 parity twice.
- **Outputs:** `source.svg`, `from_svg.pptx`, `roundtrip.svg`, `index.html`, JSON manifests, `roundtrip_receipt.json`, `dow_receipt.json`, optional `layered.pdf`, optional `flat_baseline.pdf`, `SHA256SUMS.txt`, `gg_engine_w12_demo.zip`.
- **Explicit limits:** synthetic W11 fixtures only, native PowerPoint/Inkscape opening still unverified, no real owner data in public repo, no owner legend authentication, no integrated DOCX/XLSX actual user SSOT, no Visio semantic connectivity inference.
- **Gate:** W10/W11 tests and W12 negatives; DOW exact-SHA import + independent fidelity when native deps available; GitHub CI two Python versions; no waiver, no merge-on-red.
- **DAG:** W10 accepted -> W11 source adapters accepted -> W12A native emitter + W12B evidence/Visio reader (parallel) -> W12C HTML + DOW PDF -> W12D independent challenge -> KEB receipts -> W13 real binary scale proof.
- **ABACUS upstream blocker:** PR #2745 at eca6782f has red/unfinished governance checks (3.14 canonical coverage `UNCLASSIFIED_FAILURE`, compatibility proof not completed, PR feedback gate); do not treat DOW import working as merge admission.
- **Next decision:** independent DOW reviewer, actual owner-provided native SVG/PPTX reference pair, authoritative source-specific legend record and PowerPoint/Inkscape/Acrobat visual acceptance.
