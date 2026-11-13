#!/usr/bin/env python3
"""Build a deterministic ZIP from the public W10 Python source tree.

Only the files named in RELEASE_FILES are packaged. Anything else that sits in
this folder (untracked local receipts, private source documents, editor files)
is never included, so a stray local file cannot leak into a public archive.
test_package_release.py checks that this allowlist matches the git-tracked files.
"""
from __future__ import annotations
import argparse
import hashlib
import pathlib
import zipfile

SOURCE = pathlib.Path(__file__).resolve().parent
MANIFEST_NAME = "sha256_manifest.txt"
RELEASE_FILES = (
    ".gitignore",
    "HANDOVER.md",
    "README.md",
    "benchmark_contract.py",
    "benchmark_results.json",
    "cache_keys.py",
    "ci_semantic_contract_example.yml",
    "contract_receipt.json",
    "fixture_accepted_candidate.json",
    "fixture_crossformat_pptx.json",
    "fixture_reversed_pptx.json",
    "gg_contract.py",
    "negative_parity_receipt.json",
    "package_release.py",
    "parity_gate.py",
    "parity_receipt.json",
    "release_manifest.json",
    "test_gg_contract.py",
    "test_package_release.py",
    "test_parity_and_cache.py",
    "test_results.txt",
    "worker_dag.json",
)


def source_files(root=SOURCE):
    root = pathlib.Path(root)
    missing = [name for name in RELEASE_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError("Allowlisted release files missing: " + ", ".join(missing))
    return [root / name for name in sorted(RELEASE_FILES)]


def write_archive(output, root=SOURCE):
    root = pathlib.Path(root)
    output = pathlib.Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        def put(name, content):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 12, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, content, compress_type=zipfile.ZIP_STORED)
        for path in source_files(root):
            rel = path.relative_to(root).as_posix()
            body = path.read_bytes()
            put("gg_engine_contract/" + rel, body)
            manifest.append(f"{hashlib.sha256(body).hexdigest()}  {rel}")
        put("gg_engine_contract/" + MANIFEST_NAME, ("\n".join(manifest) + "\n").encode())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/gg_engine_w10_source.zip")
    built = write_archive(parser.parse_args().output)
    print(f"{hashlib.sha256(built.read_bytes()).hexdigest()}  {built}")
