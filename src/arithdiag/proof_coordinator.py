"""Budgeted sharing of exact witnesses and certified integer conflict bounds.

Conflict members and witnesses are transient. The numerical native lower bound
is never used as a premise of an internal integer proof.
"""

import time

_installed = None


def project_core(core, pre, components):
    """Translate a proved original core into this exact reduced AB domain."""
    terms = []
    for c in sorted(core):
        if c not in components:
            raise ValueError("Unknown component in certified core")
        n = "AB_" + c
        if pre["rename"].get(n, n) != n:
            raise ValueError("Aliased AB in proof projection")
        if n in pre["fixed"]:
            if pre["fixed"][n] == 1:
                return None
            if pre["fixed"][n] != 0:
                raise ValueError("Nonbinary fixed AB")
        else:
            if n not in pre["specs"]:
                raise ValueError("Missing projected AB")
            terms.append(n)
    if not terms:
        raise ValueError("Proved core contradicts feasible reduced domain")
    return tuple(terms)


class ProofCoordinator:
    def __init__(
        self, model, pre, cores, limit, initial_lower, incumbent, known_cores=None,
        *, candidate_search=True, proof_enhancement=True
    ):
        global _installed
        if _installed is None:
            from arithdiag import proof_policy

            proof_policy.install("component_guided", candidate_search=candidate_search)
            _installed = bool(candidate_search)
        elif _installed != bool(candidate_search):
            raise ValueError("Use a fresh worker for a different ablation policy")
        from arithdiag.adaptive_proof import AdaptiveIHSDriver

        self.model = model
        self.pre = pre
        self.components = {c["name"] for c in model["components"]}
        self.driver = AdaptiveIHSDriver(
            model, pre, list(cores), total_limit_s=limit, inject_ls_cuts=False
        )
        self.driver.preferred = incumbent
        self.driver.candidate_search_enabled = bool(candidate_search)
        self.driver.proof_enhancement_enabled = bool(proof_enhancement)
        self.lower = initial_lower
        self.seen = set(map(frozenset, cores if known_cores is None else known_cores))
        self.pending = []
        self.metrics = dict(
            coordination_calls=0,
            coordination_s=0.0,
            coordination_new_conflicts=0,
            coordination_internal_lower=initial_lower,
            coordination_candidates=0,
        )

    def step(self, complete, upper, requested, deadline, accept_original):
        from arithdiag.preprocessing import projected_initial

        remaining = deadline - time.perf_counter() - 0.03
        allowed = self.driver.available_budget(min(requested, max(0.0, remaining)))
        if allowed < 0.01:
            return self.lower
        start = time.perf_counter()
        self.metrics["coordination_calls"] += 1
        healthy = {c for c in self.components if complete["AB_" + c] == 0}
        self.driver.preferred = complete
        value = self.driver.step(self.lower, upper, healthy, allowed)
        self.metrics["coordination_s"] += time.perf_counter() - start
        if time.perf_counter() >= deadline:
            return self.lower
        if value > upper:
            raise ValueError("Internal bound exceeds verified incumbent")
        self.lower = max(self.lower, value)
        self.metrics["coordination_internal_lower"] = self.lower
        for core in self.driver.conflicts:
            core = frozenset(core)
            if core not in self.seen:
                self.seen.add(core)
                terms = project_core(core, self.pre, self.components)
                if terms is not None:
                    self.pending.append(terms)
                self.metrics["coordination_new_conflicts"] += 1
        transient = getattr(self.driver, "transient_candidate", None)
        if transient is not None:
            self.driver.transient_candidate = None
            projected = projected_initial(self.pre, transient)
            if projected is not None:
                self.metrics["coordination_candidates"] += 1
                accept_original(projected, "internal_integer_witness")
        return self.lower

    def telemetry(self):
        from arithdiag.affine_conflicts import METRICS as AFFINE
        from arithdiag.relation_conflicts import METRICS as RELATION
        from arithdiag.resumable_master import METRICS as RESUME
        return dict(self.driver.metrics, **self.metrics, **AFFINE, **RELATION, **RESUME)
