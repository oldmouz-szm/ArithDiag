# Correctness arguments required for the paper

The regression suite checks implementations on independent finite models. It is
not a general proof and is not evidence of completeness of heuristic search.
The paper and artifact must state and justify these assumptions and invariants.

1. Original conditional integer model iff the supported unsigned whole-component
   weak-fault circuit semantics, including observations, domains, slices, zero
   extension and partial buses. The explicit module registry is part of the scope.
2. Connection normalization/substitution preserve assignments. Healthy propagation
   requires AB fixed healthy; it never guesses the physical injected health state.
3. Conservative dominance preserves minimum cardinality with a restoration map
   under total component functions and unit weak-fault cost. It does not preserve
   every diagnosis identity or justify fault localization claims. Prove its graph
   conditions; residual decomposition must include shared AB variables.
4. Every conflict has a sound original-model support; incomplete interval/factor
   reasoning returns UNKNOWN. Track which arithmetic checks are exhaustive.
   Shared-product cancellation requires its positive-product premises; rational
   affine paths, bounds, cycle contradictions and integer roots must carry every
   healthy assumption used. Zero products do not permit cancellation.
5. Projecting conflicts into the minimum-preserving reduced domain is sound for
   optimum bounds. Disjoint conflict parts add; caches require identical normalized
   conflict families. Completed master refutations alone raise L. UNKNOWN never
   creates blockers. Search-only proposal sizes are not published lower bounds.
   Resumable DFS frames and residual UNSAT facts are valid only for the same
   immutable edge family. Interruptions cannot promote partial work to UNSAT.
   A larger auxiliary cover is not SAT at a smaller target k, and refuting that
   cover does not by itself refute all size-k circuit diagnoses.
6. Every accepted U comes from exact restoration and full original integer
   verification. Native numerical lower bounds cannot be internal proof premises.
   U=L proves minimum cardinality, not identification of the injected fault set.
7. LS Big-M bounds cover the full legal faulty domain. Prove coefficient/RHS
   transport equivalence, including outward rounding only for redundant guarded
   terms and fixed-one remainders. A native input audit and exact witness check
   are separate safeguards; floating-point local search remains incomplete.
8. G digit/carry bounds admit every legal signal and faulty output; guarded
   functional rows and unconditional auxiliary definitions must be distinguished.
   Numerical warning guards and native optimality completion are solver-report
   evidence, not independently checked mathematical proof files.
9. All scored candidates/proofs complete before the common deadline; reference
   values and fault injection metadata cannot affect search or early stopping.
   Memory/timeout/interruption remain separate from logical satisfiability.

State where arguments follow by construction and where detailed lemmas remain to
be written. Do not claim a proof-assistant-checked implementation or claim that
unit tests alone establish these general properties.
