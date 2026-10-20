# Frozen LS ablations

The study is a 2x2 design of active internal candidate search S and internal proof
enhancement P. Only these features differ; full is the production configuration.

| CLI variant | S | P |
| --- | --- | --- |
| full | 1 | 1 |
| no-internal-search | 0 | 1 |
| no-proof-enhancement | 1 | 0 |
| backend-only | 0 | 0 |

Common to all four: connection normalization, observation substitution, constants,
justified propagation, conservative dominance, decomposition, deterministic static
observed-cone conflicts, disjoint-packing lower bound, circuit initialization,
adapted LS moves, restarts, exact restoration/validation, deadline and resources.
There is no additional structural ablation in the main paper protocol.

S includes bounded arithmetic witness construction: propagation, roots, factor
proposals and branching for candidate healthy sets. Turning S off installs no
repair callback; proof consistency checks cannot publish signal witnesses instead.
Circuit initialization and native LS component moves remain on in every variant.

P includes initial conflict refinement (0.35 s cap), explained consistency
refutations, dynamic proved-conflict learning, exact conflict-master strengthening
and completed cardinality refutations. Turning P off calls none of these, publishes
no enhanced lower bound and learns no new conflicts.

Candidate health-set proposals necessarily use the common static conflict family.
In the search-only variant, the same cover generator proposes a size-k fault set,
then arithmetic repair tries to construct a circuit witness. A completed cover
refutation may advance a private proposal size but is never exported as an enhanced
circuit lower bound. Repair failure remains UNKNOWN, receives a cooldown and blocks
no health set. This shared proposal computation is disclosed, not credited as
proof enhancement. The search path can differ when P is off; this is a mechanism
ablation, not a claim that trajectories remain identical.

backend-only bypasses the internal coordinator and periodic pause/callback path.
It can still finish on a verified initialized U equal to the common basic L.
It is not a raw-LS baseline; label it 'without active internal search and proof
enhancement, after common preparation'. Never call it 'without initialization'.

Initial/later internal time shares one nonrenewing fraction50 ledger; released
budget is available to remaining work. All variants use fresh worker processes,
record actual flags in the manifest, and reject resume configuration drift.
The G adapter exposes full only; ablations isolate the main LS configuration.
