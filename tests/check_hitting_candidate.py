#!/usr/bin/env python3
"""Transient auxiliary covers, checked by independent exhaustive enumeration.

Only aggregate test counts are printed; component selections stay in memory.
"""

from dataclasses import dataclass
import itertools
from pathlib import Path
import random
import sys
import time
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from arithdiag import hitting_set
from arithdiag.hitting_set import has_hitting_set_at_most


@dataclass(frozen=True)
class Token:
    index: int


def optimum(edges, vertices):
    for size in range(len(vertices) + 1):
        for selected in itertools.combinations(vertices, size):
            if all(set(selected).intersection(edge) for edge in edges):
                return size
    return None


def check_query(edges, vertices, k, **limits):
    minimum = optimum(edges, vertices)
    count = []

    def accept(selected):
        assert isinstance(selected, frozenset)
        assert selected <= set(vertices)
        assert len(selected) <= k
        assert all(selected.intersection(edge) for edge in edges)
        count.append(len(selected))

    result = has_hitting_set_at_most(edges, k, on_candidate=accept, **limits)
    assert all(
        isinstance(value, (str, int, float, bool, type(None)))
        for value in result.values()
    )
    expected = "SAT" if minimum is not None and minimum <= k else "UNSAT"
    assert result["status"] in (expected, "UNKNOWN")
    if result["status"] == "SAT":
        assert len(count) == 1
        assert count[0] == result["covering_cardinality"]
        assert minimum <= count[0]
    else:
        assert not count
        assert result["covering_cardinality"] is None
    if not limits:
        assert result["status"] == expected
    return result


def main():
    triangle = [{"A", "B"}, {"B", "C"}, {"A", "C"}]
    for k in range(4):
        check_query(triangle, ["A", "B", "C"], k)
    check_query([], [], 0)
    check_query([set()], [], 2)
    for edges in ([], triangle):
        result = check_query(edges, ["A", "B", "C"], 3, deadline=time.monotonic() - 1)
        assert result["status"] == "UNKNOWN"
    for k in (1, 2):
        result = check_query(triangle, ["A", "B", "C"], k, max_nodes=0)
        assert result["status"] == "UNKNOWN"

    # A search can finish its SAT recursion just as the deadline expires.
    # The callback must still be suppressed by the final deadline check.
    clock = [0.0]
    original_decision = hitting_set._Engine.decision

    def finish_after_deadline(engine, remaining, k):
        cardinality = original_decision(engine, remaining, k)
        clock[0] = 2.0
        return cardinality

    with mock.patch.object(hitting_set.time, "monotonic", side_effect=lambda: clock[0]):
        with mock.patch.object(hitting_set._Engine, "decision", finish_after_deadline):
            result = check_query(triangle, ["A", "B", "C"], 2, deadline=1.0)
            assert result["status"] == "UNKNOWN"
            assert result["reason"] == "deadline"

    # Equal masks select an original representative.  A new query rebuilds
    # coverage: a formerly interchangeable or dominated component may become
    # essential after adding a conflict.
    a, b, c = Token(0), "B", ("C", 2)
    check_query([{a, b}], [a, b, c], 1)
    check_query([{a, b}, {b, c}], [a, b, c], 1)
    check_query([{a, b}, {b, c}, {a}], [a, b, c], 2)
    check_query([{a, b}, {b, c}, {a, c}], [a, b, c], 2)

    rng = random.Random(761917)
    checked = 0
    queries = 0
    for n in range(1, 9):
        # No ordering exists across these three kinds of Hashable IDs.
        vertices = [
            Token(i) if i % 3 == 0 else str(i) if i % 3 == 1 else (i, "id")
            for i in range(n)
        ]
        families = [
            [{vertices[i], vertices[(i + 1) % n]} for i in range(n)],
            [{vertices[i], vertices[j]} for i in range(n) for j in range(i + 1, n)],
            [{vertices[0], vertices[i]} for i in range(1, n)],
        ]
        for trial in range(64):
            edges = []
            for _ in range(rng.randrange(15)):
                edge = {vertex for vertex in vertices if rng.randrange(3) == 0}
                if not edge and trial % 4:
                    edge = {rng.choice(vertices)}
                edges.append(edge)
                if rng.randrange(5) == 0:
                    edges.append(set(edge))
            families.append(edges)
        for edges in families:
            for k in range(n + 1):
                check_query(edges, vertices, k)
                queries += 1
                for cap in (0, 1, 3):
                    check_query(edges, vertices, k, max_nodes=cap)
                    queries += 1
            checked += 1
    print(
        f"transient hitting candidates: {checked} exhaustive hypergraphs, "
        f"{queries} decision/limit checks, and deadline regressions passed"
    )


if __name__ == "__main__":
    main()
