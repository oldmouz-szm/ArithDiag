# ArithDiag

**v0.4.0 is the frozen final-test source. ArithDiag-LS is the main method;
ArithDiag-G is an optional backend replacement adapter.** Formal experiments
remain unstarted pending user approval. See the [frozen experiment protocol](docs/EXPERIMENT_PROTOCOL.md).
The common model uses conditional arithmetic equations. Big-M is generated only
when invoking the LS backend; the G backend compiles directly to digits and
indicators. See [representation and validation boundaries](docs/SEMANTIC_MODEL.md).

Component-level diagnosis of unsigned arithmetic circuits using integer models,
circuit-based candidate construction, arithmetic repair and certified conflict bounds.

ArithDiag has two backend configurations. They use the same circuit model,
preprocessing, internal search, proof policy and exact original-model validator.

| Configuration | Backend representation | Solver |
|---|---|---|
| **ArithDiag-LS** | Bounded integer quadratic Big-M constraints with audited wide-coefficient transport | Adapted LS-IQCQP |
| **ArithDiag-G** (optional) | Radix-256 integer digits, exact carry equations and indicator constraints | Gurobi |

The encodings suit their respective backends. A comparison evaluates complete
configurations; it does not isolate a solver change from a representation change.

Each complete adder or multiplier has one unit-cost abnormality variable.
Healthy components obey their function; faulty components may output any legal
value. Wiring, slices, widths and the single input/output observation always hold.
The objective is the number of faulty components. Injection metadata is never a
solver input or a stopping target.

## Requirements

