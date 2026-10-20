"""Big-M encoding, arithmetic metadata and exact local candidate checks."""

from native_io import transport_constant_name
from collections import defaultdict


def lower_rows(specs, rows, source_model=None):
    """Lower conditional equalities to redundant domain-derived guards, LS only."""
    result = []
    originals = {
        c['component']: c for c in (source_model or {}).get('constraints', [])
        if c['kind'] == 'conditional_component'
    }
    original_specs = {v['name']: v for v in (source_model or {}).get('variables', [])}
    for c in rows:
        ab = c.get("ab")
        if ab is None:
            result.append(dict(c))
            continue
        if c["sense"] != "eq" or ab in c["terms"]:
            raise ValueError("Malformed conditional equation")
        # Preserve the frozen coefficient policy for an interpretable old/new
        # comparison: derive M from the original observation domains, but only
        # here at LS invocation. No M value exists in the common model.
        original = originals.get(c.get('component'))
        domain = original_specs if original else specs
        linear = defaultdict(int)
        if original:
            for t in original['linear']:
                linear[t['var']] += t['coef']
        else:
            linear.update(c['terms'])
        quadratic = ([dict(a=t['vars'][0], b=t['vars'][1], coef=t['coef'])
                      for t in original['quadratic']] if original else c['quadratic'])
        rhs = original['rhs'] if original else c['rhs']
        lo = hi = 0
        for n, k in linear.items():
            v = domain[n]
            lo += k * v["lb" if k >= 0 else "ub"]
            hi += k * v["ub" if k >= 0 else "lb"]
        for t in quadratic:
            a, b, k = domain[t["a"]], domain[t["b"]], t["coef"]
            if a["lb"] < 0 or b["lb"] < 0:
                raise ValueError("Unsigned product domains required")
            lo += k * (a["lb"]*b["lb"] if k >= 0 else a["ub"]*b["ub"])
            hi += k * (a["ub"]*b["ub"] if k >= 0 else a["lb"]*b["lb"])
        for side, sign, magnitude in (("pos",1,max(0,hi-rhs)),
                                      ("neg",-1,max(0,rhs-lo))):
            terms = {n:sign*k for n,k in c["terms"].items()}
            if magnitude:
                terms[ab] = -magnitude
            result.append(dict(c, name="guard_"+side+"_"+c["name"],
                kind="guarded_component", ab=None, sense="le", rhs=sign*c["rhs"],
                terms=terms, quadratic=[dict(t,coef=sign*t["coef"]) for t in c["quadratic"]]))
    return result


def encode(pre, group):
    names = {
        n: n if ":" not in n else "arithdiag_v_" + str(i)
        for i, n in enumerate(group["variables"])
    }
    specs = {names[n]: dict(pre["specs"][n], name=names[n]) for n in group["variables"]}
    g = dict(group, variables=list(specs), constraints=[])
    for c in lower_rows(pre["specs"], group["constraints"], pre.get('model')):
        g["constraints"].append(
            dict(
                c,
                terms={names[n]: a for n, a in c["terms"].items()},
                quadratic=[
                    dict(t, a=names[t["a"]], b=names[t["b"]])
                    for t in c.get("quadratic", [])
                ],
            )
        )
    return specs, g, names


def metadata(pre, group, names, seed, moves):
    rows = ["MODE " + str(int(moves))]
    specs, encoded, _ = encode(pre, group)
    one = transport_constant_name(specs, encoded)
    if one:
        rows.append("I " + one + " 1")
    if seed:
        rows += ["I " + names[n] + " " + str(seed[n]) for n in group["variables"]]
    active = set(group["variables"])
    for e in pre["equations"]:
        ns = set(e["terms"]) | {n for t in e["quadratic"] for n in (t["a"], t["b"])}
        if not ns <= active:
            continue
        if e["ab"] and e["ab"] not in active:
            continue
        terms = [(a, [names[n]]) for n, a in e["terms"].items()] + [
            (t["coef"], [names[t["a"]], names[t["b"]]]) for t in e["quadratic"]
        ]
        rows.append(
            "E "
            + (names[e["ab"]] if e["ab"] else "-")
            + " "
            + str(e["rhs"])
            + " "
            + str(len(terms))
            + " "
            + " ".join(
                str(a) + " " + str(len(ns)) + " " + " ".join(ns) for a, ns in terms
            )
        )
    return ("\n".join(rows) + "\n").encode()


def local_check(pre, g, values):
    if set(values) != set(g["variables"]):
        raise ValueError("Candidate variable mismatch")
    for n, x in values.items():
        if not pre["specs"][n]["lb"] <= x <= pre["specs"][n]["ub"]:
            raise ValueError("Candidate domain")
    for c in g["constraints"]:
        if c.get("ab") is not None and values[c["ab"]] == 1:
            continue
        lhs = sum(a * values[n] for n, a in c["terms"].items()) + sum(
            t["coef"] * values[t["a"]] * values[t["b"]] for t in c["quadratic"]
        )
        if not {"eq": lhs == c["rhs"], "le": lhs <= c["rhs"], "ge": lhs >= c["rhs"]}[
            c["sense"]
        ]:
            raise ValueError("Candidate exact row: " + c["name"])
    return sum(values["AB_" + c] for c in g["components"])
