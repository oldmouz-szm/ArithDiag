# v0.5.0 final-test freeze

ArithDiag-LS/full is the main method; ArithDiag-G/full is an optional backend
replacement. The default policy is interleaved50, matching the reviewed
v0.4.10.dev1 experiment configuration. Only the policy default, version/manifest
generation, regression entry and release documentation are changed in this
engineering promotion. The relational proof, resumable master, preprocessing,
repair, LS native actions and acceptance implementations are retained.

The external final data is ArithDiag-Final576-v1: MBD-Benchmark v2.0.0, commit
eec655263e3c388211e75b8cc4e69b78396a6c37, directory final576_v1. Its 576 tasks
cover 36 circuits and 192 fault groups. Selection uses historical runtimes and
must be disclosed. No data or competing baseline code is included here.

The four LS variants remain full, no-internal-search, no-proof-enhancement and
backend-only. Common preprocessing, initialization, static/basic bounds, LS
actions and validation stay enabled. Backend-only is not raw LS. Legacy
fraction50 is retained as an explicit compatibility override; the final protocol
uses interleaved50 for every applicable configuration.

## Release gate

Run tools/check.py --native on Linux in fresh test processes. This includes
source/version integrity, conditional-model/encoding equivalence, 128 independent
models and 384 transformations, conflict and hitting-set ground truth, relation
supports, resumable/changed-family master state, fake-clock interleaved budget
and stagnation advance, 65-bit Big-M boundaries, native witnesses/actions, and
fresh-worker four-variant/recovery checks. The default entry now includes
check_schedule.py, check_master.py and check_affine.py. Offline G checks use a
recording stub and never acquire a license. Live G checks remain explicitly
opt-in and are not implied by passing the LS release gate.

Rebuild LS from source, compare its binary and core implementation to the
reviewed candidate, check final576 data discovery and preparation without
--execute, and repeat regressions from the clean Git archive. The source-only
Git tag and SOURCE_MANIFEST.json are the published locks; compiler/options and
binary hashes are additionally recorded in each external execution manifest.

Tests do not replace the general arguments in CORRECTNESS_OBLIGATIONS.md or
independent proof-certificate checking. Historical results keep their original
versions and cannot be relabeled as v0.5.0 results. No formal benchmark is
authorized or launched by this release. See EXPERIMENT_PROTOCOL.md before
requesting execution approval.
