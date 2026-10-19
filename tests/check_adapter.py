from pathlib import Path
import json, os, subprocess, sys, tempfile

R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / "src"), str(R / "ArithDiag-LS")]
from arithdiag.integer_io import render, audit, native_values, exact_int
from native_helpers import encode, metadata, local_check
from native_adapter import consume_final_fragment
from worker import configuration

assert configuration()["native_actions"]
assert "gurobipy" not in sys.modules
seen = []
truncated = []


def consume(raw):
    seen.append(json.loads(raw))


consume_final_fragment(b'{"cardinality":2}', consume, lambda: truncated.append(True))
consume_final_fragment(b'{"cardinality":', consume, lambda: truncated.append(True))
assert seen == [{"cardinality": 2}] and truncated == [True]
native = R / "ArithDiag-LS/native/build/arithdiag-ls"
count = 0
with tempfile.TemporaryDirectory(dir=R / "tests") as scratch:
    for wide in (False, True):
        specs = {
            n: dict(name=n, signal=n, type="integer", role="wire", lb=lo, ub=hi)
            for n, lo, hi in [("a", 2, 2), ("b", 3, 3), ("o", 7, 7)]
        }
        specs["AB_c"] = dict(
            name="AB_c", signal="c", type="binary", role="abnormal", lb=0, ub=1
        )
        M = (1 << 65) - 1 if wide else 16
        rows = [
            dict(
                name="guard_" + str(sign),
                kind="guarded_component",
                component="c",
                sense="le",
                rhs=0,
                terms={"o": sign, "a": -sign, "b": -sign, "AB_c": -M},
                quadratic=[],
            )
            for sign in (1, -1)
        ]
        group = dict(id=0, variables=sorted(specs), components=["c"], constraints=rows)
        pre = dict(
            specs=specs,
            equations=[
                dict(terms={"o": 1, "a": -1, "b": -1}, quadratic=[], rhs=0, ab="AB_c")
            ],
        )
        sp, g, names = encode(pre, group)
        lp = Path(scratch) / "model.lp"
        lp.write_text(render(sp, g))
        report = subprocess.run(
            [str(native), "--audit", str(lp)],
            capture_output=True,
            text=True,
            check=True,
        )
        checked = audit(sp, g, json.loads(report.stdout))
        assert checked["mathematically_equivalent_input"]
        if wide:
            assert checked["safe_redundant_bigm_rounding_count"] == 2
        start = dict(a=2, b=3, o=7, AB_c=1)
        fd = os.memfd_create("ls-test-transient", 0)
        try:
            os.write(fd, metadata(pre, group, names, start, True))
            os.lseek(fd, 0, 0)
            p = subprocess.run(
                [
                    str(native),
                    "--component-probe",
                    str(lp),
                    "/proc/self/fd/" + str(fd),
                    "1",
                    "128",
                ],
                pass_fds=(fd,),
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
        finally:
            os.close(fd)
        traces = [
            json.loads(s[len("ARITHDIAG_TRACE ") :])
            for s in p.stdout.splitlines()
            if s.startswith("ARITHDIAG_TRACE ")
        ]
        assert traces
        for entry in traces:
            values = native_values(sp, g, entry["values"])
            assert local_check(pre, group, values) == 1
            assert exact_int(entry["objective"]) == 1
        count += 1
assert not any(n == "gurobipy" or n.startswith("gurobipy.") for n in sys.modules)
print(
    json.dumps(
        dict(
            passed=True,
            native_transport_and_candidate_checks=count,
            safe_65bit_bigm_transport=True,
            truncated_final_record_regression=True,
            gurobi_imported=False,
        )
    )
)
