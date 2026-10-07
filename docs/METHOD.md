# Method and limitations

## Exact component model

For a component function residual `g=0`, two Big-M inequalities guard the
function with its binary abnormality variable. Bounds follow unsigned bit widths.
The registered functions specify complete addition or multiplication; wiring,
slices and zero extensions determine which bits are visible. Exact candidate
checking includes domains, all polynomial constraints, wiring, healthy functions
and every observed port.

Unconditional connection aliases are identified before signal variables are
allocated, for every configuration. Slice boundaries propagate across direct
copies, including slice and concatenation connections. Equal aligned slices
share one bounded integer; zero-padding slices are fixed to zero. Guarded
component functions never identify variables. Conflicting observations on a
shared variable are rejected instead of overwriting one another.

The model keeps original signal-to-variable slice maps and original wiring
metadata. Forward initialization, structural dependency analysis and exact
verification still use those original interfaces. Redundant alias equalities
are absent from the search polynomial model; no later alias-elimination pass
is needed. The construction preserves all weak-fault assignments and component
identities, unlike the subsequent minimum-cardinality dominance reduction.

Known inputs can make a product constant. The benchmark contains both
linearizable instances and products with unknown internal factors. A quadratic
representation alone does not establish nonlinear search difficulty.

## Search pipeline

1. Read one top-level netlist and component interfaces. Construct the common
   integer model with shared variables for unconditional connection aliases.
2. Attach one observation and substitute observed constants. Structural
   configurations additionally propagate precisely determined healthy values.
   Partial buses retain explicit bit segments and original signal mappings.
3. Apply conservative component dominance with a restoration map. This reduction
   preserves the minimum-cardinality search objective under the implemented
   weak-fault assumptions, but does not preserve all diagnosis identities.
4. Split the residual graph while including shared abnormality variables.
5. Construct and exactly check a circuit-based feasible initialization.
6. Derive proven conflicts using observed mismatch cones and conservative
   interval/finite-product checks. Add a conflict only after a certified
   contradiction; a failed or bounded search is UNKNOWN.
7. Run LS-IQCQP on unresolved groups. Stagnation restarts and groups share one
   deadline. Component moves include exact division, bounded factor search,
   joint repairs and health projection.
8. Restore candidates to the original model and verify using Python integers.
   Stop with an optimality certificate only when the accepted upper bound equals
   the internal lower bound.

A lower bound is obtained from pairwise disjoint proven conflicts. It may be weak.
Basic cone bounds are available from `structure` onward; `full` additionally
refines conflicts, adds explicit cuts and learns conflicts between rounds.
Conflict refinement has bounded work. Incomplete factor scans are heuristic and
never constitute a proof that no factors exist. Truncated low-bit products do not
receive invalid complete-product divisibility tests.

The standard configurations and numerical policies are recorded in
`reproducibility/upstream.json`. Classical conflict and dominance techniques are
not original contributions of this project.

## Native source provenance

`native/ls-iqcqp/` contains the adapted search kernel. The retained internal
`caiq_*` symbols and protocol names reflect the development name; they do not
denote another runtime dependency. `baseline/native/` freezes the earlier kernel
with explicit seed and transient witness/audit instrumentation.

`reproducibility/ls_iqcqp_changes.patch` records adapted C++ changes against the
pinned author source. Original author notices accompany both copies.
No historical binaries, package archives or downloaded Boost headers are shipped.

## Guarantees

Every scored candidate passes exact validation. Proven conflict cuts and
certificate flags have separate justification from local-search success.
The algorithm is not generally complete, does not enumerate all diagnoses and
cannot prove UNSAT from a failed search.

Small exhaustive tests check transformations and conflicts against the original
model's feasible assignments. Native tests independently audit the parsed
polynomial and validate component-move witnesses. These checks support the
implementation; they do not replace a formal general proof in a paper.
