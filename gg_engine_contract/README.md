# gg_Engine W10 — Synthetic Semantic Contract Pilot

**Status:** Tested contract/graph-claim prototype, **NOT** a verified engineering drawing parser, not owner acceptance, and not a release into any engineering SSOT.

This copy is intentionally public-safe: **only generic Python implementation, synthetic fixtures, and synthetic test/benchmark receipts**. Private engineering source files, private repository pointers, proprietary document names, account credentials and user worktrees are not included.

## What the code does

- `gg_contract.py` checks a normalized graph claim against source hashes, stable object/native IDs, typed edges, legend evidence, review states, and dependency DAG.
- `parity_gate.py` compares two normalized diagrams for dropped/new objects, directed-edge reversals, and impermissible promotion of review states.
- `cache_keys.py` binds caches to source SHA-256, parser/adapter version, legend SHA-256 and contract version.
- `benchmark_contract.py` measures **synthetic validation**, not actual PPTX/SVG parsing, renderer quality, or engineering accuracy.

A good result such as `PASS_CONTRACT_ONLY` means **structural validation only**. It must never be described as domain/engineering approval. Do not infer arrow direction from adjacency or visual left-to-right ordering alone.

## Run from repository root (Python 3.9+)

```bash
python -m unittest discover -s gg_engine_contract -p 'test_*.py' -v
python gg_engine_contract/gg_contract.py gg_engine_contract/fixture_accepted_candidate.json --jobs gg_engine_contract/worker_dag.json --receipt /tmp/gg_contract_receipt.json
python gg_engine_contract/parity_gate.py gg_engine_contract/fixture_accepted_candidate.json gg_engine_contract/fixture_crossformat_pptx.json --receipt /tmp/gg_parity_receipt.json
python gg_engine_contract/package_release.py --output dist/gg_engine_w10_source.zip
```

On Windows PowerShell, replace the `/tmp/...` receipt paths with filenames under `$env:TEMP`; for example, `--receipt gg_contract_receipt.json` writes to the current directory.

The deliberately reversed fixture `fixture_reversed_pptx.json` **must** fail closed (exit status 1). It is a negative test, not a release failure.

## Reproducible source ZIP

`package_release.py` builds a deterministic archive of the current tracked package source, plus a SHA-256 manifest of all included files. It writes a package hash to stdout. No third-party Python dependencies are required.

```powershell
py -3 gg_engine_contract/package_release.py --output dist/gg_engine_w10_source.zip
Get-FileHash dist/gg_engine_w10_source.zip -Algorithm SHA256
```

## Publication and engineering authority

- This folder is a **staging import**, not the canonical PPTX or SVG engine.
- Changes should enter the domain-specific engine through separate, reviewed integration PRs with native source-bound evidence.
- Engineering graph relationships remain `CANDIDATE`/`UNRESOLVED` until independently corroborated and accepted by the authorized owner.
- No sample metrics presented here are from real MASTER_INPUT or a real cross-format round-trip.

For dependency and acceptance details see `HANDOVER.md`.
