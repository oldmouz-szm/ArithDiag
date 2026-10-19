# External input and scalar results

Dataset layout:

```text
dataset/
  instances.json                 # optional index
  cases/<circuit>/netlist.v
  cases/<circuit>/observations_NNN.jsonl
  library/<registered-module>.v
```

An observation contains exactly two lines: a `# ` comment with a JSON header
whose `circuit` matches the case name, then one JSON object with `inputs` and
`outputs` maps. Whole-port values are hexadecimal strings such as `"0x03"`.
Alternatively, provide all port bits as integer 0/1 values keyed by `name[bit]`.
Only top ports are observed. The header's circuit identity is checked; fault
injection locations never supply constraints.

An optional instance index is a list, or an object with an `instances` list. Each
entry contains `instance_id`, `netlist`, `observation`, and optionally
`library_dir`, `sha256`, `bit_observation` and analysis grouping/count fields.
Paths are relative to the dataset root and cannot escape it. The worker requires
the paths to match its circuit/observation ID. The integer observation's SHA-256
is checked when supplied. All relevant input files are hashed into the batch
manifest. The runner creates no observation files and never rewrites a dataset.

The model registry assigns addition or multiplication to explicit module names.
This supported Verilog subset includes unsigned ports, named component instances,
connections, slices, concatenation and zero extension. Unsupported syntax or
modules are rejected. There is no automatic recognition of arbitrary gate networks
and no joint multi-observation interface.

Each run identifies its dataset, circuit, observation, backend and seed. Outputs
include a strictly improving `{total_s, cardinality}` trajectory, first/best
verified candidate times, lower bounds and their sources, proof type and time,
phase times, original/residual model sizes, native invocations, search counters,
sampled peak process-group RSS, exit status and termination reason.

Phase times can overlap and must not be added blindly. Complete process time is
the authoritative budget scope. Backend variable counts describe different
representations and are not a substitute for measured RSS. Backend encoding
fields are absent when internal reasoning finishes before encoding; absence is
not a zero-variable backend model.

Feasibility, proof and termination are separate. A run may have an exactly
verified candidate and then hit its memory or time limit. Missing candidates use
`null`, not zero. A proof is retained only when its timestamp is within budget
and its lower bound equals the verified candidate cardinality. Candidate sets,
signal values and conflict members stay transient and are not exported.

`records/` retains scored results, including algorithmic resource failures.
`attempts/` also retains environmental interruptions. Resuming recovers only
processes carrying the interrupted attempt's ownership token and retries
environmental attempts. A result from a foreign manifest cannot be resumed.
