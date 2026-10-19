"""Earn extra proof quota only while proved cores/bounds make progress.

Base accrual 10%, productive accrual 40%, cap40% of whole-process budget.
Unspent credit never decreases, and all original worker deadline checks apply.
This changes scheduling only, never proof acceptance or oracle semantics.
"""

import math, time


def install():
    from arithdiag import adaptive_proof

    C = adaptive_proof.AdaptiveIHSDriver
    init = C.__init__
    step = C.step

    def start(self, *args, **kwargs):
        init(self, *args, **kwargs)
        limit = kwargs.get("total_limit_s", args[3] if len(args) > 3 else 60)
        self.proof_cap_s = float(limit) * 0.4
        self.focus_bonus = 0.0
        self.focus_last = time.monotonic()
        self.productive = False
        self.metrics.update(
            adaptive_quota_cap_s=self.proof_cap_s,
            focus_productive_steps=0,
            focus_idle_steps=0,
            focus_bonus_earned_s=0.0,
        )

    def available(self, requested_s):
        now = time.monotonic()
        delta = max(0.0, now - self.focus_last)
        if self.productive:
            self.focus_bonus += 0.3 * delta
        self.focus_last = now
        self.metrics["focus_bonus_earned_s"] = self.focus_bonus
        if not math.isfinite(requested_s) or requested_s <= 0:
            return 0.0
        earned = min(
            self.proof_cap_s, 1 + max(0.0, now - self.created) * 0.1 + self.focus_bonus
        )
        return min(
            requested_s, max(0.0, earned - self.metrics["proof_strengthening_s"])
        )

    def advance(self, lower, upper, healthy, budget_s):
        before = self.metrics.get("ihs_new_conflicts", 0)
        result = step(self, lower, upper, healthy, budget_s)
        self.available_budget(0.0)
        self.productive = (
            result > lower or self.metrics.get("ihs_new_conflicts", 0) > before
        )
        self.metrics[
            "focus_productive_steps" if self.productive else "focus_idle_steps"
        ] += 1
        return result

    C.__init__ = start
    C.available_budget = available
    C.step = advance
