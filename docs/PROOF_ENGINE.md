# Internal relations, conflict master and candidate search

The internal engine uses the common conditional integer circuit. Neither Big-M
nor a Gurobi model is required for internal search or proof. Bounded repair can
produce a witness; explained arithmetic refutation can produce a conflict. These
roles stay distinct. No heuristic repair failure is a refutation.

## Exact shared-product relations

From healthy equations u*v=P and u*w=Q with P,Q>0, the relation checker derives
Q*v-P*w=0. Each relation carries the union of healthy-component premises,
including assumptions used to derive P or Q. Zero products never justify
cancellation. Exact Fraction paths retain scaled affine equalities. Cycles,
domain restrictions, divisibility and univariate degree-at-most-two integer
roots may refute these premises. Unsupported multivariate states and bounded
or expired checks remain UNKNOWN. A surviving abstraction never proves circuit
feasibility. The ordinary explained interval checker is retained as well.

The relation pass gets at most 0.05 s and 25% of remaining consistency-query
credit; adaptive round limits remain 24/48/96. Fraction numerator/denominator
limits are 4096 bits. These limits affect how much reasoning is attempted;
failure to finish cannot produce a conflict.

## Resumable auxiliary master

Only proved conflicts enter the hitting-set master. Within the minimum-preserving
reduced domain, fixed AB choices are projected consistently. Independent parts
have disjoint component domains, so proved part lower bounds add. Rational
packing and complete search provide auxiliary bounds; they do not assert circuit
feasibility. See FRACTIONAL_PACKING.md and CORRECTNESS_OBLIGATIONS.md.

An immutable full edge family identifies a resumable session. Explicit DFS frames
and proved residual UNSAT states survive node/time slices. Changed families use
separate sessions; cached covers are checked against their exact family. Only
completed refutations raise a bound. Session eviction drops work, not proof
requirements. Existing limits include 16 sessions, 65,536 residual UNSAT entries
per engine and a 200,000-node decision request.

## Leave time for circuit checks

An IHS cover request receives at most half the current remaining internal grant,
subject to the existing minimum slice. If it is UNKNOWN, a greedy cover smaller
than verified U may still propose a healthy-assumption query. Its cardinality
may exceed the current k: that is neither SAT at k nor an UNSAT proof at k.
Only a subsequently proved conflict can strengthen the next master. The target
k remains the reliable current lower bound. Conflict coverage completed for
the current family does not establish that all necessary circuit conflicts are
known. The master can be exact while its circuit lower bound is still weak.

## Acceptance

Arithmetic repair uses bounded propagation, roots, factor proposals and branching
to construct candidates. Every candidate is restored and checked against the
full original integer circuit before updating U. The native LS numerical bound
never supplies an internal proof premise. A reliable internal L equal to valid U
proves minimum cardinality, subject to the reduction's preservation conditions.
Unknown checks only receive cooldowns, not blocking clauses. Dynamic new conflict
cuts are not sent to LS or G; backend LS retains the common initial static cones.

Finite tests are implementation evidence, not a general proof or a claim of
completeness. The standalone legacy affine checker and its regressions remain
available, but the active relation pass is relation_conflicts.py.
