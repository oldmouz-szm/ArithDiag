#!/usr/bin/env python3
"""Run independent checks in fresh processes; Gurobi checks are explicitly opt-in."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--native", action="store_true", help="also check the compiled LS backend"
)
parser.add_argument(
    "--gurobi",
    action="store_true",
    help="also check Gurobi encoding; requires a license",
)
args = parser.parse_args()
checks = [
    (name, [])
    for name in [
        "check_release.py",
        "check_correctness.py",
        "check_proof_policy.py",
        "check_hitting_bound.py",
        "check_hitting_candidate.py",
        "check_runner.py",
    ]
]
if args.native:
    checks += [
        (name, [])
        for name in ["check_bigm_transport.py", "check_native.py", "check_adapter.py"]
    ]
    checks += [("check_cli.py", ["--backend", "ArithDiag-LS"])]
if args.gurobi:
    checks += [
        ("check_gurobi_encoding.py", []),
        ("check_cli.py", ["--backend", "ArithDiag-G"]),
    ]
for check, flags in checks:
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "tests" / check), *flags],
        cwd=ROOT,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0"),
        check=True,
    )
print("All selected ArithDiag checks passed.")
