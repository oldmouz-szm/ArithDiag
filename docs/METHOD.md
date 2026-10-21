# Model, search and proof boundaries

For every complete component c, AB(c) is binary and costs one. Healthy component
equations are o-a-b=0 or o-a*b=0. Faulty components release only their functional
equation. Signal domains, connections and observed input/output segments remain
mandatory. This is unsigned, single-observation, component-level weak-fault
diagnosis. A returned diagnosis need not identify the injected fault locations.

The common observation model stores these conditional equations directly.
Big-M is an LS backend encoding, not the shared representation.

## Construction and reduction

Unconditional equal bit segments are canonicalized while constructing the model.
Widths, slicing, repeated bits and zero extension remain explicit. A partially
observed bus is not treated as a fully fixed bus.

Healthy-value propagation requires an actually fixed healthy abnormality variable.
The conservative dominance reduction uses complete component dependencies and
total component functions. Under unit-cost weak faults, an upstream fault can be
replaced by a dominating component without increasing cardinality. The reduction
preserves the minimum cardinality, not every diagnosis identity. It is unsuitable
for enumerating all diagnosis sets. Independent groups include shared abnormality
variables in their connectivity; splitting by output alone is insufficient.

## Candidate construction is search

Circuit-forward initialization combines nominal values with the actual observed
segments. Arithmetic repair searches signal values for a proposed set of healthy
components. It uses propagation, exact integer roots, factor-pair proposals and
bounded branching. These are candidate-producing algorithms, not mere input
compression. A hitting-set cover alone is not a feasible circuit diagnosis.

Repair stops at time, node, depth and divisor-scan limits. Failure means UNKNOWN.
Every accepted candidate is restored and checked against the original model,
including all domains, connections, healthy functions, observations and polynomial
constraints. The exact verified abnormality sum is its upper bound.

## Internal proof

A proved conflict C certifies that the components in C cannot all be healthy.
Therefore every feasible diagnosis satisfies sum(AB(c) for c in C) >= 1.
The explanation engine tracks supports through conservative integer reasoning.
Only complete arithmetic contradictions or exhaustive bounded-domain checks may
produce conflicts. Heuristic repair failure never produces a conflict.

The hitting-set master contains only proved conflicts. AB variables fixed during
minimum-preserving reduction are projected consistently. Independent conflict
parts have disjoint component domains, so their reliable lower bounds add.
Cached part results require identical normalized edges. A completed at-most-k
refutation raises the lower bound; an interrupted master remains incomplete.
Unknown consistency states receive cooldowns rather than unsound blocking clauses.

The internal coordinator uses a verified incumbent and its own proved conflicts.
Numerical native bounds never become premises of an internal integer proof.
The frozen production policy allocates one nonrenewing ledger of 50% of the
time remaining at internal entry. Initial and later work share this ledger and
the same whole-worker deadline; see INTERNAL_BUDGET.md.

## ArithDiag-G

Each bounded integer is represented by radix-256 digits with an exact upper-bound
construction. Multiplication introduces small digit products and exact carry
equations. Digit product definitions are unconditional; the component function's
carry equations are guarded by its abnormality variable. Auxiliary variable bounds
must permit every legal faulty-component output. The encoding records and audits
its variables and linear, quadratic and indicator rows before optimization.

Native numerical warnings disable native lower bounds and native optimality
acceptance. Internal exact proofs can still finish independently. A Gurobi native
certificate additionally requires a matching exact witness, trusted native bound,
optimal status, no invalid candidates or callback errors, and completion before
the deadline. Native reports are distinct from independently checked proof files.

## ArithDiag-LS

The functional relation g=0 is guarded by two Big-M inequalities. M is computed
from the legal integer domains, so AB=0 restores the equation and AB=1 releases
it throughout those domains. Only when LS is invoked are these pairs generated. The native LP reader is audited against the integer
model. A redundant Big-M coefficient may be safely rounded outward only after
proving redundancy at AB=1; restrictive rows never receive that treatment. A
fixed-one auxiliary transports a nonrepresentable right-hand-side remainder
without losing integer precision. Every native witness is checked exactly.

Every 64 steps, the adapted kernel may try four component proposals. It combines
division and factor-pair proposals, joint signal modifications, wiring repair and
health recomputation. Exhaustive small factor ranges are limited to 4096;
large divisor scans to 20000. A bounded scan never proves absence of factors.
Stagnation restarts use 3 seconds without improvement and round caps of 5, 10 and
15 seconds. With interleaved50, internal work runs after the native round has
ended, so internal work does not consume a paused LS round's clock. The optional
legacy fraction50 policy retains within-round pauses. Both are single-core policies.
All rounds, audits and validation share the whole-process deadline.

## What a certificate means

An exact verified candidate gives U. Reliable internal reasoning gives L. L=U
proves minimum cardinality for the represented diagnosis task. Without a matching
certificate, a feasible candidate is not necessarily even inclusion-minimal.
Tests provide implementation evidence on enumerated models; they do not replace
a general mathematical argument or independently checked proofs for every run.
