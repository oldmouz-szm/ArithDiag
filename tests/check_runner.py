"""Whole-process scoring, input identity, path checks and interrupted-run recovery."""

from pathlib import Path
import argparse
import json
import os
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag import resources as monitor
from arithdiag.runner import discover, resolve_input, prepare
from fixture_data import dataset

settings = dict(time_limit_s=1.0)
run = dict(
    run_id="tiny",
    method="ArithDiag-LS",
    configuration="ArithDiag-LS",
    effective_configuration={},
    instance_id="tiny/observations_001",
    seed=1,
)
raw = dict(
    method="ArithDiag-LS",
    configuration={},
    instance_id=run["instance_id"],
    seed=1,
    time_limit_s=1.0,
    trace=[
        dict(total_s=0.2, cardinality=3),
        dict(total_s=0.8, cardinality=2),
        dict(total_s=1.01, cardinality=1),
    ],
    lower_bound_trace=[dict(total_s=0.1, value=1), dict(total_s=1.02, value=2)],
    lower_bound=2,
    lower_bound_total_s=1.02,
    own_optimality_certificate=True,
    proof_time_s=1.02,
    assignment={"private": 42},
    outcome="verified_feasible",
)
row = monitor.normalize(raw, run, settings, 1.1, 20, "budget_exhausted", -9, 10)
assert row["best_cardinality"] == 2 and row["lower_bound"] == 1
assert not row["own_optimality_certificate"] and row["proof_time_s"] is None
assert "assignment" not in row and row["termination"] == "budget_exhausted"
assert row["score_eligible"] and row["has_verified_feasible"]
no_solution = monitor.normalize({}, run, settings, 1.1, 20, "budget_exhausted", -9, 10)
assert (
    no_solution["best_cardinality"] is None and not no_solution["has_verified_feasible"]
)
raw["own_optimality_certificate"] = False
memory = monitor.normalize(raw, run, settings, 0.9, 8193, "memory_limit", -9, 10)
assert (
    memory["has_verified_feasible"]
    and memory["best_cardinality"] == 2
    and memory["termination"] == "memory_limit"
)
raw["lower_bound"] = 4
raw["lower_bound_total_s"] = 0.9
try:
    monitor.normalize(raw, run, settings, 1, 20, None, 0, 10)
except ValueError:
    pass
else:
    raise AssertionError("Invalid bound accepted")
with tempfile.TemporaryDirectory(prefix="arithdiag-runner-") as temporary:
    root = dataset(Path(temporary) / "fixture")
    rows = discover(root)
    assert len(rows) == 2
    try:
        resolve_input(root, "../missing")
    except ValueError:
        pass
    else:
        raise AssertionError("Dataset path escape accepted")
    args = argparse.Namespace(
        cpus=str(min(os.sched_getaffinity(0))),
        concurrency=1,
        time_limit=1.0,
        seeds="1",
        instances="all",
        backends=["ArithDiag-G"],
        dataset_root=[str(root)],
        execute=False,
    )
    out = Path(temporary) / "run"
    out.mkdir()
    manifest = prepare(args, out)
    repeated = prepare(args, out)
    assert manifest == repeated and len(manifest["plan"]) == 2
    args.time_limit = 2.0
    try:
        prepare(args, out)
    except ValueError as exc:
        assert "drift" in str(exc)
    else:
        raise AssertionError("Changed budget resumed")
    header = dict(
        manifest["plan"][0],
        attempt_status="started",
        attempt_id="test-token",
        started_utc=monitor.utc(),
    )
    monitor.save(out / "attempts/tiny/test-token.json", header)
    with (
        mock.patch.object(monitor, "kill_owned") as killed,
        mock.patch.object(monitor, "own_groups", return_value=set()),
    ):
        assert monitor.recover(out, manifest, "test-manifest") == 1
        killed.assert_called_once_with("test-token")
    attempt = monitor.read(out / "attempts/tiny/test-token.json")
    assert (
        attempt["termination"] == "controller_recovered_interrupted_attempt"
        and not attempt["score_eligible"]
    )
print(
    json.dumps(
        dict(
            passed=True,
            deadline_scoring=True,
            memory_preserves_candidate=True,
            dataset_identity=True,
            configuration_drift_rejected=True,
            recovery_preserved=True,
        )
    )
)
