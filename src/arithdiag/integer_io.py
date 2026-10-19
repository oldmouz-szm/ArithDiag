"""Native-input equivalence audits and exact integer coefficient transport."""

import os
from pathlib import Path
from decimal import Decimal, getcontext

getcontext().prec = 4096
ROOT = Path(__file__).resolve().parents[2]
from arithdiag import model as builder
from arithdiag.validation import validate


def load_builder():
    return builder


IQ = (
    Path(os.environ.get("ARITHDIAG_DATASET_ROOT", str(ROOT / "data/benchmark")))
    .expanduser()
    .resolve()
)


def expression(terms):
    parts = []
    for name, coef in terms:
        if not coef:
            continue
        sign = "+" if coef > 0 else "-"
        parts.append(f"{sign} {abs(coef)} {name}")
    return " ".join(parts) or "0"


def native_guard_terms(specs, c):
    """Transport a redundant Big-M using an outward, 64-bit-significand integer.

    The original model is never modified. For AB=0 the row is unchanged; for
    AB=1 both rows are redundant over the declared box. All bounds, RHS values,
    and non-guard coefficients retain their exact text and fail-closed audit.
    The native long-double build uses 64 significand bits; the subsequent audit
    still checks the actual parser, including builds on different platforms.
    """
    terms = c["terms"]
    if c.get("kind") != "guarded_component" or c["sense"] != "le":
        return terms
    guards = [n for n in terms if n.startswith("AB_")]
    if len(guards) != 1:
        return terms
    ab = guards[0]
    coef = terms[ab]
    if specs[ab]["type"] != "binary" or coef >= 0:
        return terms
    magnitude = -coef
    shift = max(0, magnitude.bit_length() - 64)
    quantum = 1 << shift
    rounded = ((magnitude + quantum - 1) // quantum) * quantum
    if rounded == magnitude:
        return terms
    # Exact conservative upper bound of the original row at AB=1. Refuse to
    # relax a row unless its original guard already releases the whole domain.
    high = coef
    for n, a in terms.items():
        if n != ab:
            high += a * specs[n]["ub" if a >= 0 else "lb"]
    for t in c.get("quadratic", []):
        if ab in (t["a"], t["b"]):
            return terms
        a, b = specs[t["a"]], specs[t["b"]]
        if a["lb"] < 0 or b["lb"] < 0:
            return terms
        high += t["coef"] * (a["ub"] * b["ub"] if t["coef"] >= 0 else a["lb"] * b["lb"])
    if high > c["rhs"]:
        return terms
    return dict(terms, **{ab: -rounded})


def native_integer_exact(value):
    shift = max(0, abs(value).bit_length() - 64)
    return value % (1 << shift) == 0


def transport_constant_name(specs, group):
    if all(native_integer_exact(c["rhs"]) for c in group["constraints"]):
        return None
    name = "arithdiag_transport_one"
    while name in specs:
        name += "_"
    return name


def native_values(specs, group, raw):
    """Check and remove the uniquely fixed transport constant, never a signal."""
    values = {n: exact_int(x) for n, x in raw.items()}
    one = transport_constant_name(specs, group)
    if set(values) != set(specs) | ({one} if one else set()):
        raise ValueError("Missing/extra candidate variables")
    if one:
        if values.pop(one) != 1:
            raise ValueError("Invalid transport constant")
    return values


def render(specs, group):
    one = transport_constant_name(specs, group)
    out = [
        "Minimize",
        " obj: " + expression(("AB_" + c, 1) for c in group["components"]),
        "Subject To",
    ]
    for c in group["constraints"]:
        terms = native_guard_terms(specs, c)
        rhs = c["rhs"]
        if not native_integer_exact(rhs):
            quantum = 1 << max(0, abs(rhs).bit_length() - 64)
            high = (rhs // quantum) * quantum
            low = rhs - high
            if not native_integer_exact(low):
                raise ValueError("RHS exceeds exact native constant transport range")
            terms = dict(terms, **{one: -low})
            rhs = high
        lin = expression(terms.items())
        quad = c.get("quadratic", [])
        if quad:
            q = expression((t["a"] + " * " + t["b"], t["coef"]) for t in quad)
            lin = (lin if lin != "0" else "") + " + [ " + q + " ]"
            lin = lin.strip()
            if lin.startswith("+ ["):
                lin = lin[2:]
        out.append(
            " "
            + c["name"]
            + ": "
            + lin
            + " "
            + {"eq": "=", "le": "<=", "ge": ">="}[c["sense"]]
            + " "
            + str(rhs)
        )
    out += ["Bounds"] + [
        f" {specs[n]['lb']} <= {n} <= {specs[n]['ub']}" for n in group["variables"]
    ]
    if one:
        out.append(f" 1 <= {one} <= 1")
    out += ["Binaries"] + [
        " " + n for n in group["variables"] if specs[n]["type"] == "binary"
    ]
    out += ["Generals"] + [
        " " + n for n in group["variables"] if specs[n]["type"] != "binary"
    ]
    if one:
        out.append(" " + one)
    out += ["End", ""]
    return "\n".join(out)


def exact_int(x):
    d = Decimal(str(x))
    if not d.is_finite() or d != d.to_integral_value():
        raise ValueError("Nonintegral numeric value")
    return int(d)


def validation_failure(check):
    """A log-safe error category/count; validator details remain transient."""
    return "original_model_validation_failed; violation_count=" + str(
        len(check.get("errors", ()))
    )


def canonical_monos(items):
    result = {}
    for item in items:
        key = tuple(sorted(item["vars"]))
        result[key] = result.get(key, 0) + Decimal(str(item["coef"]))
    return {k: v for k, v in result.items() if v}


def audit(specs, group, native):
    structural = []
    numeric = []
    safe = []
    one = transport_constant_name(specs, group)
    wanted = {n: (v["type"], v["lb"], v["ub"]) for n, v in specs.items()}
    got = {
        v["name"]: (v["type"], Decimal(v["lb"]), Decimal(v["ub"]))
        for v in native["variables"]
    }
    if one and got.pop(one, None) != ("integer", Decimal(1), Decimal(1)):
        structural.append("Transport constant is not a fixed integer one")
    if set(wanted) != set(got):
        structural.append("Variable names differ")
    for n in wanted.keys() & got.keys():
        if wanted[n][0] != got[n][0]:
            structural.append("Variable type differs: " + n)
        for index in (1, 2):
            if wanted[n][index] != got[n][index]:
                numeric.append(
                    dict(
                        field="bound",
                        variable=n,
                        expected=str(wanted[n][index]),
                        parsed=str(got[n][index]),
                    )
                )
    expected = {c["name"]: c for c in group["constraints"]}
    actual = {c["name"]: c for c in native["constraints"]}
    if expected.keys() != actual.keys():
        structural.append("Constraint names/count differ")
    for name in expected.keys() & actual.keys():
        a, b = expected[name], actual[name]
        if one:
            # Independently eliminate the actual parsed fixed variable, rather than
            # accepting the exporter's claimed high/low split or rounded observation.
            rhs = Decimal(b["rhs"])
            monos = []
            for term in b["monomials"]:
                if term["vars"] == [one]:
                    rhs -= Decimal(str(term["coef"]))
                else:
                    if one in term["vars"]:
                        structural.append("Nonlinear transport constant")
                    monos.append(term)
            b = dict(b, rhs=str(rhs), monomials=monos)
        if a["sense"] != b["sense"]:
            structural.append("Constraint sense differs: " + name)
        if Decimal(b["rhs"]) != a["rhs"]:
            numeric.append(
                dict(
                    field="rhs",
                    constraint=name,
                    expected=str(a["rhs"]),
                    parsed=b["rhs"],
                )
            )
        ms = [dict(vars=[n], coef=x) for n, x in a["terms"].items()] + [
            dict(vars=[t["a"], t["b"]], coef=t["coef"]) for t in a.get("quadratic", [])
        ]
        x, y = canonical_monos(ms), canonical_monos(b["monomials"])
        if x.keys() != y.keys():
            structural.append("Monomial variables differ: " + name)
        elif x != y:
            numeric.append(dict(field="coefficients", constraint=name))
            changed = [key for key in x if x[key] != y[key]]
            if (
                len(changed) == 1
                and len(changed[0]) == 1
                and changed[0][0].startswith("AB_")
                and a["sense"] == "le"
            ):
                ab = changed[0][0]
                if specs[ab]["type"] == "binary":
                    high = y[changed[0]]
                    for key, coef in y.items():
                        if key == changed[0]:
                            continue
                        if len(key) == 1:
                            lo, hi = specs[key[0]]["lb"], specs[key[0]]["ub"]
                        else:
                            v1, v2 = specs[key[0]], specs[key[1]]
                            assert v1["lb"] >= 0 and v2["lb"] >= 0
                            lo, hi = v1["lb"] * v2["lb"], v1["ub"] * v2["ub"]
                        high += coef * (hi if coef >= 0 else lo)
                    if (
                        high <= a["rhs"]
                        and high - y[changed[0]] + x[changed[0]] <= a["rhs"]
                    ):
                        safe.append(name)
    obj = canonical_monos(native["objective"])
    if obj != {("AB_" + c,): Decimal(1) for c in group["components"]}:
        structural.append("Objective differs")
    return dict(
        structurally_correct=not structural,
        parsed_numbers_exact=not numeric,
        mathematically_equivalent_input=not structural and len(numeric) == len(safe),
        safe_redundant_bigm_rounding_count=len(safe),
        structural_errors=structural[:20],
        structural_error_count=len(structural),
        numeric_mismatches=numeric[:20],
        numeric_mismatch_count=len(numeric),
        native_model_variables=len(native["variables"]),
        transport_fixed_variables=int(one is not None),
        native_float_mantissa_bits=native["float_mantissa_bits"],
    )