The command-line workers and resource supervisor support Linux and WSL on x86-64.
The tested Python version is **3.14.4**; the Python core uses only the standard library.
ArithDiag-G additionally needs **gurobipy 13.0.3** and a valid Gurobi license.
ArithDiag-LS needs a C++17 compiler, GSL and Boost headers.

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r ArithDiag-G/requirements.txt  # ArithDiag-G only
make -C ArithDiag-LS/native -j2                               # ArithDiag-LS only
```

On Debian/Ubuntu the native development packages are `g++`, `make`, `libgsl-dev`
and `libboost-dev`. Set `GRB_LICENSE_FILE` in your environment if your Gurobi
installation needs a license file. Licenses and solver binaries are not distributed.

## Run an instance or a batch

Supply an external dataset directory containing `cases/<circuit>/netlist.v`,
`cases/<circuit>/observations_NNN.jsonl` and `library/*.v`. An `instances.json`
index is used when provided. The supported modules are explicitly registered in
`src/arithdiag/model.py`; the frontend does not infer arithmetic from arbitrary
Verilog. See [input and output formats](docs/INTERFACES.md).

```bash
.venv/bin/python -B run.py \
  --backend ArithDiag-LS \
  --dataset-root /path/to/dataset \
  --run-name example-ls --instances nl_ring16_u8/observations_045 \
  --time-limit 120 --seeds 1
```

This prepares and validates the manifest. Add **`--execute`** to start workers.
The root entry point defaults to ArithDiag-LS/full. All examples without
`--execute` prepare manifests only.
Repeat the identical command with `--execute` to resume after an interruption.
Use `--instances all` for the whole dataset; repeat `--dataset-root` to combine
external datasets. Each backend also has its own entry point:

```bash
.venv/bin/python -B ArithDiag-LS/run.py \
  --dataset-root /path/to/dataset --run-name example-ls \
  --instances all --time-limit 120 --seeds 1 --execute
```

Use `--concurrency 6 --cpus 0-5` for independent single-thread workers on six
configured CPUs, after checking physical topology and contention. Both configurations can be scheduled with
`--backend ArithDiag-G ArithDiag-LS`; their results remain separate runs.
Concurrency defaults to one, is capped at 100, and must not exceed the CPU list.
Coordinate other users of the same Gurobi license; the local WLS scheduler permits
at most two sessions and accounts for token expiry.

## Frozen LS ablations

| CLI variant | Active internal candidate search | Internal proof enhancement |
| --- | --- | --- |
| full | On | On |
| no-internal-search | Off | On |
| no-proof-enhancement | On | Off |
| backend-only | Off | Off |

All retain common preprocessing (including conservative dominance), circuit
initialization, static observed-cone conflicts/basic bounds, adapted LS component
actions, restarts and exact validation. Thus backend-only means after common
preparation and initialization, not the original unmodified LS-IQCQP. Basic U=L
can still finish an instance without LS. See [precise boundaries](docs/ABLATIONS.md).

```bash
# Preparation only; formal execution awaits approval
.venv/bin/python -B run.py \
  --dataset-root /path/to/dataset --run-name ls-ablations \
  --variants full no-internal-search no-proof-enhancement backend-only \
  --time-limit 120 --seeds 1,2,3
```

The G adapter supports full only and remains a backend replacement study.

## Search and proof

1. Normalize unconditional connections while constructing integer variables and substitute observations.
2. Apply healthy-value propagation, conservative dominance and residual decomposition.
3. Construct and exactly validate a circuit-based initial candidate.
4. Use proved conflicts, a reduced hitting-set master and bounded arithmetic repair to improve bounds and candidates.
5. Stop when a verified upper bound equals a certified internal lower bound.
6. Otherwise encode the residual model for the selected backend and continue budgeted internal reasoning during native search.
7. Restore every candidate to the original circuit and check it with Python integers before scoring it.

Initial and later internal work share one nonrenewing ledger of at most 50% of
the time remaining at internal entry after common processing, less a deadline
margin. Early return is allowed. This is an empirical scheduling parameter,
not a theorem; see [budget accounting](docs/INTERNAL_BUDGET.md).

Some instances finish before a native solver is invoked. `native_invocations`
records this explicitly. ArithDiag-LS retains joint component moves, division and
factor-pair proposals, health recomputation and stagnation restarts. ArithDiag-G
receives verified starts and candidate improvements; dynamically learned conflict
cuts and separate component-action callbacks are disabled in its production policy.

This is a budgeted, incomplete diagnosis procedure. A failed search, bounded factor
scan or UNKNOWN answer never establishes UNSAT. Internal integer certificates and
Gurobi native optimality reports are distinguished in the output. The latter are
solver reports, not independently checked formal proof files.

## Resources and result records

The wall-clock budget includes process startup, imports, reading, modeling,
preprocessing, all internal/native search and original integer verification.
Only candidates fully verified before the deadline are scored. Own optimality
certificates permit early exit; external reference values are never read.

Default guards are one thread and one configured CPU per worker, nice=10,
12 GiB per-process address space, 8 GiB sampled process-group RSS, at least
2.5 GiB host memory before launch and 2 GiB during execution. Failed memory
queries stop the batch. RSS is sampled, not a continuously enforced cgroup peak;
actual sampling gaps are recorded. License queue waits precede worker startup.

`results/<run-name>/` contains the manifest, status, attempts, environment records
and scalar run results. Timeouts and resource failures remain results; interrupted
environmental attempts are preserved for recovery. Diagnoses, signal assignments,
conflict members, generated models and raw solver streams are not result exports.

`SOURCE_MANIFEST.json` locks the published source tree. Preparation and recovery
reject source, configuration or dataset hash drift. Reviewed code changes require
regenerating that manifest with `tools/freeze_sources.py` and starting a new batch.

## Correctness checks

```bash
.venv/bin/python -B tools/check.py
.venv/bin/python -B tools/check.py --native
.venv/bin/python -B tools/check.py --gurobi  # needs an available license
```

Checks cover independent small-domain enumeration, connection normalization,
partial buses, transformation minima, conflict reliability, hitting-set bounds,
wide Big-M input audits, native component proposals, deadline scoring and recovery.
See [method and correctness boundaries](docs/METHOD.md).
The [general correctness obligations](docs/CORRECTNESS_OBLIGATIONS.md) remain
necessary for the paper; tests do not substitute for those arguments.

Old results remain archived under their original source versions. They must not
be relabeled or pooled as final v0.4.0 experiments.

Only ArithDiag source, tests, build instructions and documentation are included.
The [benchmark](https://github.com/oldmouz-szm/MBD-Benchmark) is maintained separately.
No datasets, competing baselines, environments, binaries, experiment outputs or
license files are part of this repository.

MIT license; see [third-party notices](THIRD_PARTY_NOTICES.md).
