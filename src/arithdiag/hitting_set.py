"""Certified lower bounds from already proved component conflicts.

This module knows no circuit semantics: every input hyperedge must independently
be proved to require at least one faulty component.  A covering solution is an
UPPER bound for this auxiliary problem, never a lower bound for diagnosis.
Only a packing or a completed UNSAT decision strengthens a diagnosis bound.
All returned data are scalar metrics; component identities remain in memory.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Hashable, Iterable


class _Stopped(Exception):
    pass


@dataclass
class _Budget:
    deadline: float | None
    max_nodes: int | None
    nodes: int = 0
    reason: str | None = None

    def check(self, *, visit: bool = False) -> None:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.reason = "deadline"
            raise _Stopped
        if visit:
            if self.max_nodes is not None and self.nodes >= self.max_nodes:
                self.reason = "node_limit"
                raise _Stopped
            self.nodes += 1


def _normalise(conflicts: Iterable[Iterable[Hashable]]) -> list[frozenset]:
    # Smaller edges imply their supersets; removing a superset preserves every
    # hitting set.  Stable tie order avoids relying on comparable component IDs.
    unique = list(dict.fromkeys(frozenset(edge) for edge in conflicts))
    unique.sort(key=len)
    result: list[frozenset] = []
    for edge in unique:
        if not any(previous <= edge for previous in result):
            result.append(edge)
    return result


def _packing(edges: list[frozenset], order: Iterable[int]) -> int:
    used: set = set()
    count = 0
    for index in order:
        edge = edges[index]
        if not used.intersection(edge):
            used.update(edge)
            count += 1
    return count


def greedy_packing_bound(conflicts: Iterable[Iterable[Hashable]]) -> int:
    """A deterministic disjoint-conflict lower bound (empty edge is invalid)."""
    edges = _normalise(conflicts)
    if edges and not edges[0]:
        raise ValueError("an empty proved conflict certifies infeasibility")
    return _packing(edges, range(len(edges)))


class _Engine:
    def __init__(self, edges: list[frozenset], budget: _Budget):
        self.edges = edges
        self.budget = budget
        self.full = (1 << len(edges)) - 1
        by_vertex: dict[Hashable, int] = {}
        for index, edge in enumerate(edges):
            budget.check()
            for vertex in edge:
                by_vertex[vertex] = by_vertex.get(vertex, 0) | (1 << index)
        # Equal coverage is interchangeable for unit costs.  We retain original
        # cover masks; per-branch dominance removal is sufficient and inexpensive.
        self.representatives: dict[int, Hashable] = {}
        for vertex, cover in by_vertex.items():
            self.representatives.setdefault(cover, vertex)
        self.covers = sorted(self.representatives, key=lambda x: (-x.bit_count(), x))
        self.by_edge: list[list[int]] = [[] for _ in edges]
        self.neighbours = [0] * len(edges)
        for cover in self.covers:
            budget.check()
            pending = cover
            while pending:
                bit = pending & -pending
                index = bit.bit_length() - 1
                self.by_edge[index].append(cover)
                self.neighbours[index] |= cover
                pending ^= bit
        self.edge_order = sorted(
            range(len(edges)), key=lambda i: (len(self.by_edge[i]), i)
        )
        # An UNSAT state with k available selections also refutes every smaller k.
        self.unsat: dict[int, int] = {}
        self.last_solution: tuple[int, ...] | None = None

    def packing(self, remaining: int) -> int:
        best = 0
        for order in (self.edge_order, reversed(self.edge_order)):
            available = remaining
            count = 0
            for index in order:
                if available & (1 << index):
                    count += 1
                    available &= ~self.neighbours[index]
            best = max(best, count)
        return best

    def greedy_upper(self) -> int:
        remaining = self.full
        count = 0
        while remaining:
            self.budget.check()
            cover = max(
                self.covers, key=lambda candidate: (candidate & remaining).bit_count()
            )
            remaining &= ~cover
            count += 1
        return count

    def decision(self, remaining: int, k: int) -> int | None:
        self.last_solution = self._decision(remaining, k)
        return None if self.last_solution is None else len(self.last_solution)

    def _decision(self, remaining: int, k: int) -> tuple[int, ...] | None:
        self.budget.check(visit=True)
        if not remaining:
            return ()
        if k <= 0 or self.unsat.get(remaining, -1) >= k:
            return None

        # The most constrained uncovered edge supplies a complete branching
        # disjunction: at least one component hitting this edge must be selected.
        index = next(i for i in self.edge_order if remaining & (1 << i))
        # Keep the original cover behind each residual mask.  Its original
        # component is needed only transiently if this search finds a cover.
        originals: dict[int, int] = {}
        for cover in self.by_edge[index]:
            originals.setdefault(cover & remaining, cover)
        candidates = sorted(
            originals,
            key=lambda mask: (-mask.bit_count(), mask),
        )
        maximal: list[int] = []
        for cover in candidates:
            self.budget.check()
            if cover == remaining:
                return (originals[cover],)
            # Replacing a selected component by one covering a superset can only
            # help in this unit-cost, positive-cover auxiliary problem.
            if not any(cover & other == cover for other in maximal):
                maximal.append(cover)

        max_coverage = max((cover & remaining).bit_count() for cover in self.covers)
        capacity_bound = (remaining.bit_count() + max_coverage - 1) // max_coverage
        if max(capacity_bound, self.packing(remaining)) > k:
            self.unsat[remaining] = max(k, self.unsat.get(remaining, -1))
            return None

        for cover in maximal:
            result = self._decision(remaining & ~cover, k - 1)
            if result is not None:
                return (originals[cover],) + result
        self.unsat[remaining] = max(k, self.unsat.get(remaining, -1))
        return None


def _validate_limit(value: int | None, name: str) -> None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value < 0
    ):
        raise ValueError(f"{name} must be a nonnegative integer or None")


def has_hitting_set_at_most(
    conflicts: Iterable[Iterable[Hashable]],
    k: int,
    *,
    deadline: float | None = None,
    max_nodes: int | None = None,
    on_candidate: Callable[[frozenset], None] | None = None,
) -> dict:
    """Decide whether all proved conflicts can be hit by at most ``k`` items.

    ``deadline`` uses time.monotonic().  UNKNOWN is never a refutation.  SAT's
    covering_cardinality is only an auxiliary upper bound, not a diagnosis.
    If supplied, ``on_candidate`` receives the original component IDs of one
    cover transiently, only for SAT and while the deadline remains open.  No
    component identity is included in the returned scalar metrics.
    """
    _validate_limit(k, "k")
    _validate_limit(max_nodes, "max_nodes")
    started = time.monotonic()
    budget = _Budget(deadline, max_nodes)
    edges = _normalise(conflicts)
    status = "UNKNOWN"
    cardinality = None
    infeasible = bool(edges and not edges[0])
    try:
        budget.check()
        if infeasible:
            status = "UNSAT"
        elif not edges:
            if on_candidate is not None:
                budget.check()
                on_candidate(frozenset())
            status, cardinality = "SAT", 0
        else:
            engine = _Engine(edges, budget)
            cardinality = engine.decision(engine.full, k)
            if cardinality is not None and on_candidate is not None:
                budget.check()
                on_candidate(
                    frozenset(
                        engine.representatives[cover] for cover in engine.last_solution
                    )
                )
            status = "SAT" if cardinality is not None else "UNSAT"
    except _Stopped:
        cardinality = None
    return {
        "status": status,
        "complete": status != "UNKNOWN",
        "covering_cardinality": cardinality,
        "infeasible": infeasible,
        "nodes": budget.nodes,
        "reason": budget.reason,
        "elapsed_s": time.monotonic() - started,
        "conflict_count": len(edges),
    }


def improve_bound(
    conflicts: Iterable[Iterable[Hashable]],
    current_lower: int = 0,
    *,
    target_upper: int | None = None,
    deadline: float | None = None,
    max_nodes: int | None = None,
) -> dict:
    """Raise a reliable diagnosis lower bound using already proved conflicts.

    Starting from packing, completed UNSAT decisions for at-most-k hitting sets
    justify k+1.  A completed SAT decision never raises a lower bound.  Searches
    share one deadline and node budget.  target_upper is only a stopping target;
    the caller must independently verify its diagnosis upper bound.

    ``exact`` concerns the conflict hitting-set optimum, not the original model.
    An empty proved edge sets infeasible=True and produces no finite new bound.
    """
    _validate_limit(current_lower, "current_lower")
    _validate_limit(target_upper, "target_upper")
    _validate_limit(max_nodes, "max_nodes")
    started = time.monotonic()
    budget = _Budget(deadline, max_nodes)
    edges = _normalise(conflicts)
    infeasible = bool(edges and not edges[0])
    conflict_lower = 0
    auxiliary_upper = None
    checked_up_to = None
    decisions = 0
    status = "NOT_NEEDED"
    exact = not edges
    evidence = "none"
    try:
        budget.check()
        if infeasible:
            status, exact, evidence = "INFEASIBLE", True, "empty_proved_conflict"
        elif edges:
            conflict_lower = max(
                _packing(edges, range(len(edges))),
                _packing(edges, reversed(range(len(edges)))),
            )
            evidence = "disjoint_proved_conflicts"
            engine = _Engine(edges, budget)
            conflict_lower = max(conflict_lower, engine.packing(engine.full))
            auxiliary_upper = engine.greedy_upper()
            exact = conflict_lower == auxiliary_upper
            k = max(current_lower, conflict_lower)
            while not exact and (target_upper is None or k < target_upper):
                if k >= auxiliary_upper:
                    break
                decisions += 1
                result = engine.decision(engine.full, k)
                if result is not None:
                    auxiliary_upper = min(auxiliary_upper, result)
                    status = "SAT"
                    exact = conflict_lower == auxiliary_upper
                    break
                checked_up_to = k
                conflict_lower = max(conflict_lower, k + 1)
                evidence = "completed_hitting_set_refutation"
                status = "UNSAT"
                exact = conflict_lower == auxiliary_upper
                k = max(current_lower, conflict_lower)
    except _Stopped:
        status = "UNKNOWN"
    return {
        "lower_bound": max(current_lower, conflict_lower),
        "conflict_lower_bound": conflict_lower,
        "auxiliary_upper_bound": auxiliary_upper,
        "exact": exact,
        "infeasible": infeasible,
        "checked_up_to": checked_up_to,
        "last_status": status,
        "evidence": evidence,
        "nodes": budget.nodes,
        "decisions": decisions,
        "reason": budget.reason,
        "elapsed_s": time.monotonic() - started,
        "conflict_count": len(edges),
    }
