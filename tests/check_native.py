#!/usr/bin/env python3
"""Self-contained native audits and exact component-neighborhood probes."""
import sys, os, json, tempfile, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "ArithDiag-LS")]
from check_correctness import toy
from arithdiag.preprocessing import transform, initial, projected_initial, restore
from native_io import render, audit, exact_int
from native_helpers import encode, metadata, local_check


def main():
    native = ROOT / "ArithDiag-LS/native/build/arithdiag-ls"
    audits = traces = 0
    with tempfile.TemporaryDirectory(prefix="arithdiag-test-") as tmp:
        lp = Path(tmp) / "probe.lp"
        from fixture_data import partial_bus_model

        model = partial_bus_model()
        pre = transform(model, False, False)
        group = dict(
            variables=sorted(pre["specs"]),
            components=[c["name"] for c in model["components"]],
            constraints=[c for g in pre["groups"] for c in g["constraints"]],
        )
        specs, encoded, names = encode(pre, group)
        lp.write_text(render(specs, encoded))
        for binary in (native,):
            proc = subprocess.run(
                [str(binary), "--audit", str(lp)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert proc.returncode == 0, proc.stderr
            assert audit(specs, encoded, json.loads(proc.stdout))[
                "mathematically_equivalent_input"
            ]
            audits += 1
        restore(pre, projected_initial(pre, initial(model)))
        for inputs, outputs in [((1, 0, 1), (2, 7)), ((1, 1, 1), (4, 13))]:
            model = toy(inputs, outputs, True)
            pre = transform(model, True, False)
            init = projected_initial(pre, initial(model))
            g = dict(
                variables=sorted(pre["specs"]),
                components=[c["name"] for c in model["components"]],
                constraints=[c for gg in pre["groups"] for c in gg["constraints"]],
            )
            specs, encoded, names = encode(pre, g)
            lp.write_text(render(specs, encoded))
            for binary in (native,):
                proc = subprocess.run(
                    [str(binary), "--audit", str(lp)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert proc.returncode == 0, proc.stderr
                check = audit(specs, encoded, json.loads(proc.stdout))
                assert check["mathematically_equivalent_input"], check
                audits += 1
            reverse = {v: k for k, v in names.items()}
            for seed in (1, 2, 3):
                fd = os.memfd_create("arithdiag-test-witness", 0)
                try:
                    os.write(fd, metadata(pre, g, names, init, True))
                    os.lseek(fd, 0, 0)
                    proc = subprocess.run(
                        [
                            str(native),
                            "--component-probe",
                            str(lp),
                            "/proc/self/fd/" + str(fd),
                            str(seed),
                            "256",
                        ],
                        pass_fds=(fd,),
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                finally:
                    os.close(fd)
                assert proc.returncode == 0, proc.stderr
                found = False
                stats = False
                for line in proc.stdout.splitlines():
                    if line.startswith("ARITHDIAG_TRACE "):
                        row = json.loads(line[len("ARITHDIAG_TRACE ") :])
                        values = {
                            reverse[n]: exact_int(v) for n, v in row["values"].items()
                        }
                        assert local_check(pre, g, values) == exact_int(
                            row["objective"]
                        )
                        restore(pre, values)
                        traces += 1
                        found = True
                    if line.startswith("ARITHDIAG_PROBE "):
                        _, attempts, accepted = line.split()
                        assert int(attempts) > 0
                        stats = True
                assert found and stats
    print(
        json.dumps(
            dict(
                passed=True,
                native_input_audits=audits,
                exact_native_witness_checks=traces,
            )
        )
    )


if __name__ == "__main__":
    main()
