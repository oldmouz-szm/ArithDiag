"""Frozen LS ablations. Common construction and initialization stay enabled."""

import os

VARIANTS = {
    "full": (True, True),
    "no-internal-search": (False, True),
    "no-proof-enhancement": (True, False),
    "backend-only": (False, False),
}


def configuration(variant=None):
    name = variant if variant is not None else os.environ.get("ARITHDIAG_VARIANT", "full")
    if name not in VARIANTS:
        raise ValueError("Unsupported ArithDiag variant")
    search, proof = VARIANTS[name]
    return dict(
        variant=name,
        internal_candidate_search=search,
        internal_proof_enhancement=proof,
        internal_callbacks=search or proof,
        circuit_initialisation=True,
        static_conflicts_enabled=True,
        basic_conflict_bound=True,
    )
