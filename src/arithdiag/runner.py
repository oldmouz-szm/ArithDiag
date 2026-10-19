"""Portable Linux batch preparation with explicit external datasets and recovery."""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

from arithdiag import __version__
from arithdiag import resources as monitor

ROOT = Path(__file__).resolve().parents[2]
BACKENDS = ("ArithDiag-G", "ArithDiag-LS")
SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
INSTANCE = re.compile(r"[A-Za-z0-9_]+/observations_[0-9]+\Z")


def verify_sources():
    """Reject changes to a published source snapshot before preparing or resuming."""
    manifest = monitor.read(ROOT / "SOURCE_MANIFEST.json")
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        if not path.resolve().is_relative_to(ROOT) or not path.is_file():
            raise ValueError("Missing or invalid source path: " + relative)
        if monitor.sha(path) != expected:
            raise ValueError("Published source changed: " + relative)
    return manifest


def resolve_input(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Missing input or dataset path escape: " + str(relative))
    return path


def discover(root):
    """Use an external instance list, or discover integer observations in cases/."""
    index = root / "instances.json"
    if index.is_file():
        rows = monitor.read(index)
        rows = rows if isinstance(rows, list) else rows["instances"]
    else:
        rows = []
        for netlist in sorted((root / "cases").glob("*/netlist.v")):
            for observation in sorted(netlist.parent.glob("observations_[0-9]*.jsonl")):
                rows.append(
                    dict(
                        instance_id=netlist.parent.name + "/" + observation.stem,
                        netlist=str(netlist.relative_to(root)),
                        observation=str(observation.relative_to(root)),
                        library_dir="library",
                    )
                )
    if not rows:
        raise ValueError("No integer observations in dataset: " + str(root))
    seen = set()
    for row in rows:
        instance = row["instance_id"]
        if not INSTANCE.fullmatch(instance) or instance in seen:
            raise ValueError("Invalid or duplicate instance ID: " + instance)
        seen.add(instance)
        circuit, observation = instance.split("/")
        # The worker's loader uses this layout; reject a misleading instance list.
        if (
            resolve_input(root, row["netlist"])
            != (root / "cases" / circuit / "netlist.v").resolve()
        ):
            raise ValueError("Instance netlist does not match its ID")
        if (
            resolve_input(root, row["observation"])
            != (root / "cases" / circuit / (observation + ".jsonl")).resolve()
        ):
            raise ValueError("Instance observation does not match its ID")
        library = (root / row.get("library_dir", "library")).resolve()
        if library != (root / "library").resolve() or not library.is_dir():
            raise ValueError("Dataset requires a library/ directory")
    return rows


def backend_configuration(backend):
    path = (
        ROOT
        / backend
        / ("configuration.py" if backend == "ArithDiag-G" else "worker.py")
    )
    spec = importlib.util.spec_from_file_location(
        "_arithdiag_config_" + backend[-2:], path
    )
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        sys.path.insert(0, str(path.parent))
        spec.loader.exec_module(module)
        return module.configuration()
    finally:
        sys.path[:] = before


def prepare(args, out):
    release = verify_sources()
    cpus = monitor.parse_cpus(args.cpus)
    if not set(cpus) <= os.sched_getaffinity(0):
        raise ValueError("Requested CPU is outside current affinity")
    if not 1 <= args.concurrency <= min(100, len(cpus)):
        raise ValueError("Concurrency must be 1..min(100, number of CPUs)")
    if not math.isfinite(args.time_limit) or not 0 < args.time_limit <= 3600:
        raise ValueError("Time limit must be finite and in (0, 3600] seconds")
    seeds = [int(x) for x in args.seeds.split(",")]
    if (
        len(set(seeds)) != len(seeds)
        or not seeds
        or any(x < 0 or x > 2_000_000_000 for x in seeds)
    ):
        raise ValueError("Seeds must be distinct integers in 0..2000000000")
    selected = None if args.instances == "all" else args.instances.split(",")
    if selected is not None and (
        len(set(selected)) != len(selected)
        or any(not INSTANCE.fullmatch(x) for x in selected)
    ):
        raise ValueError("Invalid or duplicate instance selection")
    configurations = {name: backend_configuration(name) for name in args.backends}
    roots = {}
    cases = []
    inputs = set()
    for supplied in args.dataset_root:
        root = Path(supplied).expanduser().resolve()
        name = root.name
        if not root.is_dir() or not SAFE_NAME.fullmatch(name) or name in roots:
            raise ValueError(
                "Dataset directories must exist and have distinct simple names"
            )
        roots[name] = str(root)
        for row in discover(root):
            if selected is not None and row["instance_id"] not in selected:
                continue
            paths = {
                key: resolve_input(root, row[key]) for key in ("netlist", "observation")
            }
            observation_sha = monitor.sha(paths["observation"])
            if row.get("sha256") and row["sha256"] != observation_sha:
                raise ValueError("Observation SHA-256 mismatch: " + row["instance_id"])
            inputs.update(paths.values())
            inputs.update((root / "library").glob("*.v"))
            if row.get("bit_observation"):
                inputs.add(resolve_input(root, row["bit_observation"]))
            # Physical fault identities are analysis metadata, never worker arguments.
            metadata = {
                key: row[key]
                for key in (
                    "fault_pattern_id",
                    "observation_id",
                    "component_count",
                    "injected_component_count",
                    "injected_gate_count",
                    "structure_type",
                )
                if key in row
            }
            cases.append(
                dict(
                    metadata,
                    dataset=name,
                    instance_id=row["instance_id"],
                    circuit=row["instance_id"].split("/")[0],
                    sha256=observation_sha,
                )
            )
        for name2 in (
            "instances.json",
            "circuits.json",
            "dataset_config.json",
            "SHA256SUMS",
        ):
            if (root / name2).is_file():
                inputs.add(root / name2)
    if not cases or (
        selected is not None and set(selected) != {r["instance_id"] for r in cases}
    ):
        raise ValueError("No cases selected or requested instance is missing")
    native = ROOT / "ArithDiag-LS/native/build/arithdiag-ls"
    if "ArithDiag-LS" in args.backends and not native.is_file():
        raise ValueError("Build ArithDiag-LS first: make -C ArithDiag-LS/native")
    if (
        "ArithDiag-G" in args.backends
        and args.execute
        and importlib.util.find_spec("gurobipy") is None
    ):
        raise ValueError(
            "Install the pinned ArithDiag-G/requirements.txt in this Python environment"
        )
    plan = []
    for seed in seeds:
        for row in cases:
            for method in args.backends:
                cpu = cpus[len(plan) % len(cpus)]
                run_id = (
                    row["dataset"]
                    + "__"
                    + row["instance_id"].replace("/", "__")
                    + "__"
                    + method
                    + "__s"
                    + str(seed)
                )
                plan.append(
                    dict(
                        row,
                        run_id=run_id,
                        method=method,
                        configuration=method,
                        effective_configuration=configurations[method],
                        seed=seed,
                        wave=0,
                        position=len(plan),
                        affinity_cpu=cpu,
                        preferred_affinity_cpu=cpu,
                    )
                )
    settings = dict(
        time_limit_s=float(args.time_limit),
        concurrency=args.concurrency,
        cpus=cpus,
        dataset_roots=roots,
        rss_sampling_period_s=0.05,
        host_check_period_s=1.0,
        host_start_min_gib=2.5,
        host_stop_min_gib=2.0,
        rss_limit_mib=8192,
        address_space_limit_mib=12288,
        threads=1,
        nice=10,
        python=str(Path(sys.executable).absolute()),
        external_reference_stopping=False,
        raw_streams_persisted=False,
        diagnosis_export=False,
        assignment_export=False,
        budget_scope="worker launch through original integer verification and proof",
        wls_max_sessions=2,
        wls_token_duration_minutes=5,
        wls_token_refresh=1.0,
        wls_wait_outside_budget=True,
    )
    sources = {ROOT / relative for relative in release["files"]}
    sources.update({ROOT / "SOURCE_MANIFEST.json", Path(sys.executable).resolve()})
    if "ArithDiag-LS" in args.backends:
        sources.add(native)
    dependency_versions = {}
    if "ArithDiag-G" in args.backends:
        try:
            dependency_versions["gurobipy"] = importlib.metadata.version("gurobipy")
            distribution = importlib.metadata.distribution("gurobipy")
            sources.update(
                Path(distribution.locate_file(p)).resolve()
                for p in distribution.files or []
                if str(p).endswith((".py", ".so", ".pyd", "METADATA"))
                and Path(distribution.locate_file(p)).is_file()
            )
        except importlib.metadata.PackageNotFoundError:
            dependency_versions["gurobipy"] = None
    manifest = dict(
        schema="arithdiag-batch-v1",
        version=__version__,
        root=str(ROOT),
        created_utc=monitor.utc(),
        settings=settings,
        plan=plan,
        configurations=configurations,
        source_hashes={str(p): monitor.sha(p) for p in sorted(sources)},
        input_hashes={str(p): monitor.sha(p) for p in sorted(inputs)},
        dependencies=dependency_versions,
        environment=monitor.environment(),
        reference_input=False,
        diagnosis_export=False,
        assignment_export=False,
    )
    path = out / "manifest.json"
    if path.exists():
        prior = monitor.read(path)
        for key in (
            "version",
            "settings",
            "plan",
            "configurations",
            "source_hashes",
            "input_hashes",
            "dependencies",
        ):
            if prior[key] != manifest[key]:
                raise ValueError("Resume configuration drift: " + key)
        manifest = prior
    else:
        monitor.save(path, manifest)
        monitor.save(
            out / "status.json",
            dict(
                state="prepared",
                total_runs=len(plan),
                completed_runs=0,
                workers_started=False,
            ),
        )
    monitor.check(manifest)
    return manifest


def main(default_backend="ArithDiag-G"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        dest="backends",
        choices=BACKENDS,
        nargs="+",
        default=[default_backend],
    )
    parser.add_argument(
        "--dataset-root",
        action="append",
        required=True,
        help="external dataset directory; repeat to combine datasets",
    )
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--cpus", default=str(min(os.sched_getaffinity(0))))
    parser.add_argument("--seeds", default="1")
    parser.add_argument("--instances", default="all")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="start workers; without this flag only prepare a manifest",
    )
    args = parser.parse_args()
    if not SAFE_NAME.fullmatch(args.run_name) or args.run_name in (".", ".."):
        parser.error("Invalid run name")
    if len(set(args.backends)) != len(args.backends):
        parser.error("Duplicate backend")
    state = ROOT / ".state"
    state.mkdir(exist_ok=True)
    with (state / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = args.output_root.expanduser().resolve() / args.run_name
        out.mkdir(parents=True, exist_ok=True)
        manifest = prepare(args, out)
        if not args.execute:
            print(
                json.dumps(
                    dict(
                        prepared=True,
                        workers_started=False,
                        runs=len(manifest["plan"]),
                        manifest=str(out / "manifest.json"),
                    )
                )
            )
            return 0
        status = monitor.execute(out, manifest)
        return 0 if status["state"] == "completed" else 2
