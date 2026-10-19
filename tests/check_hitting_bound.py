#!/usr/bin/env python3
"""Exhaustive, deterministic checks; no diagnosis or conflict files are written."""

import itertools
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from arithdiag.hitting_set import (
    greedy_packing_bound,
    has_hitting_set_at_most,
    improve_bound,
)


def exhaustive(edges, n):
    for size in range(n + 1):
        for selected in itertools.combinations(range(n), size):
            values = set(selected)
            if all(values.intersection(edge) for edge in edges):
                return size
    return None


def main():
    triangle = [{"A", "B"}, {"B", "C"}, {"A", "C"}]
    assert greedy_packing_bound(triangle) == 1
    result = improve_bound(triangle, 1, target_upper=2)
    assert result["lower_bound"] == 2 and result["exact"]
    assert result["checked_up_to"] == 1
    assert result["evidence"] == "completed_hitting_set_refutation"
    assert has_hitting_set_at_most(triangle, 1)["status"] == "UNSAT"
    assert has_hitting_set_at_most(triangle, 2)["status"] == "SAT"

    independent = [{2 * i, 2 * i + 1} for i in range(16)]
    result = improve_bound(independent)
    assert result["lower_bound"] == 16 and result["exact"]
    assert result["nodes"] == 0
    assert improve_bound([])["lower_bound"] == 0
    assert improve_bound([], 5)["lower_bound"] == 5
    assert has_hitting_set_at_most([], 0)["status"] == "SAT"
    assert has_hitting_set_at_most([set()], 100)["status"] == "UNSAT"
    assert improve_bound([set()])["infeasible"]
    assert improve_bound([set()])["lower_bound"] == 0

    for limits in ({"deadline": time.monotonic() - 1}, {"max_nodes": 0}):
        result = has_hitting_set_at_most(triangle, 1, **limits)
        assert result["status"] == "UNKNOWN" and not result["complete"]
        result = improve_bound(triangle, 1, **limits)
        assert result["lower_bound"] == 1
        assert result["last_status"] == "UNKNOWN" and not result["exact"]

    # A found auxiliary cover with cost 3 must never be promoted to a lower bound
    # when a smaller cover may exist and no refutation has completed.
    result = improve_bound(triangle, 0, target_upper=1)
    assert result["lower_bound"] == 1 and not result["exact"]
    assert result["nodes"] == 0

    # External circuit bounds can exceed the conflict-only optimum.  Preserve the
    # external bound without falsely claiming an exact conflict optimum.
    cycle5 = [{i, (i + 1) % 5} for i in range(5)]
    result = improve_bound(cycle5, 4)
    assert result["lower_bound"] == 4
    assert result["conflict_lower_bound"] <= 3

    rng = random.Random(19417)
    checked = 0
    families = []
    for n in range(2, 10):
        families.append((n, [{i, j} for i in range(n) for j in range(i + 1, n)]))
        families.append((n, [{i, (i + 1) % n} for i in range(n)]))
        # Unequal component coverage exercises the dominance simplification.
        families.append((n, [{0, i} for i in range(1, n)]))
    for n, edges in families:
        optimum = exhaustive(edges, n)
        result = improve_bound(edges)
        assert result["lower_bound"] == optimum and result["exact"]
        for k in range(n + 1):
            result = has_hitting_set_at_most(edges, k)
            assert result["status"] == ("SAT" if optimum <= k else "UNSAT")
        checked += 1
    for n in range(1, 9):
        for trial in range(80):
            edges = []
            for _ in range(rng.randrange(0, 15)):
                edge = {v for v in range(n) if rng.randrange(3) == 0}
                # Include empty edges, repeated edges, and implied supersets.
                # Most trials have no empty edge, so exact search is exercised
                # rather than almost every case ending at a trivial conflict.
                if not edge and trial % 4:
                    edge = {rng.randrange(n)}
                edges.append(edge)
                if rng.randrange(5) == 0:
                    edges.append(set(edge))
            optimum = exhaustive(edges, n)
            result = improve_bound(edges)
            if optimum is None:
                assert result["infeasible"]
            else:
                assert result["lower_bound"] == optimum, (edges, optimum, result)
                assert result["exact"]
            for k in range(n + 1):
                result = has_hitting_set_at_most(edges, k)
                expected = "SAT" if optimum is not None and optimum <= k else "UNSAT"
                assert result["status"] == expected, (edges, k, optimum, result)
                if result["status"] == "SAT":
                    assert optimum <= result["covering_cardinality"] <= k
                for limit in (0, 1, 3):
                    bounded = has_hitting_set_at_most(edges, k, max_nodes=limit)
                    assert bounded["status"] in ("UNKNOWN", expected)
            for limit in (0, 1, 3):
                bounded = improve_bound(edges, max_nodes=limit)
                if optimum is not None:
                    assert bounded["lower_bound"] <= optimum
            checked += 1
    print(
        f"hitting bound: triangle, independent, limits, and {checked} exhaustive random hypergraphs passed"
    )


if __name__ == "__main__":
    main()
