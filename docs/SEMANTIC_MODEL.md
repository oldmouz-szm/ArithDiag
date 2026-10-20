# Independent semantic-model refactor

This independent version descends from frozen v0.2.0, commit
7160ec30d267055b3272927e59ce255d939c596b. Existing code and experiment results
are retained separately. It is not a rerun or replacement of the frozen cohort.

## Backend-neutral contract

The original observation model stores bounded integer variables, wiring and
observations, unit-cost abnormality variables, and one conditional equality per
component: AB(c)=0 implies g_c=0. There are no Big-M coefficients or paired
Big-M rows in the shared model, reduction, arithmetic repair or proof engine.
Original-circuit validation checks the conditional equations and signal-level
semantics using Python integers.

Reduction preserves the existing dominance and propagation policy. Conditional
rows include their shared abnormality variable in connectivity. A constant false
conditional equation is retained with its guard; it is not treated as an
unconditional contradiction. A constant true conditional equation is redundant.

## Backend boundary

Only ArithDiag-LS/native_helpers.py lowers conditional rows into Big-M pairs.
It is invoked when residual LS solving is necessary. Its coefficients use the
same original observation domains as frozen v0.2.0, avoiding an additional
change to coefficient-tightening policy during the representation comparison.
LP export, wide-coefficient transport and native parser audits reside under
ArithDiag-LS/native_io.py. Every resulting candidate is still checked against
the original conditional circuit semantics.

ArithDiag-G directly reads conditional healthy equations and generates
radix-256 digit products, carries and indicators. Its input audit checks the
semantic contract directly, with no intermediate Big-M guard construction.
The native numerical-report policy remains unchanged.

## Preserved algorithm policy

Initialization, proof premises, bounded arithmetic repair, conflict learning,
proof quotas, backend scheduling, LS joint moves, restarts, and deadlines retain
the frozen policy. New conflicts are not dynamically injected into either
backend. All variants use original-integer witness validation. Source/model
statistics change their meaning: a semantic component contributes one
conditional row, while LS later creates up to two guarded rows. Variable and
constraint counts must identify their representation.

## Checks without Gurobi use

check_g_encoding_offline.py exercises the actual G encoder with a recording
stub. It checks emitted algebra, wide assignments and indicator activation,
without loading the Gurobi SDK, starting a license session or optimizing. It
does not replace actual Gurobi integration/readback checks. Those remain
explicitly opt-in and are excluded from this refactor's requested test run.

Finite exhaustive tests are implementation evidence, not a general formal
proof of the full algorithm. Delayed Big-M lowering is equivalent on bounded
integer domains because its domain-derived guards are redundant at AB=1 and
reduce to the original equality at AB=0.
