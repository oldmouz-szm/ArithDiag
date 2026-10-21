# Frozen internal-engine budget: interleaved50

The v0.5.0 production default for both backend adapters is `interleaved50`.
`ARITHDIAG_INTERNAL_BUDGET_POLICY` may select explicit `fraction50` only for legacy
compatibility experiments. The effective policy is recorded in the manifest and
propagated to fresh workers and resumed runs. The final protocol fixes
interleaved50; do not mix the two policies in one result column.

## One nonrenewing ledger

At internal entry, after loading, reduction, initialization and enabled initial
conflict refinement, let R=max(0, global_deadline-entry_time-0.03 s), B=0.50*R.
All initial and later internal calls debit the same cap B. No restart or new
conflict renews it. The ledger counts the driver's whole wall time, including
arithmetic repair. Coordinator restoration, verification and publication remain
charged to the common worker deadline, rather than the driver ledger.

The first request is min(5 s, available credit), and may return early. After that
request, ordinary credit accrues at one second per second spent outside the
driver, up to the same cap. Time spent on internal work cannot earn itself more
credit. Requests are clipped to unspent credit and the common deadline.

## Backend integration

LS first runs a native round, terminates and drains it, and then requests internal
work between rounds. Native round caps remain 5/10/15 s and stagnation remains
3 s. Internal work therefore cannot expire a paused native round or trigger a
false native stagnation interval. A round ending on stagnation may advance all
remaining internal credit for one call; this borrows existing credit only. On
return or exception, the ordinary earned-credit function is restored. A better
validated candidate is available as the next round's warm start.

G receives the same cap and initial-request policy. Its existing callbacks may
request internal work with available credit; it does not implement LS rounds or
LS component actions. A licensed G run remains a separate opt-in acceptance.

All calls share the global deadline and one assigned CPU. Small non-preemptible
overshoots are measured, never refunded; a candidate or certificate finishing
late does not score. These are checked budgets, not hard-real-time guarantees.

## Ablations and compatibility

The remaining internal mechanism in each ablation uses the same policy. With
both active search and proof enhancement disabled, no coordinator or callbacks
run: the internal allocation is zero and LS receives remaining time. No disabled
mechanism waits artificially. Common construction, initialization, static
conflicts/basic bounds, LS actions and exact validation stay enabled.

The explicit legacy fraction50 policy can consume its 50% request before LS and
uses within-round paused callbacks. Its implementation is retained for
reproducibility. The lower-level standalone driver's older accrual guard is
replaced by run_initial before production work; it is not a second production
cap. Five seconds, 50%, and the stagnation/round lengths are disclosed empirical
scheduling parameters, not universal runtime-optimality or completeness claims.
