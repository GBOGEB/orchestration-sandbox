# gg_Engine W12 — native binary review dock

This folder contains **real SVG/PPTX/PDF/HTML file bytes generated from a deliberately synthetic two-equipment model**, and the exact GitHub-run W12 QA receipts. These are **review aids, not an engineering plant digital twin**.

## Browser-first review (no Git or CD)

- [Open interactive W12 HTML viewer](https://raw.githack.com/GBOGEB/orchestration-sandbox/feat/gg-engine-w12-convergent-pilot-20261113/docs/gg_engine/w12/index.html)
- [Download all binaries and receipts together](https://github.com/GBOGEB/orchestration-sandbox/raw/refs/heads/feat/gg-engine-w12-convergent-pilot-20261113/dist/gg_engine_w12_demo.zip)
- [Open layered PDF](layered.pdf) (inspect layer toggles in a capable PDF viewer)
- [Open editable PPTX](from_svg.pptx)
- [Open native SVG](source.svg)
- [Read exact CI QA receipt](QA_RECEIPT.json)
- [Inspect source-to-PPTX-to-SVG parity](roundtrip_receipt.json)
- [Inspect DOW nested-OCG fidelity](dow_fidelity_receipt.json)

## Authority and scope

- DOW SVG engine imported from ABACUS #2745 exact pinned SHA `eca6782f9850b61c083c25a03371a7be74aa0a98`; it remains RED in its own repository and **not admitted**.
- Output contains 4 native PDF layers, including a hidden parent and visible child; no real owner drawing is included.
- Source parser does not infer direction from color, proximity or text order.
- `W12 source → PPTX → SVG` has two W10 semantic-parity PASS receipts; these are **synthetic**, not full source geometry reconstruction.
- The original W10 ZIP lives under `dist/gg_engine_w10_source.zip`; this separate W12 ZIP is deterministic and backed by `dist/SHA256SUMS_W12.txt`.
- Native Microsoft PowerPoint and Adobe Acrobat acceptance, independent human review, and engineering owner approval **remain open**.
