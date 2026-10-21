# Standalone signed-affine regression checker

`affine_conflicts.py` retains the earlier standalone checker and its exhaustive
regressions. The active v0.5.0 IHS path calls `relation_conflicts.py` instead; see
[PROOF_ENGINE.md](PROOF_ENGINE.md). The bounded multi-square enumeration below
describes the standalone checker, not a completeness guarantee or an additional
active IHS pass. Its telemetry may be zero in production.

Active integer equalities may imply x=+/-r+d within a connected linear part.
The offsets are exact integers and every path carries the union of the healthy
assumptions justifying its edges. A cycle gives 0*r=b or +/-2*r=b: a nonzero
constant or failed integer divisibility proves its support inconsistent.
A determined root must satisfy every original domain. Its exact value can be
propagated with its explanation. Subsequent univariate degree-at-most-two
equations are checked by exact divisibility and integer discriminant roots,
including output squares. No unfixed root is guessed. A consistent abstraction,
round limit or deadline remains UNKNOWN. The ordinary original-model candidate
validator and the U=L proof acceptance rule remain unchanged.


For an unfixed affine root, healthy square-output relations in its component
give necessary restrictions on that root. If one factor's entire declared
integer domain has at most 4096 values, every value is enumerated, mapped to a
candidate root, and checked against all these square constraints and bounds.
No remaining candidate proves inconsistency; a unique remaining candidate may
be propagated. Both conclusions require completing the full domain before the
deadline. Shared-factor and cross-component correlations may be relaxed, so a
surviving candidate never proves circuit feasibility. Explanation supports union
all relations and domain-derived paths used in this check.
