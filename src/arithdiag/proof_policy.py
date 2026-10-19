"""Install the component-guided proof reduction, arithmetic repair and scheduling policy."""


def install(variant):
    if variant != "component_guided":
        raise ValueError("Only the component_guided proof policy is supported")
    from arithdiag import proof_reduction

    proof_reduction.install(components=True)
    from arithdiag import arithmetic_repair

    arithmetic_repair.install()
    from arithdiag import proof_scheduling

    proof_scheduling.install()
