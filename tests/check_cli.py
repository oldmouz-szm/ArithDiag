"""Exercise real fresh workers, process supervision and no-rerun resume behavior."""

from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import tempfile

from fixture_data import dataset

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--backend", choices=("ArithDiag-G", "ArithDiag-LS"), default="ArithDiag-LS"
)
parser.add_argument("--variants", nargs="+", default=["full"])
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="arithdiag-cli-") as temporary:
    base = Path(temporary)
    inputs = dataset(base / "fixture")
    command = [
        sys.executable,
        "-B",
        str(ROOT / args.backend / "run.py"),
        "--dataset-root",
        str(inputs),
        "--run-name",
        "smoke",
        "--output-root",
        str(base / "runs"),
        "--time-limit",
        "3",
        "--variants",
        *args.variants,
        "--cpus",
        str(min(os.sched_getaffinity(0))),
        "--execute",
    ]
    first = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert first.returncode == 0, first.stderr
    out = base / "runs/smoke"
    records = [json.loads(p.read_text()) for p in (out / "records").glob("*.json")]
    assert len(records) == 2 * len(args.variants)
    for variant in args.variants:
        subset = [r for r in records if r["variant"] == variant]
        assert sorted(r["best_cardinality"] for r in subset) == [0, 1]
        assert all(r["effective_configuration"]["variant"] == variant for r in subset)
        if variant == "backend-only":
            assert all(r["coordination_calls"] == 0 for r in subset)
        if variant in ("no-proof-enhancement", "backend-only"):
            assert all(r["initial_refinement_checks"] == 0 for r in subset)
    assert all(
        r["own_optimality_certificate"] and r["has_verified_feasible"] for r in records
    )
    assert all(
        r["method"] == args.backend
        and r["score_eligible"]
        and r["native_invocations"] == 0
        for r in records
    )
    assert all(
        r["peak_rss_mib"] > 0
        and (
            r["rss_group_resident_sample_count"] > 0
            or (r.get("rss_leader_initial_mib") or 0) > 0
        )
        for r in records
    )
    assert all(r['bigm_encoding_invocations'] == 0 for r in records)
    first_status = json.loads((out / "status.json").read_text())
    assert (
        first_status["min_host_available_gib"] >= 2.0
        and not first_status["active_runs"]
    )
    attempts = {str(p): p.read_bytes() for p in (out / "attempts").glob("*/*.json")}
    second = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert second.returncode == 0, second.stderr
    assert attempts == {
        str(p): p.read_bytes() for p in (out / "attempts").glob("*/*.json")
    }
    status = json.loads((out / "status.json").read_text())
    assert status["state"] == "completed" and status["completed_runs"] == len(records)
    assert not status["active_runs"]
print(
    json.dumps(
        dict(
            passed=True,
            backend=args.backend,
            fresh_worker_cases=len(records),
            variants=args.variants,
            resumed_without_rerun=True,
            sampled_memory=True,
            resident_sampled_cases=sum(r["rss_group_resident_sample_count"] > 0 for r in records),
            initial_only_rss_cases=sum(r["rss_group_resident_sample_count"] == 0 for r in records),
            exact_certificates=True,
        )
    )
)
