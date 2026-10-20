# Frozen internal-engine budget

The only supported production policy is fraction50, used by both backends.
Legacy first-call constants and alternative fractions are not exposed in this
release. The supervisor records the policy and propagates it on resume.

At entry after loading, preprocessing, initialization and enabled initial conflict
refinement, R=max(0, global_deadline-entry_time-0.03 s) and B=0.50*R.
Initial and later internal calls draw from this single nonrenewing ledger.
An initial call may return early, including UNKNOWN; unused credit remains for
later checkpoints, not a waiting loop. Later requests are at most 0.75 s, subject
to the ledger and the common deadline, with at least 1 s between native checkpoints.
LS is paused during internal work so both use one assigned CPU.

The ledger measures the complete driver wall time, including arithmetic repair;
coordinator restoration/verification/publication is charged to the global deadline.
Small non-preemptible overruns are measured, never refunded. No late candidate or
certificate is scored. The existing proof_strengthening_s telemetry field includes
all internal driver time, including in the search-only ablation.

The low-level driver retains its standalone earned-credit guard for direct unit
checks. The production coordinator always installs the fraction50 ledger before
any work, replacing that guard. It is not a second production scheduling policy.

Ablations give the same fraction50 ledger to their remaining internal mechanism.
With both mechanisms disabled, the internal allocation is zero and LS receives
all remaining time. No disabled mechanism consumes artificial waiting time.
Therefore this measures each complete budgeted configuration, including the work
that can use time released by ablation. The 50% value is an empirical parameter;
no universal runtime-optimality or completeness claim follows from it.
