"""Align proof master fault choices with minimum-preserving preprocessing.

Every core remains an original-model proved core. Within the reduced search,
ABs fixed to zero cannot hit a core, while an AB fixed to one already hits it.
The resulting bound applies to the reduced model and to original minimum
cardinality via the preprocessor's established optimum-preservation property;
it does not assert preservation of all diagnosis identities. Actual IHS health
queries still use the full original circuit and exact original explanations.
"""

METRICS = dict(
    reduced_fixed_healthy=0, reduced_core_calls=0, reduced_removed_literals=0
)


def install(components=False):
    from arithdiag import adaptive_proof, proof, hitting_set

    active = []
    init = adaptive_proof.AdaptiveIHSDriver.__init__

    def wrapped_init(self, model, pre, *args, **kwargs):
        init(self, model, pre, *args, **kwargs)
        self.fixed_ab = {}
        for c in model["components"]:
            name = c["name"]
            ab = "AB_" + name
            if pre["rename"].get(ab, ab) != ab:
                raise ValueError("Proof master requires distinct abnormality variables")
            if ab in pre["fixed"]:
                self.fixed_ab[name] = pre["fixed"][ab]

    adaptive_proof.AdaptiveIHSDriver.__init__ = wrapped_init
    if components:
        from arithdiag import component_master

        improve, decide = component_master.improve, component_master.decide
    else:
        improve, decide = hitting_set.improve_bound, hitting_set.has_hitting_set_at_most

    def project(conflicts):
        fixed = active[-1].fixed_ab if active else {}
        METRICS["reduced_fixed_healthy"] = sum(v == 0 for v in fixed.values())
        result = []
        METRICS["reduced_core_calls"] += 1
        for core in conflicts:
            if any(fixed.get(c) == 1 for c in core):
                continue
            reduced = frozenset(c for c in core if fixed.get(c) != 0)
            if not reduced:
                raise ValueError(
                    "Proved conflict incompatible with a feasible reduced incumbent"
                )
            METRICS["reduced_removed_literals"] += len(core) - len(reduced)
            result.append(reduced)
        return result

    def reduced_improve(conflicts, *args, **kwargs):
        return improve(project(conflicts), *args, **kwargs)

    def reduced_decide(conflicts, *args, **kwargs):
        return decide(project(conflicts), *args, **kwargs)

    proof.improve_bound = reduced_improve
    adaptive_proof.has_hitting_set_at_most = reduced_decide
    step = adaptive_proof.AdaptiveIHSDriver.step

    def wrapped_step(self, *args, **kwargs):
        active.append(self)
        try:
            return step(self, *args, **kwargs)
        finally:
            active.pop()
            self.metrics.update(METRICS)
            if components:
                self.metrics.update(component_master.METRICS)

    adaptive_proof.AdaptiveIHSDriver.step = wrapped_step
