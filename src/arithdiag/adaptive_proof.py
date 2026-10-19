"""Budgeted, incomplete integer implicit-hitting-set proof strengthening.

Only proved conflicts and completed at-most-k refutations raise bounds.  A SAT
cover is a transient healthy-assumption query, never a circuit diagnosis or a
lower bound.  UNKNOWN causes a bounded in-memory cooldown, never a blocker.
"""

from __future__ import annotations

from collections import OrderedDict
import math
import time

from arithdiag.hitting_set import has_hitting_set_at_most
from arithdiag.conflicts import explain_conflict
from arithdiag.proof import ProofDriver


class AdaptiveIHSDriver(ProofDriver):
    def __init__(self, model, pre, conflicts, total_limit_s=60, *, inject_ls_cuts=True):
        if not math.isfinite(total_limit_s) or total_limit_s < 0:
            raise ValueError("A finite nonnegative whole-worker limit is required")
        super().__init__(
            model, pre, conflicts, enhanced=True, inject_ls_cuts=inject_ls_cuts
        )
        self.created = time.monotonic()
        self.proof_cap_s = total_limit_s * 0.10
        self.unknown_states = OrderedDict()
        self.rotation = 0
        self.metrics.update(
            adaptive_calls=0,
            adaptive_queries=0,
            adaptive_quota_skips=0,
            adaptive_cooldown_skips=0,
            adaptive_unknown_retries=0,
            adaptive_round_limit_max=24,
            adaptive_last_budget_s=0.0,
            adaptive_quota_cap_s=self.proof_cap_s,
            adaptive_last_query_k=None,
            ihs_calls=0,
            ihs_master_calls=0,
            ihs_master_nodes=0,
            ihs_integer_checks=0,
            ihs_new_conflicts=0,
            ihs_unknown_candidates=0,
            ihs_refuted_cardinality_queries=0,
            ihs_s=0.0,
            ihs_master_s=0.0,
            ihs_integer_s=0.0,
            ihs_last_target_k=None,
            ihs_last_master_status=None,
            proof_backend="adaptive_internal_integer_conflicts_and_hitting_sets",
        )

    def available_budget(self, requested_s):
        """Unspent earned proof time; this query does not consume the quota."""
        if not math.isfinite(requested_s) or requested_s <= 0:
            return 0.0
        elapsed = max(0.0, time.monotonic() - self.created)
        earned = min(self.proof_cap_s, 1.0 + elapsed * 0.10)
        return min(
            requested_s, max(0.0, earned - self.metrics["proof_strengthening_s"])
        )

    def should_checkpoint(self, native_elapsed_s):
        """Let each native search round run for at least one second."""
        return native_elapsed_s >= 1.0 and self.available_budget(0.75) >= 0.05

    def _remember_unknown(self, key, attempts):
        self.unknown_states[key] = dict(attempts=attempts, at=time.monotonic())
        self.unknown_states.move_to_end(key)
        while len(self.unknown_states) > 128:
            self.unknown_states.popitem(last=False)

    def _retry_state(self, key):
        state = self.unknown_states.get(key)
        if state is None:
            return 0
        cooldown = min(8.0, float(2 ** min(state["attempts"] - 1, 3)))
        if time.monotonic() - state["at"] < cooldown:
            return None
        return state["attempts"]

    def step(self, lower, upper, healthy, budget_s):
        start = time.monotonic()
        allowed = self.available_budget(budget_s)
        self.metrics["adaptive_last_budget_s"] = allowed
        if allowed <= 0:
            self.metrics["adaptive_quota_skips"] += 1
            return lower
        self.metrics["adaptive_calls"] += 1
        self.metrics["ihs_calls"] += 1
        previous_spent = self.metrics["proof_strengthening_s"]
        deadline = start + allowed
        accepted_lower = lower
        ihs_started = None
        try:
            if lower >= upper:
                return lower
            # Retain explained propagation and incumbent-health trials
            # alive, while reserving most of the quota for the new loop.
            propagation_budget = min(0.2, allowed * 0.25)
            candidate_lower = super().step(lower, upper, healthy, propagation_budget)
            if time.monotonic() >= deadline:
                return accepted_lower
            accepted_lower = candidate_lower
            ihs_started = time.monotonic()
            while accepted_lower < upper and time.monotonic() < deadline:
                # Start at the reliable current bound, so large gaps make
                # incremental progress. A completed UNSAT raises it by one.
                k = accepted_lower
                key = (frozenset(self.conflicts), k)
                attempts = self._retry_state(key)
                if attempts is None:
                    self.metrics["adaptive_cooldown_skips"] += 1
                    break
                if attempts:
                    self.metrics["adaptive_unknown_retries"] += 1
                self.metrics["adaptive_queries"] += 1
                self.metrics["adaptive_last_query_k"] = k
                self.metrics["ihs_last_target_k"] = k
                captured = []
                # Equivalent orders can expose a different original cover.
                # Rotation changes no clause and excludes no UNKNOWN cover.
                edges = list(self.conflicts)
                if edges:
                    offset = self.rotation % len(edges)
                    edges = edges[offset:] + edges[:offset]
                    self.rotation += 1
                tick = time.monotonic()
                row = has_hitting_set_at_most(
                    edges,
                    k,
                    deadline=deadline,
                    max_nodes=200000,
                    on_candidate=captured.append,
                )
                self.metrics["ihs_master_s"] += time.monotonic() - tick
                self.metrics["ihs_master_calls"] += 1
                self.metrics["ihs_master_nodes"] += row["nodes"]
                self.metrics["ihs_last_master_status"] = row["status"]
                if time.monotonic() >= deadline:
                    break
                if row["status"] == "UNSAT":
                    self.metrics["ihs_refuted_cardinality_queries"] += 1
                    accepted_lower = max(accepted_lower, k + 1)
                    continue
                if row["status"] != "SAT" or not captured:
                    # A timeout/node cap can be retried with future quota.
                    break
                faulty = captured[0]
                if len(faulty) > k or not faulty <= set(self.components):
                    raise ValueError("Invalid transient hitting-set candidate")
                if any(not faulty.intersection(core) for core in self.conflicts):
                    raise ValueError("Transient candidate fails a proved conflict")
                assumed_healthy = frozenset(self.components) - faulty
                rounds = min(96, 24 * 2 ** min(attempts, 2))
                self.metrics["adaptive_round_limit_max"] = max(
                    self.metrics["adaptive_round_limit_max"], rounds
                )
                tick = time.monotonic()
                core = explain_conflict(
                    self.model,
                    assumed_healthy,
                    deadline=time.perf_counter()
                    + max(0.0, deadline - time.monotonic()),
                    max_rounds=rounds,
                )
                self.metrics["ihs_integer_s"] += time.monotonic() - tick
                self.metrics["ihs_integer_checks"] += 1
                if time.monotonic() >= deadline:
                    # Even a sound returned explanation is not accepted late.
                    break
                if core is None:
                    self.metrics["ihs_unknown_candidates"] += 1
                    self._remember_unknown(key, attempts + 1)
                    break
                if not core <= assumed_healthy or faulty.intersection(core):
                    raise ValueError("Integer conflict depends on a relaxed component")
                if not self._add(core):
                    raise ValueError("Refuted candidate did not produce a new conflict")
                self.metrics["ihs_new_conflicts"] += 1
                # Rebuild immediately: strengthening an old conflict can change
                # packing even before another integer health query is made.
                candidate_lower = self._master(accepted_lower, upper, deadline)
                if time.monotonic() >= deadline:
                    break
                accepted_lower = candidate_lower
            return accepted_lower
        finally:
            now = time.monotonic()
            if ihs_started is not None:
                self.metrics["ihs_s"] += now - ihs_started
            # The superclass updates this field itself. Replace that partial
            # amount with this call's complete wall time, counted exactly once.
            self.metrics["proof_strengthening_s"] = previous_spent + now - start
