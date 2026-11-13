"""Synthetic contract-validation scale pilot: never an engineering-data benchmark.

Documents are independently varied graph manifests. Reads files from disk and
compares identical receipts across worker counts, including an expected error.
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from gg_contract import from_path, receipt

ROOT = Path(__file__).resolve().parent


def synthetic_document(base, i):
    d = copy.deepcopy(base)
    d["source"]["sha256"] = f"{i + 1:064x}"
    d["source"]["locator"] = f"synthetic://graph-{i:04d}.svg"
    d["nodes"][0]["id"] = f"eq:P-{i:04d}"
    d["nodes"][1]["id"] = f"eq:HX-{i:04d}"
    d["edges"][0]["source_id"] = d["nodes"][0]["id"]
    d["edges"][0]["target_id"] = d["nodes"][1]["id"]
    d["edges"][0]["id"] = f"edge:{i:04d}"
    # Deterministic adversarial population: each 13th document falsely
    # claims direction using only spatial proximity.
    if i % 13 == 12:
        d["edges"][0]["evidence"] = [{"type": "PROXIMITY", "locator": "synthetic:nearby"}]
    return d


def scan(path):
    r = receipt(from_path(path))
    return (path.name, r["status"], r["input_digest_sha256"], tuple(f["code"] for f in r["findings"]))


def measure(paths, workers, trials=3):
    samples = []
    result = None
    for _ in range(trials):
        start = time.perf_counter()
        if workers == 1:
            output = [scan(p) for p in paths]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                output = list(pool.map(scan, paths))
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        if result is None:
            result = output
        elif result != output:
            raise RuntimeError("Non-deterministic result across repeated trials")
    return {"workers": workers,
            "median_wall_s": round(statistics.median(samples), 6),
            "throughput_files_per_s": round(len(paths) / statistics.median(samples), 1),
            "trials": trials,
            "classifications": {"PASS_CONTRACT_ONLY": sum(x[1] == "PASS_CONTRACT_ONLY" for x in result),
                                "FAIL_CLOSED": sum(x[1] == "FAIL_CLOSED" for x in result)}}, result


def run(sizes, worker_counts):
    base = from_path(ROOT / "fixture_accepted_candidate.json")
    runs = []
    with tempfile.TemporaryDirectory(prefix="gg-w10-synthetic-") as tmp:
        for n in sizes:
            folder = Path(tmp) / str(n)
            folder.mkdir()
            paths = []
            for i in range(n):
                p = folder / f"graph-{i:04d}.json"
                p.write_text(json.dumps(synthetic_document(base, i), sort_keys=True), encoding="utf-8")
                paths.append(p)
            expected_bad = sum(i % 13 == 12 for i in range(n))
            signature = None
            for w in worker_counts:
                metric, out = measure(paths, w)
                if signature is None:
                    signature = out
                elif signature != out:
                    raise RuntimeError(f"Classification differs at worker count {w}")
                if metric["classifications"]["FAIL_CLOSED"] != expected_bad:
                    raise RuntimeError("Adversarial population was not classified consistently")
                metric["documents"] = n
                metric["injected_false_direction_count"] = expected_bad
                runs.append(metric)
    return {
        "dataset": "SYNTHETIC_CONTRACT_FIXTURES_NOT_REAL_MASTER_INPUT",
        "purpose": "Contract-validation throughput and parallelism smoke, not SVG/PPTX parser performance",
        "checks": ["K01-K17", "deterministic classify", "same population across workers"],
        "runs": runs,
        "scale_admission": "NOT_QUALIFIED_FOR_PRODUCTION",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="10,50,200")
    parser.add_argument("--workers", default="1,4,8")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sizes = [int(i) for i in args.sizes.split(",")]
    workers = [int(i) for i in args.workers.split(",")]
    if not sizes or not workers or min(sizes + workers) < 1:
        raise SystemExit("sizes and workers must be positive")
    result = run(sizes, workers)
    out = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
