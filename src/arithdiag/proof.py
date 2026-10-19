"""Integer proof strengthening; never exports conflicts or witnesses."""

import time
from arithdiag.hitting_set import improve_bound
from arithdiag.conflicts import explain_conflict
from arithdiag.preprocessing import add_conflicts


class ProofDriver:
    def __init__(self, model, pre, conflicts, enhanced=False, *, inject_ls_cuts=True):
        self.model = model
        self.pre = pre
        self.conflicts = conflicts
        self.enhanced = enhanced
        self.inject_ls_cuts = bool(inject_ls_cuts)
        self.components = tuple(c["name"] for c in model["components"])
        self.seen_healthy = set()
        self.seen_initial = set()
        self.master_exact = {}
        self.last_faults = None
        self.cursor = 0
        self.metrics = dict(
            proof_strengthening_s=0.0,
            proof_master_s=0.0,
            proof_refutation_s=0.0,
            proof_master_calls=0,
            proof_master_nodes=0,
            proof_master_exact_calls=0,
            proof_refutation_checks=0,
            proof_new_conflicts=0,
            proof_cuts_added=0,
            proof_bound_calls=0,
            proof_ls_cut_rows_added=0,
            proof_ls_cut_injection_skips=0,
            proof_external_conflicts_seen=0,
            proof_external_conflicts_imported=0,
            proof_external_conflicts_skipped=0,
            proof_min_core_size=None,
            proof_max_core_size=0,
        )

    def _remember_conflict(self, core):
        """Keep one proved family; remember no provenance or LS side effects."""
        if core is None:
            return None
        core = frozenset(core)
        if not core:
            raise ValueError(
                "Unconditional contradiction conflicts with a validated incumbent"
            )
        if any(old <= core for old in self.conflicts):
            return None
        self.conflicts[:] = [old for old in self.conflicts if not core < old]
        self.conflicts.append(core)
        return core

    def import_external_conflicts(self, cores):
        """Import already-proved worker cores without reinstalling their rows.

        The caller certifies these cores before installing its ordinary LS
        cuts. These are external proof facts, not internally generated events.
        Master and UNKNOWN caches retain actual-family keys: a changed family
        naturally misses, while duplicate imports preserve prior cache state.
        """
        imported = 0
        for core in cores:
            self.metrics["proof_external_conflicts_seen"] += 1
            if self._remember_conflict(core) is None:
                self.metrics["proof_external_conflicts_skipped"] += 1
            else:
                self.metrics["proof_external_conflicts_imported"] += 1
                imported += 1
        return imported

    def _add(self, core):
        core = self._remember_conflict(core)
        if core is None:
            return False
        self.metrics["proof_new_conflicts"] += 1
        # Proof learning and its hitting-set bound are independent of whether
        # a redundant row is also installed in the local-search model.
        if self.inject_ls_cuts:
            added = add_conflicts(self.pre, [core])
            self.metrics["proof_cuts_added"] += added  # Historical row counter.
            self.metrics["proof_ls_cut_rows_added"] += added
        else:
            # One event per accepted proof core; this is not a row estimate.
            self.metrics["proof_ls_cut_injection_skips"] += 1
        size = len(core)
        old_min = self.metrics["proof_min_core_size"]
        self.metrics["proof_min_core_size"] = (
            size if old_min is None else min(old_min, size)
        )
        self.metrics["proof_max_core_size"] = max(
            self.metrics["proof_max_core_size"], size
        )
        return True

    def _master(self, lower, upper, deadline):
        key = frozenset(self.conflicts)
        if key in self.master_exact:
            return max(lower, self.master_exact[key])
        start = time.monotonic()
        row = improve_bound(
            self.conflicts,
            current_lower=lower,
            target_upper=upper,
            deadline=deadline,
            max_nodes=200000,
        )
        self.metrics["proof_master_s"] += time.monotonic() - start
        self.metrics["proof_master_calls"] += 1
        self.metrics["proof_master_nodes"] += row["nodes"]
        if row.get("infeasible"):
            raise ValueError("Empty conflict inconsistent with validated incumbent")
        if row["exact"]:
            self.metrics["proof_master_exact_calls"] += 1
            self.master_exact[key] = row["conflict_lower_bound"]
        return row["lower_bound"]

    def step(self, lower, upper, healthy, budget_s):
        start = time.monotonic()
        deadline = start + max(0.0, budget_s)
        self.metrics["proof_bound_calls"] += 1
        lower = self._master(lower, upper, min(deadline, start + 0.25))
        if lower >= upper or not self.enhanced:
            self.metrics["proof_strengthening_s"] += time.monotonic() - start
            return lower
        # Each checker returns a proved healthy-assumption support, or UNKNOWN.
        # Do not repeatedly check the same set with the same deterministic rules.
        candidates = []
        for core in sorted(self.conflicts, key=lambda c: (len(c), sorted(c))):
            if core not in self.seen_initial:
                candidates.append((core, True))
        faults = tuple(c for c in self.components if c not in healthy)
        if faults != self.last_faults:
            self.cursor = 0
            self.last_faults = faults
        if faults:
            ordered = faults[self.cursor :] + faults[: self.cursor]
            candidates += [(frozenset(healthy | {c}), False) for c in ordered]
        reserve = min(0.3, max(0.0, budget_s / 3))
        check_deadline = deadline - reserve
        for healthy_set, initial in candidates:
            if time.monotonic() >= check_deadline:
                break
            if healthy_set in self.seen_healthy:
                if initial:
                    self.seen_initial.add(healthy_set)
                continue
            tick = time.monotonic()
            core = explain_conflict(
                self.model,
                healthy_set,
                deadline=time.perf_counter()
                + max(0.0, check_deadline - time.monotonic()),
            )
            self.metrics["proof_refutation_s"] += time.monotonic() - tick
            self.metrics["proof_refutation_checks"] += 1
            # UNKNOWN can also mean the deadline expired. Retry that final call.
            if time.monotonic() < check_deadline:
                self.seen_healthy.add(healthy_set)
                if initial:
                    self.seen_initial.add(healthy_set)
                else:
                    self.cursor = (self.cursor + 1) % max(1, len(faults))
            self._add(core)
        if time.monotonic() < deadline:
            lower = self._master(lower, upper, deadline)
        self.metrics["proof_strengthening_s"] += time.monotonic() - start
        return lower
