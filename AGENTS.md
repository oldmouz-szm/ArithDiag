# ArithDiag source maintenance

The main configuration is ArithDiag-LS; ArithDiag-G is an optional adapter.
Both use the common
integer modeling, preprocessing, arithmetic repair, proof and validation modules.
Keep one implementation of that common algorithm. Do not reintroduce experimental
dispatchers, competing baseline code, machine-specific paths or benchmark data.

The model is unsigned, whole-component, single-observation, unit-cost weak fault.
Preserve diagnosis semantics, search parameters, proof premises and deadlines.
UNKNOWN and heuristic failure never establish UNSAT. Native numerical bounds
are not premises for internal integer proofs. Do not export diagnosis members,
signal assignments, conflict members, raw solver streams, credentials or licenses.

Core performance work is frozen. Make substantive algorithm changes only as an
explicitly requested new version; preserve existing results and source snapshots.
Source reorganization must pass independent semantic and backend regression checks.
Regenerate SOURCE_MANIFEST.json only after reviewing a source change. New-code
experiments require a fresh batch and cannot be pooled with old-code records.

Use private environments. Keep default host memory protection at 2 GiB, with
2.5 GiB required before worker startup. Preserve single-thread workers, exclusive
configured CPUs, process-group RSS monitoring and interruption/recovery journals.

The v0.5.0 final-test protocol is docs/EXPERIMENT_PROTOCOL.md. Keep the four LS
variants in docs/ABLATIONS.md and interleaved50 production budget fixed. The
dataset is ArithDiag-Final576-v1 at MBD-Benchmark v2.0.0, directory final576_v1;
legacy fraction50 remains an explicit compatibility policy, not the final protocol. Formal experiments
require separate user approval; correctness/fixture regressions do not start them.
