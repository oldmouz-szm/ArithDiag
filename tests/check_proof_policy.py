"""Independent finite semantics for the internal search/proof coordinator.

No original validator is used to determine the ground-truth optimum/supports.
Synthetic witnesses and component sets stay in RAM; output is aggregate counts.
"""

from pathlib import Path
from collections import Counter
import argparse, itertools, json, os, random, sys, time

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
from arithdiag.preprocessing import (
    transform,
    initial,
    restore,
    cone_conflicts,
    conflict_bound,
)
from arithdiag.proof_coordinator import ProofCoordinator
from arithdiag.conflicts import explain_conflict
from arithdiag import component_master
from arithdiag.variants import configuration as variant_configuration

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--variant", choices=("full", "no-internal-search", "no-proof-enhancement"), default="full")
args = parser.parse_args()
features = variant_configuration(args.variant)

rng = random.Random(2026101807)
count = Counter()
start = time.perf_counter()


def fixture(i):
    widths = {"a": 1, "b": 1, "c": 1}
    inputs = {x: rng.randrange(2) for x in widths}
    ops = []
    for j in range(3 + i % 2):
        choices = []
        for a in widths:
            for b in widths:
                for op in ("add", "multiply"):
                    w = (
                        max(widths[a], widths[b]) + 1
                        if op == "add"
                        else widths[a] + widths[b]
                    )
                    if w <= 4:
                        choices.append((a, b, op, w))
        a, b, op, w = rng.choice(choices)
        name = "s" + str(j)
        ops.append((name, a, b, op))
        widths[name] = w
    observed = dict(inputs)
    observed[ops[-1][0]] = rng.randrange(1 << widths[ops[-1][0]])
    if i % 3 == 0:
        observed[ops[-2][0]] = rng.randrange(1 << widths[ops[-2][0]])
    specs = [
        dict(
            name=n,
            signal=n,
            bits=[w - 1, 0],
            role="input" if n in inputs else "output" if n in observed else "wire",
            type="integer",
            lb=observed.get(n, 0),
            ub=observed.get(n, (1 << w) - 1),
        )
        for n, w in widths.items()
    ]

    def ref(n):
        return dict(signal=n, low=0, high=widths[n] - 1)

    def ex(n):
        return dict(parts=[dict(width=widths[n], ref=ref(n))])

    components = []
    rows = []
    for j, (out, a, b, op) in enumerate(ops):
        c = "C" + str(j)
        components.append(dict(name=c, operation=op, a=ex(a), b=ex(b), output=ref(out)))
        specs.append(
            dict(name="AB_" + c, signal=c, role="abnormal", type="binary", lb=0, ub=1)
        )
        lin = [dict(var=out, coef=1)]
        quad = []
        if op == "add":
            lin.extend([dict(var=a, coef=-1), dict(var=b, coef=-1)])
        else:
            quad = [dict(vars=[a, b], coef=-1)]
        rows.append(dict(name="conditional_"+c, kind="conditional_component",
            component=c, abnormal="AB_"+c, sense="eq", rhs=0,
            linear=lin, quadratic=quad))
    model = dict(
        variables=specs,
        components=components,
        constraints=rows,
        ports=[
            dict(
                name=n, width=widths[n], direction="input" if n in inputs else "output"
            )
            for n in observed
        ],
        observed_ports=observed,
    )
    return model, widths, observed, ops


def independent(model, widths, observed, ops):
    free = [n for n in widths if n not in observed]
    states = {}
    for values in itertools.product(*(range(1 << widths[n]) for n in free)):
        x = dict(observed, **dict(zip(free, values)))
        healthy = 0
        for j, (out, a, b, op) in enumerate(ops):
            healthy |= (x[out] == (x[a] + x[b] if op == "add" else x[a] * x[b])) << j
        states.setdefault(healthy, x)
    return states


def check_witness(x, model, widths, observed, ops):
    assert all(type(x[n]) is int and 0 <= x[n] < (1 << w) for n, w in widths.items())
    assert all(x[n] == v for n, v in observed.items())
    for j, (out, a, b, op) in enumerate(ops):
        ab = x["AB_C" + str(j)]
        assert ab in (0, 1)
        if ab == 0:
            assert x[out] == (x[a] + x[b] if op == "add" else x[a] * x[b])


def exhaustive_hitting(edges, n):
    for k in range(n + 1):
        for d in itertools.combinations(range(n), k):
            if all(set(d) & e for e in edges):
                return k
    return None


