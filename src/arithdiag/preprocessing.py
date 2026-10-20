"""Exact, component-level transformations and certified conflicts."""

from collections import defaultdict
import time
from arithdiag.model_io import ROOT, IQ, load_builder, validate, validation_failure
from arithdiag.model import circuit_wiring, signal_layout
from arithdiag.dominance import top_level_search_components


def load(dataset, case, obs):
    base = IQ / ("nonlinear" if dataset == "nonlinear" else "")
    return load_builder().build_diagnostic_model(
        base / "cases" / case / "netlist.v",
        base / "cases" / case / (obs + ".jsonl"),
        IQ / "library",
    )


def substitute(c, fixed, rename):
    constant = 0
    linear = defaultdict(int)
    quad = defaultdict(int)
    for t in c["linear"]:
        n = rename.get(t["var"], t["var"])
        a = t["coef"]
        if n in fixed:
            constant += a * fixed[n]
        else:
            linear[n] += a
    for t in c["quadratic"]:
        a, b = (rename.get(n, n) for n in t["vars"])
        k = t["coef"]
        if a in fixed and b in fixed:
            constant += k * fixed[a] * fixed[b]
        elif a in fixed:
            linear[b] += k * fixed[a]
        elif b in fixed:
            linear[a] += k * fixed[b]
        else:
            quad[tuple(sorted((a, b)))] += k
    return dict(
        name=c["name"],
        kind=c["kind"],
        component=c.get("component"),
        terms={n: a for n, a in linear.items() if a},
        quadratic=[dict(a=a, b=b, coef=k) for (a, b), k in sorted(quad.items()) if k],
        sense=c["sense"],
        ab=c.get("ab"),
        rhs=c["rhs"] - constant,
    )



def normal_equations(model):
    """Return hard wiring and directly stored healthy-conditional equations."""
    eq = []
    for c in model["constraints"]:
        if c["kind"] == "wiring":
            eq.append(dict(c, ab=None))
        elif c["kind"] == "conditional_component":
            eq.append(dict(c, ab=c["abnormal"]))
    return eq

