"""Pin the shared W10 graph schema before the SVG and PPTX lanes are combined.

HANDOVER (W10 -> W11): "shared graph schema must be pinned before combined
integration". The pin covers the W10 vocabulary that both adapters write
(contract version, directions, review states, direction proofs, weak proofs and
relationship taxonomy). If W10 changes any of it, both adapters refuse to run
until someone re-pins on purpose, in a reviewed change.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from w10_bridge import gg_contract

PINNED_CONTRACT_VERSION = "gg-semantic-1.0"
PINNED_SCHEMA_SHA256 = "97a07d88a20077f9304ff186986d1ad665d486ce8bbec3c896348e8677652f6e"


class SchemaDrift(RuntimeError):
    """The W10 vocabulary no longer matches the pin; adapters fail closed."""


def schema_vocabulary(module: Any = gg_contract) -> Dict[str, Any]:
    return {
        "contract_version": module.CONTRACT_VERSION,
        "direction_proofs": sorted(module.DIRECTION_PROOFS),
        "directions": sorted(module.DIRECTIONS),
        "relationships": sorted(module.RELATIONSHIPS),
        "states": sorted(module.STATES),
        "weak_proofs": sorted(module.WEAK_PROOFS),
    }


def schema_digest(vocabulary: Optional[Dict[str, Any]] = None) -> str:
    vocab = schema_vocabulary() if vocabulary is None else vocabulary
    raw = json.dumps(vocab, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def assert_schema_pinned(vocabulary: Optional[Dict[str, Any]] = None) -> str:
    vocab = schema_vocabulary() if vocabulary is None else vocabulary
    digest = schema_digest(vocab)
    if vocab.get("contract_version") != PINNED_CONTRACT_VERSION or digest != PINNED_SCHEMA_SHA256:
        raise SchemaDrift(
            "W10 graph schema drifted from the W11 pin "
            f"(contract {vocab.get('contract_version')}, digest {digest}); re-pin deliberately"
        )
    return digest