for i in range(220):
    model, widths, observed, ops = fixture(i)
    states = independent(model, widths, observed, ops)
    n = len(ops)
    optimum = n - max(mask.bit_count() for mask in states)
    names = ["C" + str(j) for j in range(n)]

    def sound(core):
        mask = sum(1 << names.index(c) for c in core)
        assert not any((h & mask) == mask for h in states), "Unsound health support"
        count["independent_conflict_checks"] += 1

    for mask in range(1 << n):
        healthy = {c for j, c in enumerate(names) if mask >> j & 1}
        core = explain_conflict(model, healthy)
        if core is not None:
            assert core <= healthy
            sound(core)
        count["health_queries"] += 1
    before = repr(model)
    init = initial(model)
    assert init is not None
    check_witness(init, model, widths, observed, ops)
    cores = cone_conflicts(model)
    for c in cores:
        sound(c)
    for structural, dom, decompose in (
        (False, False, False),
        (True, False, True),
        (True, True, True),
    ):
        pre = transform(model, structural, dom, decompose)
        fixed = {
            j: pre["fixed"]["AB_" + c]
            for j, c in enumerate(names)
            if "AB_" + c in pre["fixed"]
        }
        assert all(v == 0 for v in fixed.values())
        reduced = {h: x for h, x in states.items() if all(h >> j & 1 for j in fixed)}
        assert (
            reduced and n - max(h.bit_count() for h in reduced) == optimum
        ), "Dominance changed optimum"
        count["reduction_optimum_checks"] += 1
        # Deliberately start with a poor feasible diagnosis to exercise search.
        health, x = next(iter(reduced.items()))
        complete = dict(x)
        complete.update(
            {"AB_" + c: 0 if j in fixed else 1 for j, c in enumerate(names)}
        )
        _, upper = restore(pre, {k: complete[k] for k in pre["specs"]})
        best = [complete, upper]
        lower = conflict_bound(cores)
        coop = ProofCoordinator(
            model, pre, list(cores), 120, lower, complete,
            candidate_search=features["internal_candidate_search"],
            proof_enhancement=features["internal_proof_enhancement"],
        )

        def accept(candidate, origin):
            full, k = restore(pre, candidate)
            check_witness(full, model, widths, observed, ops)
            assert k >= optimum
            if k < best[1]:
                best[:] = [full, k]
            count["independent_repair_witnesses"] += 1

        for _ in range(3):
            actual = coop.step(
                best[0], best[1], 0.025, time.perf_counter() + 0.1, accept
            )
            assert lower <= actual <= optimum <= best[1], "Unsound focused bound"
            if not features["internal_proof_enhancement"]:
                assert actual == lower and set(coop.driver.conflicts) == set(cores)
                assert coop.driver.metrics["ihs_refuted_cardinality_queries"] == 0
                assert coop.driver.metrics["ihs_new_conflicts"] == 0
                assert coop.driver.metrics["proof_master_calls"] == 0
                assert coop.driver.metrics["proof_refutation_checks"] == 0
            if not features["internal_candidate_search"]:
                assert coop.telemetry()["coordination_candidates"] == 0
                assert coop.driver.metrics.get("repair_calls", 0) == 0
            for c in coop.driver.conflicts:
                sound(c)
            if actual == best[1]:
                assert actual == optimum
                count["correct_closed_bounds"] += 1
            lower = actual
            count["focused_steps"] += 1
        projected = [
            {names.index(c) for c in core if pre["fixed"].get("AB_" + c) != 0}
            for core in coop.driver.conflicts
        ]
        exact = exhaustive_hitting(projected, n)
        assert exact is not None and lower <= optimum and exact <= optimum
        count["projected_master_truth_checks"] += 1
    assert repr(model) == before, "Audit mutated original model"
    count["circuit_models"] += 1

# Independent conflict-master fuzz, including duplicates and disconnected parts.
for n in range(1, 11):
    for _ in range(100):
        edges = []
        for j in range(rng.randrange(0, 18)):
            e = {v for v in range(n) if rng.randrange(4) == 0}
            if not e:
                e = {rng.randrange(n)}
            edges.append(e)
            if rng.randrange(5) == 0:
                edges.append(set(e))
        exact = exhaustive_hitting(edges, n)
        row = component_master.improve(
            edges, deadline=time.monotonic() + 1, max_nodes=200000
        )
        assert row["lower_bound"] <= exact
        if row["exact"]:
            assert row["lower_bound"] == exact
        for k in range(n + 1):
            captured = []
            r = component_master.decide(
                edges,
                k,
                deadline=time.monotonic() + 1,
                max_nodes=200000,
                on_candidate=captured.append,
            )
            if r["status"] == "UNSAT":
                assert k < exact
            elif r["status"] == "SAT":
                assert (
                    exact <= k
                    and captured
                    and len(captured[0]) <= k
                    and all(captured[0] & e for e in edges)
                )
            count["decomposed_master_decisions"] += 1
        count["decomposed_hypergraphs"] += 1

out = dict(
    passed=True,
    counts=dict(count),
    elapsed_s=time.perf_counter() - start,
    ground_truth="independent exhaustive unsigned signal arithmetic; not the original candidate validator",
    runtime_variant=args.variant,
)
if features["internal_candidate_search"]:
    assert count["independent_repair_witnesses"] > 0, "Active search never produced a checked witness"

print(json.dumps(out))