def transform(model, structural=False, dominance=False, decomposition=True):
    variables = {v["name"]: dict(v) for v in model["variables"]}
    # Connection aliases are already shared by the common model builder.
    rename = {n: n for n in variables}
    reps = variables
    fixed = {n: v["lb"] for n, v in reps.items() if v["lb"] == v["ub"]}
    dominated = {}
    if dominance:
        group = {"components": [c["name"] for c in model["components"]]}
        dominated = top_level_search_components(model, group)
        fixed.update({"AB_" + c: 0 for c in dominated})
    propagation = 0
    if structural:
        for iteration in range(len(reps) + 1):
            changed = False
            for c in normal_equations(model):
                if c["ab"] and fixed.get(rename[c["ab"]]) != 0:
                    continue
                r = substitute(c, fixed, rename)
                if not r["quadratic"] and len(r["terms"]) == 1:
                    n, k = next(iter(r["terms"].items()))
                    if r["rhs"] % k:
                        raise ValueError("Nonintegral forced value")
                    value = r["rhs"] // k
                    if not reps[n]["lb"] <= value <= reps[n]["ub"]:
                        raise ValueError("Forced value outside domain")
                    fixed[n] = value
                    changed = True
                    propagation += 1
                elif not r["quadratic"] and not r["terms"] and r["rhs"]:
                    raise ValueError("Inconsistent healthy reduction")
            if not changed:
                break
    specs = {n: v for n, v in reps.items() if n not in fixed}
    residual = []
    for c in model["constraints"]:
        ab = c.get("abnormal") if c["kind"] == "conditional_component" else None
        if ab is not None and fixed.get(ab) == 1:
            continue
        r = substitute(c, fixed, rename)
        r["ab"] = ab if ab is not None and ab not in fixed else None
        if r["ab"] is not None:
            # A false constant function forces its guard faulty; it is not an
            # unconditional contradiction. A true constant equation is redundant.
            if not r["terms"] and not r["quadratic"] and r["rhs"] == 0:
                continue
            residual.append(r)
        elif not r["terms"] and not r["quadratic"]:
            if not {"eq": 0 == r["rhs"], "le": 0 <= r["rhs"], "ge": 0 >= r["rhs"]}[
                r["sense"]
            ]:
                raise ValueError("Constant contradiction")
        else:
            residual.append(r)
    if decomposition:
        # Include shared AB variables in connectivity.
        parent = {n: n for n in specs}

        def find(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        for c in residual:
            ns = sorted(
                set(c["terms"]) | {n for t in c["quadratic"] for n in (t["a"], t["b"])}
                | ({c["ab"]} if c.get("ab") else set())
            )
            for n in ns[1:]:
                parent[find(n)] = find(ns[0])
        groups = defaultdict(lambda: dict(variables=[], constraints=[], components=[]))
        for n in specs:
            g = groups[find(n)]
            g["variables"].append(n)
            if specs[n]["role"] == "abnormal":
                g["components"].append(specs[n]["signal"])
        for c in residual:
            ns = (set(c["terms"]) | {n for t in c["quadratic"] for n in (t["a"], t["b"])}
                  | ({c["ab"]} if c.get("ab") else set()))
            roots = {find(n) for n in ns}
            assert len(roots) == 1
            groups[roots.pop()]["constraints"].append(c)
        groups = sorted(groups.values(), key=lambda g: min(g["variables"]))
    else:
        groups = (
            [
                dict(
                    variables=sorted(specs),
                    constraints=residual,
                    components=sorted(
                        specs[n]["signal"]
                        for n in specs
                        if specs[n]["role"] == "abnormal"
                    ),
                )
            ]
            if specs
            else []
        )
    for i, g in enumerate(groups):
        g.update(
            id=i, variables=sorted(g["variables"]), components=sorted(g["components"])
        )
    equations = []
    for c in normal_equations(model):
        if c["ab"] and fixed.get(rename[c["ab"]]) == 1:
            continue
        r = substitute(c, fixed, rename)
        r["ab"] = rename[c["ab"]] if c["ab"] and rename[c["ab"]] not in fixed else None
        equations.append(r)
    return dict(
        model=model,
        specs=specs,
        fixed=fixed,
        rename=rename,
        groups=groups,
        equations=equations,
        stats=dict(
            original_variables=len(variables),
            original_constraints=len(model["constraints"]),
            remaining_variables=len(specs),
            remaining_constraints=len(residual),
            independent_groups=len(groups),
            dominated_components=len(dominated),
            decomposition_enabled=decomposition,
            aliases_removed=model.get("normalization", {}).get("aliases_merged", 0),
            propagated_variables=propagation,
        ),
    )


def restore(pre, values):
    complete = {
        n: pre["fixed"][r] if r in pre["fixed"] else values[r]
        for n, r in pre["rename"].items()
    }
    check = validate(pre["model"], complete)
    if not check["valid"]:
        raise ValueError(validation_failure(check))
    return complete, check["objective_exact"]


def initial(model):
    """Construct a witness using inputs and observed outputs, never fault metadata."""
    widths = {
        signal: max(segment["high"] for segment in segments) + 1
        for signal, segments in signal_layout(model).items()
    }
    signals = {
        p["name"]: model["observed_ports"][p["name"]]
        for p in model["ports"]
        if p["direction"] == "input"
    }
    wires = circuit_wiring(model)
    known = {n: (1 << widths[n]) - 1 for n in signals}

    def ref(r):
        mask = ((1 << (r["high"] - r["low"] + 1)) - 1) << r["low"]
        if known.get(r["signal"], 0) & mask != mask:
            raise KeyError("Unready source bits")
        return (signals[r["signal"]] >> r["low"]) & (
            (1 << (r["high"] - r["low"] + 1)) - 1
        )

    def expr(e):
        z = 0
        for p in e["parts"]:
            z = (z << p["width"]) + (ref(p["ref"]) if p["ref"] else 0)
        return z

    def put(r, value):
        mask = ((1 << (r["high"] - r["low"] + 1)) - 1) << r["low"]
        signals[r["signal"]] = (signals.get(r["signal"], 0) & ~mask) | (
            (value << r["low"]) & mask
        )
        known[r["signal"]] = known.get(r["signal"], 0) | mask

    pending = [("w", c) for c in wires] + [("c", c) for c in model["components"]]
    ordered = []
    while pending:
        rest = []
        progress = False
        for typ, c in pending:
            try:
                if typ == "w":
                    value = expr(c["source"])
                    out = c["target"]
                else:
                    a, b = expr(c["a"]), expr(c["b"])
                    value = a + b if c["operation"] == "add" else a * b
                    out = c["output"]
            except KeyError:
                rest.append((typ, c))
                continue
            put(out, value)
            ordered.append((typ, c))
            progress = True
        if not progress:
            raise ValueError("Cannot evaluate supported circuit DAG")
        pending = rest
    forced = defaultdict(int)
    input_names = {p["name"] for p in model["ports"] if p["direction"] == "input"}

    def force(r, value, active=None):
        active = set() if active is None else set(active)
        key = (r["signal"], r["low"], r["high"])
        if key in active:
            raise ValueError("Reverse wire cycle")
        active.add(key)
        mask = ((1 << (r["high"] - r["low"] + 1)) - 1) << r["low"]
        if r["signal"] in input_names and ref(r) != value:
            raise ValueError("Observation contradicts hard input")
        existing = signals.get(r["signal"], 0)
        if (existing ^ (value << r["low"])) & forced[r["signal"]] & mask:
            raise ValueError("Conflicting observed aliases")
        put(r, value)
        forced[r["signal"]] |= mask
        for w in wires:
            t = w["target"]
            if t["signal"] != r["signal"]:
                continue
            low = max(r["low"], t["low"])
            high = min(r["high"], t["high"])
            if low > high:
                continue
            offset = 0
            for p in reversed(w["source"]["parts"]):
                pl = offset + t["low"]
                ph = pl + p["width"] - 1
                a, b = max(low, pl), min(high, ph)
                if a <= b:
                    z = (signals[r["signal"]] >> a) & ((1 << (b - a + 1)) - 1)
                    if p["ref"]:
                        rr = p["ref"]
                        force(
                            dict(
                                signal=rr["signal"],
                                low=rr["low"] + a - pl,
                                high=rr["low"] + b - pl,
                            ),
                            z,
                            active,
                        )
                    elif z:
                        raise ValueError("Observed zero padding contradicts")
                offset += p["width"]

    for p in model["ports"]:
        if p["direction"] == "output":
            force(
                dict(signal=p["name"], low=0, high=widths[p["name"]] - 1),
                model["observed_ports"][p["name"]],
            )
    abs = {}
    for typ, c in ordered:
        out = c["target"] if typ == "w" else c["output"]
        if typ == "w":
            value = expr(c["source"])
        else:
            a, b = expr(c["a"]), expr(c["b"])
            value = a + b if c["operation"] == "add" else a * b
        mask = ((1 << (out["high"] - out["low"] + 1)) - 1) << out["low"]
        old = signals[out["signal"]]
        merged = (old & forced[out["signal"]] & mask) | (
            (value << out["low"]) & ~forced[out["signal"]] & mask
        )
        signals[out["signal"]] = (old & ~mask) | merged
        if typ == "c":
            abs["AB_" + c["name"]] = int(ref(out) != value)
    values = dict(abs)
    for v in model["variables"]:
        if v["role"] != "abnormal":
            hi, lo = v["bits"]
            values[v["name"]] = (signals[v["signal"]] >> lo) & (
                (1 << (hi - lo + 1)) - 1
            )
    check = validate(model, values)
    if not check["valid"]:
        return None
    return values


def projected_initial(pre, full):
    if full is None:
        return None
    vs = {r: full[n] for n, r in pre["rename"].items() if r in pre["specs"]}
    try:
        restore(pre, vs)
    except ValueError:
        return None
    return vs


def cone_conflicts(model):
    """Certified cones per observed word segment, with whole-component ABs."""
    nominal = initial_nominal(model)
    by_signal = signal_layout(model)

    def touched(r):
        return [
            "v:" + v["name"]
            for v in by_signal[r["signal"]]
            if max(v["low"], r["low"]) <= min(v["high"], r["high"])
        ]

    incoming = defaultdict(set)
    for c in model["components"]:
        node = "c:" + c["name"]
        for dst in touched(c["output"]):
            incoming[dst].add(node)
        for e in (c["a"], c["b"]):
            for part in e["parts"]:
                if part["ref"]:
                    incoming[node].update(touched(part["ref"]))
    for c in circuit_wiring(model):
        src = {n for p in c["source"]["parts"] if p["ref"] for n in touched(p["ref"])}
        for dst in touched(c["target"]):
            incoming[dst].update(src)
    conflicts = []
    outputs = [
        (p["name"], v)
        for p in model["ports"]
        if p["direction"] == "output"
        for v in by_signal[p["name"]]
    ]
    for signal, v in outputs:
        hi, lo = v["high"], v["low"]
        mask = (1 << (hi - lo + 1)) - 1
        if (nominal[signal] >> lo) & mask == (
            model["observed_ports"][signal] >> lo
        ) & mask:
            continue
        seen = set()
        stack = ["v:" + v["name"]]
        cs = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            if n.startswith("c:"):
                cs.add(n[2:])
            stack.extend(incoming[n])
        if not cs:
            raise ValueError("Inconsistent output outside component model")
        conflicts.append(frozenset(cs))
    return sorted(set(conflicts), key=lambda c: (len(c), sorted(c)))


def initial_nominal(model):
    # Exact healthy evaluation; no observations on internal signals.
    signals = {
        p["name"]: model["observed_ports"][p["name"]]
        for p in model["ports"]
        if p["direction"] == "input"
    }
    widths = {
        signal: max(segment["high"] for segment in segments) + 1
        for signal, segments in signal_layout(model).items()
    }
    known = {n: (1 << widths[n]) - 1 for n in signals}

    def expr(e):
        z = 0
        for p in e["parts"]:
            r = p["ref"]
            if r is not None:
                mask = ((1 << (r["high"] - r["low"] + 1)) - 1) << r["low"]
                if known.get(r["signal"], 0) & mask != mask:
                    raise KeyError("Unready source bits")
            v = (
                0
                if r is None
                else (signals[r["signal"]] >> r["low"])
                & ((1 << (r["high"] - r["low"] + 1)) - 1)
            )
            z = (z << p["width"]) + v
        return z

    pending = [("w", c) for c in circuit_wiring(model)] + [
        ("c", c) for c in model["components"]
    ]
    while pending:
        rest = []
        for typ, c in pending:
            try:
                if typ == "w":
                    out = c["target"]
                    value = expr(c["source"])
                else:
                    out = c["output"]
                    a, b = expr(c["a"]), expr(c["b"])
                    value = a + b if c["operation"] == "add" else a * b
            except KeyError:
                rest.append((typ, c))
                continue
            lo, hi = out["low"], out["high"]
            mask = ((1 << (hi - lo + 1)) - 1) << lo
            signals[out["signal"]] = (signals.get(out["signal"], 0) & ~mask) | (
                (value << lo) & mask
            )
            known[out["signal"]] = known.get(out["signal"], 0) | mask
        if len(rest) == len(pending):
            raise ValueError("Cyclic/unsupported DAG")
        pending = rest
    return signals


def certified_conflict(model, healthy, max_rounds=12):
    """Sound interval/finite-product contradiction checker; otherwise UNKNOWN."""
    specs = {v["name"]: v for v in model["variables"]}
    bounds = {
        n: [v["lb"], v["ub"]] for n, v in specs.items() if v["role"] != "abnormal"
    }
    equations = [
        c for c in normal_equations(model) if c["ab"] is None or c["ab"][3:] in healthy
    ]
    for _ in range(max_rounds):
        changed = False
        for c in equations:
            ts = c["linear"]
            qs = c["quadratic"]
            rhs = c["rhs"]

            def rest(exclude=None):
                lo = hi = 0
                for t in ts:
                    if t["var"] == exclude:
                        continue
                    a, b = bounds[t["var"]]
                    k = t["coef"]
                    lo += min(k * a, k * b)
                    hi += max(k * a, k * b)
                for t in qs:
                    a, b = t["vars"]
                    al, ah = bounds[a]
                    bl, bh = bounds[b]
                    k = t["coef"]
                    vals = [k * x * y for x in (al, ah) for y in (bl, bh)]
                    lo += min(vals)
                    hi += max(vals)
                return lo, hi

            lo, hi = rest()
            if not lo <= rhs <= hi:
                return True
            quadratic_vars = {n for t in qs for n in t["vars"]}
            for t in ts:
                n, k = t["var"], t["coef"]
                if n in quadratic_vars or not k:
                    continue
                l, h = rest(n)
                a, b = rhs - h, rhs - l
                if k < 0:
                    a, b, k = -b, -a, -k
                nl, nh = -((-a) // k), b // k
                old = bounds[n]
                new = [max(old[0], nl), min(old[1], nh)]
                if new[0] > new[1]:
                    return True
                if new != old:
                    bounds[n] = new
                    changed = True
            if len(qs) == 1 and all(
                bounds[t["var"]][0] == bounds[t["var"]][1] for t in ts
            ):
                q = qs[0]
                a, b = q["vars"]
                k = q["coef"]
                if a == b:
                    continue
                product = rhs - sum(t["coef"] * bounds[t["var"]][0] for t in ts)
                if product % k:
                    return True
                product //= k
                al, ah = bounds[a]
                bl, bh = bounds[b]
                if ah - al <= 2048:
                    if not any(
                        (x == 0 and product == 0)
                        or (x and product % x == 0 and bl <= product // x <= bh)
                        for x in range(al, ah + 1)
                    ):
                        return True
        if not changed:
            break
    return False


def learn_conflicts(model, deadline, max_checks=64, initial_conflicts=None):
    conflicts = (
        cone_conflicts(model) if initial_conflicts is None else initial_conflicts
    )
    checks = 0
    learned = []
    # Start from certified cones; shrink only with a proved contradiction.
    for conflict in conflicts:
        cs = set(conflict)
        if len(cs) <= 16:
            for component in sorted(cs):
                if checks >= max_checks or time.perf_counter() >= deadline:
                    break
                trial = cs - {component}
                checks += 1
                if certified_conflict(model, trial):
                    cs = trial
        learned.append(frozenset(cs))
    unique = []
    for c in sorted(set(learned), key=lambda x: (len(x), sorted(x))):
        if not any(p <= c for p in unique):
            unique.append(c)
    return unique, checks


def conflict_bound(conflicts):
    used = set()
    lower = 0
    for c in sorted(conflicts, key=lambda x: (len(x), sorted(x))):
        if not used & c:
            used.update(c)
            lower += 1
    return lower


def add_conflicts(pre, conflicts):
    added = 0
    existing_names = {c["name"] for g in pre["groups"] for c in g["constraints"]}
    next_index = 0
    for i, cs in enumerate(conflicts):
        reps = {pre["rename"]["AB_" + c] for c in cs}
        const = sum(pre["fixed"].get(n, 0) for n in reps)
        unknown = sorted(n for n in reps if n not in pre["fixed"])
        if const >= 1:
            continue
        if not unknown:
            raise ValueError("Conflict invalid under reduction")
        containing = [g for g in pre["groups"] if set(unknown) <= set(g["variables"])]
        if len(containing) != 1:
            continue  # Do not merge independent groups for a redundant cut.
        while "conflict_" + str(next_index) in existing_names:
            next_index += 1
        name = "conflict_" + str(next_index)
        existing_names.add(name)
        containing[0]["constraints"].append(
            dict(
                name=name,
                terms={n: 1 for n in unknown},
                quadratic=[],
                sense="ge",
                rhs=1 - const,
                kind="certified_conflict",
            )
        )
        added += 1
    return added
