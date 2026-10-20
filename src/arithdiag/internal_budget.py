"""Frozen nonrenewing 50% internal-engine ledger; never a proof premise."""

import math
import os
import time

POLICIES = ("fraction50",)
FRACTIONS = {"fraction50": 0.50}


def selected_policy():
    policy = os.environ.get("ARITHDIAG_INTERNAL_BUDGET_POLICY", "fraction50")
    if policy not in POLICIES:
        raise ValueError("Unsupported internal budget policy")
    return policy


def policy_configuration(policy):
    if policy not in POLICIES:
        raise ValueError("Unsupported internal budget policy")
    return dict(
        budget_policy=policy,
        initial_request_s=None,
        internal_budget_fraction=FRACTIONS[policy],
        fraction_basis="remaining_after_common_processing",
        initial_and_later_share_one_ledger=True,
        later_accrued_policy_restored=False,
        early_return_allowed=True,
    )


def run_initial(coordinator, policy, deadline, result, strengthen, now):
    """Run one normal strengthening call with an explicit, deadline-safe grant.

    The ledger measures the unchanged driver's complete strengthening wall time,
    including its arithmetic repair. Coordinator validation/publication overhead
    remains part of the global deadline, rather than the driver's time ledger.
    """
    if policy not in POLICIES or not math.isfinite(deadline):
        raise ValueError("Invalid internal budget configuration")
    driver = coordinator.driver
    started = time.perf_counter()
    remaining = max(0.0, deadline - started - 0.03)
    initial_spent = driver.metrics["proof_strengthening_s"]
    if initial_spent != 0:
        raise ValueError("Initial budget must be configured before any driver work")
    cap = FRACTIONS[policy] * remaining
    request = cap
    result.update(
        budget_policy=policy,
        initial_phase_requested_s=request,
        initial_phase_start_total_s=now(),
        initial_phase_remaining_s=remaining,
        initial_phase_granted_s=0.0,
        initial_phase_actual_s=0.0,
        initial_phase_proof_spent_s=0.0,
        initial_phase_lower_before=coordinator.lower,
        initial_phase_original_proof_cap_s=driver.proof_cap_s,
        internal_budget_total_s=cap,
        internal_budget_fraction=FRACTIONS.get(policy),
        initial_phase_single_step=True,
        initial_phase_early_return_allowed=True,
        initial_phase_time_charged_to_later_quota=True,
        initial_phase_policy_restored=False,
    )
    driver.proof_cap_s = cap
    driver.metrics["adaptive_quota_cap_s"] = cap

    def ledger_available(requested):
        if not math.isfinite(requested) or requested <= 0:
            return 0.0
        return min(
            requested,
            max(0.0, cap - driver.metrics["proof_strengthening_s"]),
            max(0.0, deadline - time.perf_counter() - 0.03),
        )

    subsequent_available = ledger_available

    def initial_available(requested):
        allowed = subsequent_available(requested)
        if requested > 0:
            result["initial_phase_granted_s"] = max(result["initial_phase_granted_s"], allowed)
        return allowed

    driver.available_budget = initial_available
    try:
        strengthen(request)
    finally:
        driver.available_budget = subsequent_available
        result.update(
            initial_phase_actual_s=time.perf_counter() - started,
            initial_phase_end_total_s=now(),
            initial_phase_proof_spent_s=driver.metrics["proof_strengthening_s"] - initial_spent,
            initial_phase_lower_after=coordinator.lower,
            initial_phase_policy_restored=False,
            shared_ledger_active=True,
        )
