# ArithDiag

**Arithmetic-aware local search for component-level model-based diagnosis.**

ArithDiag models unsigned arithmetic circuits as integer quadratic constraints,
combines an adapted LS-IQCQP kernel with circuit preprocessing, arithmetic
neighborhoods and certified conflicts, and independently checks every accepted
candidate using exact integer arithmetic.

This is an initial source release. It does not contain final paper results or a
claim of superiority over SATbD, MaxSAT, or other diagnostic methods.

## Diagnostic task

Each complete adder or multiplier instance has one binary variable `AB(c)`.
A healthy component (`AB=0`) must implement its specified arithmetic function.
A faulty component (`AB=1`) may produce any output within its legal width.
Wiring and the observed top-level inputs and outputs remain enforced.
The objective is to minimize the number of abnormal components.

All configurations, including `baseline`, share the same normalized integer
model. Unconditional wire aliases use one variable from model construction;
slice boundaries are aligned across copies. Original signal/slice and wiring
maps are retained for initialization and exact original-circuit checks.

ArithDiag searches for one best feasible diagnosis within a whole-instance budget.
It is an incomplete search method. A candidate is marked optimal only when its
exactly checked cardinality matches an independently justified internal lower
bound. Search failure and timeouts never establish UNSAT. The method does not
enumerate all diagnoses.

Only one observation is used per run. Fault-injection metadata in JSONL comments
is ignored by the solver. No diagnosis members or assignments are saved.

## Build on Linux or WSL

Requirements: Python 3.10 or later, GNU Make, a C++17 compiler, GSL development
files and Boost headers. Python code uses the standard library only. Python 3.14
is supported by the release smoke checks; no SCIP, CPLEX, Gurobi or SAT installation
is required.

On a dedicated Ubuntu environment, dependencies can be installed with:

```bash
sudo apt-get update
sudo apt-get install build-essential libgsl-dev libboost-dev python3-venv git
git clone https://github.com/oldmouz-szm/ArithDiag.git
cd ArithDiag
python3 -m venv .venv
make -j1
make test PYTHON=.venv/bin/python
```

To use already installed headers/libraries without changing a system environment,
set `CPPFLAGS`, `LDFLAGS` and `LDLIBS` explicitly when running `make`. Build serially
to limit peak memory. Virtual environments and build products are not distributed.

## Read the benchmark without copying it into this repository

The released benchmark is separate:
[MBD-Benchmark v1.0.0](https://github.com/oldmouz-szm/MBD-Benchmark/tree/v1.0.0).
It contains 10 circuits and 450 single-observation diagnosis tasks,
derived from 150 physical fault configurations. Three observations of one physical
configuration are separate runs, not a shared multi-observation model.

```bash
git clone --branch v1.0.0 https://github.com/oldmouz-szm/MBD-Benchmark.git ../MBD-Benchmark
.venv/bin/python -B scripts/audit_dataset.py --dataset-root ../MBD-Benchmark
.venv/bin/python -B src/run.py \
  --dataset-root ../MBD-Benchmark --run-name smoke \
  --instances mac_bank16_u4/observations_001 --methods full \
  --seeds 1 --time-limit 10
```

A dataset already stored on a Windows drive can be supplied using its `/mnt/...`
path. Inputs are read-only; results must be written outside the dataset root.

```bash
.venv/bin/python -B src/run.py \
  --dataset-root ../MBD-Benchmark --run-name final-300s \
  --all --methods full --seeds 1 --time-limit 300
```

The last command is a potentially long campaign; it is not part of the smoke
tests. Runs are serial, and each method/seed/observation has its own 300-second
maximum. There are no hidden reference-optimum targets.

## Ablations

```bash
.venv/bin/python -B src/run.py \
  --dataset-root ../MBD-Benchmark --run-name ablation \
  --instances nl_ring16_u8/observations_001 \
  --methods baseline structure restart semantic full \
  --seeds 1 2 3 --time-limit 300
```

| Method | Configuration |
| --- | --- |
| `baseline` | LS-IQCQP search after common wire-alias normalization and observed-constant substitution, with seed/witness instrumentation and exact verification |
| `structure` | Healthy-value propagation, decomposition, conservative dominance reduction and basic output-cone conflict lower bounds |
| `restart` | Structure, circuit initialization and stagnation restarts |
| `semantic` | Restart plus arithmetic component neighborhoods |
| `full` | Semantic plus certified conflict refinement, explicit conflict constraints and dynamic conflict learning |

These are ArithDiag configurations, not implementations of SATbD or BE-RC2.
External baseline projects are not bundled with this source release.
Wire-alias normalization is common modeling work, not a `structure` ablation.
Historical results from v0.1.0 used different model construction and must not be
combined with new runs; the runner rejects changed code hashes on resume.

## Outputs and resource limits

Results are saved under `results/<run-name>/`, or `--output-dir`. The manifest
records parameters, source/binary/input hashes and runtime information. Instance
records contain status, first feasible and best verified cardinality times,
quality traces, internal bounds/certificates, variable/constraint counts, native
invocations and sampled process-group peak RSS. No assignments are retained.

The deadline includes worker startup, parsing, preprocessing, native input audits,
all subproblems/restarts and exact validation. Only candidates fully validated
before the deadline count. Process wall time and budget overrun are also recorded.

The controller uses a single worker at a time. Workers and native children share
one CPU affinity, run with lower priority and have a 2 GiB address-space limit per
process. The controller enforces a 1.5 GiB process-group RSS limit. Available host
memory must be at least 2.5 GiB before a run and 1.5 GiB during it. WSL queries
Windows host memory; native Linux reads `MemAvailable`. RSS is sampled every
50 ms, so extremely brief peaks may be missed.

A run name is bound to parameters and input/code hashes. Matching completed
instance records are reused; changed settings require a new run name.

## Scope and reproducibility

The parser accepts the project's restricted Verilog wiring subset and the
explicit module registry in `vendor/iqcqp_model.py`; it is not a general Verilog
frontend and does not infer arithmetic semantics from arbitrary gates.
The public benchmark's eight arithmetic modules are registered.

Some large weak-fault circuits are easy because a downstream faulty component can
explain many observations. Some instances are solved by preprocessing and bounds
without calling LS; inspect `native_invocations` before attributing performance
to the numeric kernel. Integer and Boolean variable counts are not comparable
memory units.

See [method details](docs/METHOD.md), [result schema](docs/RESULTS.md),
[publication contents](docs/PUBLICATION.md), [upstream provenance](reproducibility/upstream.json)
and [third-party notices](THIRD_PARTY_NOTICES.md).

Run self-contained correctness/native tests with `make test`. To check every
external observation's model, preprocessing and feasible initialization without
a solver campaign:

```bash
.venv/bin/python -B scripts/audit_dataset.py --dataset-root ../MBD-Benchmark --all
```

## Attribution

The LS-IQCQP kernel derives from
[INFORMSJoC/2025.1178](https://github.com/INFORMSJoC/2025.1178), commit
`d41da7f2cb1dbd03f3cf18c8508bb82080383a51`.
Please cite its [paper](https://doi.org/10.1287/ijoc.2025.1178)
and [software archive](https://doi.org/10.1287/ijoc.2025.1178.cd) when using it.
Classic MBD ideas used here include conflicts, conservative dominance,
healthy-state improvements and restarts; these are not claimed as new ideas.

ArithDiag-authored source is MIT-licensed. Original LS-IQCQP copyright and license
are retained. The separately published benchmark has its own licensing notices.
