"""Exact integer checks independent of SCIP constraint tolerances."""
import math
from iqcqp_model import circuit_wiring, signal_layout

def decode_integers(raw, mapping, tolerance=1e-6):
    if set(raw) != {v["lp_name"] for v in mapping["variables"]}:
        raise ValueError("Solver variables differ from mapping")
    values = {}
    for v in mapping["variables"]:
        x = raw[v["lp_name"]]
        if not math.isfinite(x) or abs(x - round(x)) > tolerance:
            raise ValueError(f"Nonintegral: {v['lp_name']}={x}")
        values[v["name"]] = int(round(x))
    return values

def validate(model, values, solver_objective=None):
    errors = []
    checks = dict(bounds=0, wiring=0, healthy_components=0, observed_ports=0, polynomial_constraints=0)
    if set(values) != {v["name"] for v in model["variables"]}:
        return dict(valid=False, errors=["Missing or extra variables"], checks=checks)
    signals = {}
    for v in model["variables"]:
        x = values[v["name"]]
        checks["bounds"] += 1
        if type(x) is not int or not v["lb"] <= x <= v["ub"]:
            errors.append(f"bounds/integer: {v['name']}={x}")
        if v["role"] != "abnormal":
            high, low = v["bits"]
            if type(x) is not int or not 0 <= x < (1 << (high - low + 1)):
                errors.append(f"bit width: {v['name']}")
    if any(type(x) is not int for x in values.values()):
        return dict(valid=False, errors=errors, checks=checks)
    # Reconstruct every original signal, including names absent from the shared
    # variable list. Wiring and healthy functions are checked at original ports.
    for signal, segments in signal_layout(model).items():
        signals[signal] = sum(values[segment["name"]] << segment["low"] for segment in segments)

    def ref(r):
        return (signals[r["signal"]] >> r["low"]) & ((1 << (r["high"] - r["low"] + 1)) - 1)
    def expr(e):
        acc = 0
        for p in e["parts"]:
            acc = (acc << p["width"]) + (ref(p["ref"]) if p["ref"] else 0)
        return acc

    for c in circuit_wiring(model):
        checks["wiring"] += 1
        if ref(c["target"]) != expr(c["source"]):
            errors.append(f"wiring: {c['name']}")
    for c in model["constraints"]:
        lhs = sum(t["coef"] * values[t["var"]] for t in c["linear"])
        lhs += sum(t["coef"] * values[t["vars"][0]] * values[t["vars"][1]] for t in c["quadratic"])
        checks["polynomial_constraints"] += 1
        if not {"eq": lhs == c["rhs"], "le": lhs <= c["rhs"], "ge": lhs >= c["rhs"]}[c["sense"]]:
            errors.append(f"polynomial: {c['name']}: {lhs} {c['sense']} {c['rhs']}")
    for c in model["components"]:
        if values["AB_" + c["name"]] == 0:
            checks["healthy_components"] += 1
            a, b = expr(c["a"]), expr(c["b"])
            result = a + b if c["operation"] == "add" else a * b
            if ref(c["output"]) != result:
                errors.append(f"healthy function: {c['name']}")
    for p in model["ports"]:
        checks["observed_ports"] += 1
        if signals[p["name"]] != model["observed_ports"][p["name"]]:
            errors.append(f"observation: {p['name']}")
    objective = sum(values["AB_" + c["name"]] for c in model["components"])
    if solver_objective is not None and (not math.isfinite(solver_objective) or abs(solver_objective - objective) > 1e-6):
        errors.append("Objective differs from exact AB sum")
    return dict(valid=not errors, errors=errors, checks=checks, objective_exact=objective,
                diagnosis=sorted(c["name"] for c in model["components"] if values["AB_" + c["name"]] == 1))
