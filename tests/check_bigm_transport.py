#!/usr/bin/env python3
"""Exercise actual LP readers at the 64/65-bit Big-M boundary; no witnesses saved."""
import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag.integer_io import (
    audit,
    canonical_monos,
    render,
    native_values,
    transport_constant_name,
)


def fixture(offset=1, quadratic=False):
    upper = 2**64 - 1
    specs = {n: dict(type="integer", lb=0, ub=upper) for n in ("x", "y")}
    specs["AB_c"] = dict(type="binary", lb=0, ub=1)
    maximum = upper**2 if quadratic else 2 * upper
    row = dict(
        name="guard_neg_c",
        kind="guarded_component",
        sense="le",
        rhs=offset,
        terms={"AB_c": -(maximum - offset)},
        quadratic=[],
    )
    if quadratic:
        row["quadratic"] = [dict(a="x", b="y", coef=1)]
    else:
        row["terms"].update(x=1, y=1)
    return specs, dict(components=["c"], variables=list(specs), constraints=[row])


def main():
    audits = assignments = 0
    with tempfile.TemporaryDirectory(prefix="arithdiag-bigm-test-") as tmp:
        lp = Path(tmp) / "model.lp"
        for quadratic, offset in itertools.product(
            (False, True), list(range(1, 17)) + [2**64 + 1, -(2**64 + 1), 2**65 - 3]
        ):
            specs, group = fixture(offset, quadratic)
            before = copy.deepcopy(group)
            lp.write_text(render(specs, group))
            assert group == before, "Export mutated original integer constraints"
            for binary in (ROOT / "ArithDiag-LS/native/build/arithdiag-ls",):
                native = json.loads(
                    subprocess.check_output(
                        [str(binary), "--audit", str(lp)], text=True
                    )
                )
                checked = audit(specs, group, native)
                assert checked["mathematically_equivalent_input"], checked
                parsed = canonical_monos(native["constraints"][0]["monomials"])
                original = group["constraints"][0]
                one = transport_constant_name(specs, group)
                for x, y, ab in itertools.product(
                    (
                        0,
                        1,
                        abs(offset) % (2**64),
                        specs["x"]["ub"] - 1,
                        specs["x"]["ub"],
                    ),
                    (0, 1, specs["y"]["ub"]),
                    (0, 1),
                ):
                    values = dict(x=x, y=y, AB_c=ab)
                    left = sum(a * values[n] for n, a in original["terms"].items())
                    left += sum(
                        t["coef"] * values[t["a"]] * values[t["b"]]
                        for t in original["quadratic"]
                    )
                    if one:
                        values[one] = 1
                    assert native_values(specs, group, values) == dict(
                        x=x, y=y, AB_c=ab
                    )
                    right = sum(
                        int(a)
                        * (
                            values[key[0]]
                            if len(key) == 1
                            else values[key[0]] * values[key[1]]
                        )
                        for key, a in parsed.items()
                    )
                    assert (left <= offset) == (
                        right <= int(native["constraints"][0]["rhs"])
                    )
                    assignments += 1
                audits += 1
                if one:
                    broken = copy.deepcopy(native)
                    next(v for v in broken["variables"] if v["name"] == one)["ub"] = "2"
                    assert not audit(specs, group, broken)[
                        "mathematically_equivalent_input"
                    ]
                    broken = copy.deepcopy(native)
                    broken["constraints"][0]["rhs"] = str(
                        int(broken["constraints"][0]["rhs"]) + 2
                    )
                    assert not audit(specs, group, broken)[
                        "mathematically_equivalent_input"
                    ]
                    try:
                        native_values(specs, group, dict(x=0, y=0, AB_c=1, **{one: 0}))
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Invalid fixed constant accepted")
        # A restrictive row must never be turned into a redundant guard, even
        # when its name/type resembles a component guard.
        specs, group = fixture()
        group["constraints"][0]["terms"]["AB_c"] = -(2**64 + 1)
        lp.write_text(render(specs, group))
        assert str(2**64 + 1) in lp.read_text()
        native = json.loads(
            subprocess.check_output(
                [
                    str(ROOT / "ArithDiag-LS/native/build/arithdiag-ls"),
                    "--audit",
                    str(lp),
                ],
                text=True,
            )
        )
        assert not audit(specs, group, native)["mathematically_equivalent_input"]
        # Non-guard rows and non-AB numeric mismatches stay subject to the audit.
        for field in ("kind", "sense"):
            specs, group = fixture()
            group["constraints"][0][field] = "wiring" if field == "kind" else "eq"
            assert str(2**65 - 3) in render(specs, group)
        # Complete guarded addition with a genuinely 65-bit observation: run
        # the component action and validate each transient native witness.
        observed = 2**64 + 1
        specs, group = fixture(observed)
        group["constraints"].append(
            dict(
                name="guard_pos_c",
                kind="guarded_component",
                sense="le",
                rhs=-observed,
                terms={"x": -1, "y": -1, "AB_c": -observed},
                quadratic=[],
            )
        )
        lp.write_text(render(specs, group))
        one = transport_constant_name(specs, group)
        fd = os.memfd_create("arithdiag-bigm-probe", 0)
        try:
            os.write(
                fd,
                (
                    f"MODE 1\nI x {2**64-1}\nI y 0\nI AB_c 1\nI {one} 1\n"
                    f"E AB_c {observed} 2 1 1 x 1 1 y\n"
                ).encode(),
            )
            os.lseek(fd, 0, 0)
            proc = subprocess.run(
                [
                    str(ROOT / "ArithDiag-LS/native/build/arithdiag-ls"),
                    "--component-probe",
                    str(lp),
                    "/proc/self/fd/" + str(fd),
                    "1",
                    "256",
                ],
                pass_fds=(fd,),
                capture_output=True,
                text=True,
                timeout=15,
            )
        finally:
            os.close(fd)
        assert proc.returncode == 0
        seen = []
        for line in proc.stdout.splitlines():
            if line.startswith("ARITHDIAG_TRACE "):
                event = json.loads(line[len("ARITHDIAG_TRACE ") :])
                values = native_values(specs, group, event["values"])
                for n, v in values.items():
                    assert specs[n]["lb"] <= v <= specs[n]["ub"]
                assert values["AB_c"] or values["x"] + values["y"] == observed
                seen.append(int(event["objective"]))
        assert (
            seen and min(seen) == 0
        ), "65-bit observation must allow a healthy native witness"
    print(
        json.dumps(
            dict(
                passed=True,
                native_input_audits=audits,
                exact_boundary_assignments=assignments,
                fail_closed_checks=3,
                native_65bit_observation_witnesses=len(seen),
            )
        )
    )


if __name__ == "__main__":
    main()
