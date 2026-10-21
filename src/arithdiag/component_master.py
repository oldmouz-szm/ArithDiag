"""Additive exact/partial optimization of independent proved-conflict parts.

Independence is checked on original component IDs of the current core family.
Cached component results are reused only for exactly identical normalized edges.
No circuit diagnosis, negative oracle answer or UNSAT is inferred from a cover.
"""

from collections import OrderedDict, defaultdict
import time
from arithdiag import hitting_set as h
from arithdiag import resumable_master

ORIGINAL_IMPROVE = h.improve_bound
ORIGINAL_DECIDE = h.has_hitting_set_at_most
CACHE = OrderedDict()
PARTS = OrderedDict()
METRICS = dict(
    part_calls=0,
    part_cache_hits=0,
    part_solves=0,
    part_max_edges=0,
    part_max_count=0,
    part_nodes=0,
    part_s=0.0,
)


def split(edges):
    key = frozenset(frozenset(e) for e in edges)
    if key in PARTS:
        PARTS.move_to_end(key)
        return PARTS[key]
    edges = h._normalise(key)
    if edges and not edges[0]:
        return [tuple(edges)]
    parent = list(range(len(edges)))
    owner = {}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, e in enumerate(edges):
        for v in e:
            if v in owner:
                parent[find(i)] = find(owner[v])
            else:
                owner[v] = i
    groups = defaultdict(list)
    for i, e in enumerate(edges):
        groups[find(i)].append(e)
    parts = sorted(
        (tuple(es) for es in groups.values()),
        key=lambda es: (len(es), sum(map(len, es))),
    )
    PARTS[key] = parts
    while len(PARTS) > 16:
        PARTS.popitem(last=False)
    METRICS["part_max_count"] = max(METRICS["part_max_count"], len(parts))
    METRICS["part_max_edges"] = max(
        METRICS["part_max_edges"], max(map(len, parts), default=0)
    )
    return parts


def state(part):
    key = frozenset(part)
    if key not in CACHE:
        lower = h.greedy_packing_bound(part)
        # Selecting every distinct component is always a hitting set.
        upper = len(set().union(*part))
        CACHE[key] = dict(lower=lower, upper=upper, exact=lower == upper, cover=None)
        while len(CACHE) > 1024:
            CACHE.popitem(last=False)
    else:
        METRICS["part_cache_hits"] += 1
        CACHE.move_to_end(key)
    return CACHE[key]


def optimize(parts, deadline, max_nodes):
    states = [state(p) for p in parts]
    nodes = 0
    for i, (part, s) in enumerate(zip(parts, states)):
        if deadline is not None and time.monotonic() >= deadline:
            break
        if s["exact"]:
            continue
        left = (deadline - time.monotonic()) if deadline is not None else 1.0
        portion = min(left, max(0.003, left / (len(parts) - i)))
        captured = []
        options = {"on_candidate": captured.append} if h.FAST_MASTER else {}
        row = resumable_master.improve(
            part,
            current_lower=s["lower"],
            deadline=time.monotonic() + portion,
            max_nodes=max_nodes,
            **options,
        )
        METRICS["part_solves"] += 1
        nodes += row["nodes"]
        s["lower"] = max(s["lower"], row["conflict_lower_bound"])
        if row["auxiliary_upper_bound"] is not None:
            s["upper"] = min(s["upper"], row["auxiliary_upper_bound"])
        s["exact"] = s["lower"] == s["upper"]
        if s["cover"] is not None and len(s["cover"]) > s["upper"]:
            s["cover"] = None
        for cover in captured:
            if len(cover) <= s["upper"]:
                if any(not cover.intersection(edge) for edge in part):
                    raise ValueError("Cached auxiliary cover fails its exact conflict family")
                s["cover"] = cover
    METRICS["part_nodes"] += nodes
    return states, nodes


def improve(
    conflicts, current_lower=0, *, target_upper=None, deadline=None, max_nodes=None
):
    start = time.monotonic()
    METRICS["part_calls"] += 1
    parts = split(conflicts)
    if any(not e for p in parts for e in p):
        return ORIGINAL_IMPROVE(
            conflicts,
            current_lower,
            target_upper=target_upper,
            deadline=deadline,
            max_nodes=max_nodes,
        )
    states, nodes = optimize(parts, deadline, max_nodes)
    low = sum(s["lower"] for s in states)
    upper = sum(s["upper"] for s in states)
    exact = all(s["exact"] for s in states)
    METRICS["part_s"] += time.monotonic() - start
    return dict(
        lower_bound=max(current_lower, low),
        conflict_lower_bound=low,
        auxiliary_upper_bound=upper,
        exact=exact,
        infeasible=False,
        checked_up_to=None,
        last_status="SAT" if exact else "UNKNOWN",
        evidence="sum_of_independent_proved_conflict_part_bounds",
        nodes=nodes,
        decisions=0,
        reason=None if exact else "incomplete_parts",
        elapsed_s=time.monotonic() - start,
        conflict_count=sum(map(len, parts)),
    )


def decide(conflicts, k, *, deadline=None, max_nodes=None, on_candidate=None):
    start = time.monotonic()
    parts = split(conflicts)
    if any(not e for p in parts for e in p):
        return ORIGINAL_DECIDE(
            conflicts,
            k,
            deadline=deadline,
            max_nodes=max_nodes,
            on_candidate=on_candidate,
        )
    states, nodes = optimize(parts, deadline, max_nodes)
    low = sum(s["lower"] for s in states)
    status = "UNKNOWN"
    cardinality = None
    if low > k:
        status = "UNSAT"
    elif sum(s["upper"] for s in states) <= k:
        found = set()
        complete = True
        for part, s in zip(parts, states):
            if deadline is not None and time.monotonic() >= deadline:
                complete = False
                break
            if s["cover"] is None:
                captured = []
                row = ORIGINAL_DECIDE(
                    part,
                    s["upper"],
                    deadline=deadline,
                    max_nodes=max_nodes,
                    on_candidate=captured.append,
                )
                nodes += row["nodes"]
                if row["status"] != "SAT" or not captured:
                    complete = False
                    break
                s["cover"] = captured[0]
            found.update(s["cover"])
        if (
            complete
            and len(found) <= k
            and (deadline is None or time.monotonic() < deadline)
        ):
            if on_candidate:
                on_candidate(frozenset(found))
            status = "SAT"
            cardinality = len(found)
    if deadline is not None and time.monotonic() >= deadline:
        status = "UNKNOWN"
        cardinality = None
    return dict(
        status=status,
        complete=status != "UNKNOWN",
        covering_cardinality=cardinality,
        infeasible=False,
        nodes=nodes,
        reason=None if status != "UNKNOWN" else "incomplete_parts",
        elapsed_s=time.monotonic() - start,
        conflict_count=sum(map(len, parts)),
    )


def install():
    from arithdiag import proof, adaptive_proof

    proof.improve_bound = improve
    adaptive_proof.has_hitting_set_at_most = decide
    step = adaptive_proof.AdaptiveIHSDriver.step

    def wrapped(self, *args, **kwargs):
        try:
            return step(self, *args, **kwargs)
        finally:
            self.metrics.update(METRICS)

    adaptive_proof.AdaptiveIHSDriver.step = wrapped
