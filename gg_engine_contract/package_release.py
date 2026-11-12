#!/usr/bin/env python3
"""Build a deterministic ZIP from the public W10 Python source tree."""
from __future__ import annotations
import argparse
import hashlib
import pathlib
import zipfile

SOURCE = pathlib.Path(__file__).resolve().parent
EXCLUDE = {"sha256_manifest.txt"}

def source_files():
    return sorted((p for p in SOURCE.rglob("*") if p.is_file()
                   and p.suffix not in {".pyc", ".zip"}
                   and "__pycache__" not in p.parts
                   and p.name not in EXCLUDE), key=lambda p: p.relative_to(SOURCE).as_posix())

def write_archive(output):
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
        for path in source_files():
            rel = path.relative_to(SOURCE).as_posix()
            body = path.read_bytes()
            put("gg_engine_contract/" + rel, body)
            manifest.append(f"{hashlib.sha256(body).hexdigest()}  {rel}")
        put("gg_engine_contract/sha256_manifest.txt", ("\n".join(manifest) + "\n").encode())
    print(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output}")
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/gg_engine_w10_source.zip")
    write_archive(parser.parse_args().output)
