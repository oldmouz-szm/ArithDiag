# Final experiment protocol (frozen; execution awaiting approval)

Source: ArithDiag v0.4.0. Main method: ArithDiag-LS/full. Optional replacement:
ArithDiag-G/full. This file specifies future experiments and contains no claim
that they have been run. Historical development records stay separately archived.

## Task and data

Whole-component, unsigned, single-observation, unit-cost weak-fault diagnosis.
Minimize fault count within the budget; only a valid certificate proves minimum
cardinality. Do not conflate inclusion-minimality and minimum cardinality.
Connection, slice, width and observation constraints always hold. Injected locations
are analysis metadata only, never input to initialization, constraints or stopping.

Use all 594 frozen tasks: 450 original and 144 supplementary observations, 18
circuit families. Before execution freeze exact dataset commits, full instance
list, file hashes and physical-fault grouping. Keep correlated observations and
seeds within their physical fault group during resampling. Report both datasets
and every family, including residual unknown-factor products and search group size.
These datasets have been used during development; do not call them an unseen test set.

## Main methods and repetitions

| Method | Fixed implementation policy | Repetitions |
| --- | --- | --- |
| ArithDiag-LS | full, fraction50, adapted LS | Seeds 1,2,3 |
| BE-RC2 | Basic component encoding, unit soft !AB, DOE=false; official RC2/Glucose3 | Once if deterministic |
| SATbD-C | Faithful paper-flow component adaptation; BEE2017, CryptoMiniSat2.5.1 | Once if deterministic |
| SMT-Int | Integer semantics and native Optimize; no binary cardinality search | Once if deterministic |
| SAFARI-C | Component weak-fault adaptation; incremental SAT; disclosed random start; M=component count, budget-driven restarts | Seeds 1,2,3 |

Actual library/backend versions, all parameters and seeds must be frozen in an
execution manifest. Any randomized external baseline uses seeds 1,2,3 instead of
one run. RC2 retains the validated Basic Encoding and options adapt=false,
exhaust=false, incr=false, minz=false, process=0, trim=0 and verbose=0; no DOE.
SAFARI UNKNOWN cannot accept a candidate or prove infeasibility. SATbD's output-
health equivalence preserves minimum cardinality under these task assumptions,
not all nonminimal weak-fault assignments. Preserve its original optimizations;
state the component adaptation and exact-version reconstruction limits.

Do not include baseline implementation code in this source release. Validate all
baseline candidates against original circuit semantics in the external controller.
Optional ArithDiag-G replacement uses the same 594 tasks, seeds 1,2,3 and common
policy. Its encoding differs by design; compare whole backend configurations.

## Minimal main-paper ablations

Use full and the three variants in ABLATIONS.md, seeds 1,2,3 on all 594 tasks.
They respectively remove active internal search, proof enhancement, or both.
Preprocessing, initialization, static conflicts/basic bounds and adapted LS stay
common. No structural ablation is required for the main table; preserve the prior
dominance evaluation as supporting evidence, without pooling it into this batch.

## Time and resources

Primary: 120 seconds end-to-end per method/instance/seed. Checkpoints 1,5,10,30,60,
120 seconds are extracted from the same verified improvement trajectory.
The fraction50 policy is frozen (see INTERNAL_BUDGET.md), not retuned per instance.
Early exit only on an internally established optimum or valid native completion.
External reference optima are never available to any worker.

Cold fresh workers include startup/imports, read/build/reduction, encoding, all
internal/native search and proof, and complete exact verification. Late validation
or certificates do not score. SATbD compile reuse is a separately labeled online
study with offline cost and amortization; do not mix it into the cold main table.
License queue waits are logged separately; in-worker acquisition remains timed.

One compute thread and one physical core per run for every method. Start with six
concurrent tasks only after a contention calibration; lock topology, concurrency,
method-order rotation and order seed in the manifest. More cores/RAM do not prove
that timing is unaffected by shared CPU, cache, memory or storage contention.
Keep other jobs off assigned cores and record environment conditions.

Uniform limits: 8192 MiB sampled process-group RSS, 12288 MiB per-process address
space, nice=10; host available memory >=2.5 GiB before launch and >=2 GiB while
running. Stop on failed memory queries. Sample all descendants every 50 ms; record
actual gaps and overshoot. These limits are resource conditions of the conclusions,
not a continuously enforced RSS/cgroup cap. Record memory termination separately
from timeout/error and retain any earlier valid candidate.

Budget robustness: independently run ArithDiag-LS/full and BE-RC2 on all 594 tasks
with 300 seconds, seed 1. Do not substitute the 120-second checkpoints of these
runs for the primary 120-second experiment, because the internal fraction depends
on the total budget. No unapproved execution is started by this protocol.

## Records and analysis

Freeze source and binary hashes, compiler/options, Python and solver versions,
machine/kernel/topology, limits, complete instance/group table and order. Keep
all attempts and resume journals; reject source, input or configuration drift.
Changed code needs a new batch. Retain failures; environmental interruptions can
be rerun with both attempts preserved. Algorithmic memory failures are results.

Per run: identity and flags, feasibility, best cardinality (null if absent), first
feasible and first final-best times, improving trace, lower-bound trace/source,
proof flag/time/type, phase times, complete wall time/overshoot, peak group RSS,
original/residual/backend sizes, unknown products, search-group sizes, backend
invocations, witness/proof origins, internal search/proof/native counters, invalid
candidate count, errors and termination. Never export members or signal values.

Construct references after experiments, as proven_optimum or best_known with
source run/configuration/model hashes and evidence. An exact solver's completion
report is distinguished from an independently checked proof file. Minimum across
feasible results is only a best-known upper bound until justified. Injected fault
count is not an optimum label. Do not feed references back into workers.

Report feasibility, checkpoint quality, reference-optimum attainment (and labeled
subset size), best-known attainment separately, own optimality proofs, RSS and
resource failures. Compare attainment times with attainment times and proof times
with proof times. PAR-2 must name its task: success uses event time, failure uses
240 seconds for the primary budget. Common-success means are supplementary and
must state sample size; do not hide failures by averaging successful runs only.

Score each seed, then summarize means/dispersion; never choose best-of-three
against a single deterministic run. Use paired confidence intervals by physical
fault groups, keeping their observations and seeds together. Provide family tables,
paired ablations, time-to-target and memory plots. Explain pre-backend resolutions
and backend improvements rather than attributing everything to LS or Gurobi.

## Before authorizing execution

Pass correctness/native/offline-G and ablation gate checks. Verify baseline adapters,
record schemas, group mapping, timeout/memory interruption and recovery. Freeze an
external experiment manifest with actual versions and datasets. Submit that concrete
plan for user approval. Until then the project remains frozen without formal runs.
