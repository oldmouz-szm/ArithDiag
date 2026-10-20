"""Real LS handoff on an independently enumerable fan-out diagnosis fixture."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

from fixture_data import dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag.model import build_diagnostic_model
from arithdiag.preprocessing import initial, transform, projected_initial, restore
variants = ("full", "no-internal-search", "no-proof-enhancement", "backend-only")
# A computes s=1+2. B and C copy s[7:0] by adding zero; both observe 4.
# Enumerate s independently of the model builder and candidate validator.
truth = min(int(s != 3) + 2 * int(s % 256 != 4) for s in range(512))
assert truth == 1
with tempfile.TemporaryDirectory(prefix="arithdiag-handoff-") as directory:
    base = Path(directory)
    inputs = dataset(base / "fixture")
    case = inputs / "cases/fanout"
    case.mkdir()
    (case / "netlist.v").write_text(
        "module fanout(input [7:0] a, input [7:0] b, input [7:0] zero, "
        "output [8:0] y, output [8:0] z);\n"
        "wire [8:0] s;\n"
        "u_rca8 A0 (.a(a), .b(b), .u_rca8_out(s));\n"
        "u_rca8 A1 (.a(s[7:0]), .b(zero), .u_rca8_out(y));\n"
        "u_rca8 A2 (.a(s[7:0]), .b(zero), .u_rca8_out(z));\nendmodule\n"
    )
    (case / "observations_001.jsonl").write_text(
        '# {"circuit":"fanout"}\n'
        '{"inputs":{"a":"0x1","b":"0x2","zero":"0x0"},'
        '"outputs":{"y":"0x4","z":"0x4"}}\n'
    )
    model = build_diagnostic_model(case / "netlist.v", case / "observations_001.jsonl", inputs / "library")
    pre = transform(model, True, True, True)
    _, k = restore(pre, projected_initial(pre, initial(model)))
    assert k == 2
    command = [sys.executable, "-B", str(ROOT / "run.py"),
               "--dataset-root", str(inputs), "--instances", "fanout/observations_001",
               "--run-name", "handoff", "--output-root", str(base / "runs"),
               "--time-limit", "3", "--variants", *variants,
               "--cpus", str(min(os.sched_getaffinity(0))), "--execute"]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=45)
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr,
        json.loads((base / "runs/handoff/status.json").read_text()))
    rows = {r["variant"]: r for p in (base / "runs/handoff/records").glob("*.json")
            for r in [json.loads(p.read_text())]}
    assert set(rows) == set(variants)
    for variant, r in rows.items():
        assert r["method"] == "ArithDiag-LS" and r["has_verified_feasible"]
        assert not r["invalid_candidate_count"] and not r["gurobi_imported"]
        assert r["trace"][0]["cardinality"] == 2
        assert truth <= r["best_cardinality"] <= 2
        assert r["lower_bound"] <= truth
        if r["own_optimality_certificate"]:
            assert r["best_cardinality"] == truth
        if variant in ("no-internal-search", "backend-only"):
            assert r["native_invocations"] > 0
            assert r["native_audit_invocations"] == 1 and r["strict_equivalent_input"]
            assert r["bigm_encoding_invocations"] == 1
            assert r.get("coordination_candidates", 0) == 0
        else:
            assert r["coordination_candidates"] > 0
        if variant == "backend-only":
            assert r["coordination_calls"] == 0 and r["proof_strengthening_s"] == 0
            assert all(round_["proof_pause_s"] == 0 for round_ in r["rounds"])
        if variant in ("no-proof-enhancement", "backend-only"):
            assert r["initial_refinement_checks"] == 0
            assert r.get("proof_master_calls", 0) == 0
            assert r.get("proof_refutation_checks", 0) == 0
print(json.dumps(dict(passed=True, fresh_worker_cases=4,
                      independent_optimum=truth, real_ls_handoff=True,
                      disabled_mechanisms_not_called=True, gurobi_used=False)))
