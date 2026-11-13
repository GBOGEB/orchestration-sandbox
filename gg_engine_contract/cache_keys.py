"""Cache-key contract shared by parallel adapters; no cached authority promotion."""
import hashlib
import json
import re


def make_cache_key(source_sha256: str, adapter_version: str, legend_sha256: str,
                   contract_version: str = "gg-semantic-1.0") -> str:
    for name, value in (("source", source_sha256), ("legend", legend_sha256)):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{name} SHA-256 must be 64 lowercase hex characters")
    if not adapter_version or not contract_version:
        raise ValueError("adapter and contract versions are required")
    data={"source_sha256":source_sha256,"adapter_version":adapter_version,
          "legend_sha256":legend_sha256,"contract_version":contract_version}
    raw=json.dumps(data,sort_keys=True,separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
