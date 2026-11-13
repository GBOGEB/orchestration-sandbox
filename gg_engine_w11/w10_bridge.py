"""Single import point for the frozen W10 contract gates.

W11 imports the W10 functions; it never copies them. The W10 folder is flat
(modules import each other by bare name), so it is appended to ``sys.path``
once, here, and nowhere else.
"""
from __future__ import annotations

import sys
from pathlib import Path

W10_DIR = Path(__file__).resolve().parent.parent / "gg_engine_contract"
if str(W10_DIR) not in sys.path:
    sys.path.append(str(W10_DIR))

import gg_contract  # noqa: E402
from cache_keys import make_cache_key  # noqa: E402
from gg_contract import (  # noqa: E402
    CONTRACT_VERSION,
    DIRECTION_PROOFS,
    DIRECTIONS,
    RELATIONSHIPS,
    STATES,
    WEAK_PROOFS,
    receipt,
    validate_manifest,
)
from parity_gate import compare_graphs  # noqa: E402

__all__ = [
    "CONTRACT_VERSION", "DIRECTION_PROOFS", "DIRECTIONS", "RELATIONSHIPS", "STATES",
    "W10_DIR", "WEAK_PROOFS", "compare_graphs", "gg_contract", "make_cache_key",
    "receipt", "validate_manifest",
]
