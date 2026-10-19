"""Big-M encoding, arithmetic metadata and exact local candidate checks."""

from arithdiag.integer_io import transport_constant_name


def encode(pre, group):
    names = {
        n: n if ":" not in n else "arithdiag_v_" + str(i)
        for i, n in enumerate(group["variables"])
    }
    specs = {names[n]: dict(pre["specs"][n], name=names[n]) for n in group["variables"]}
    g = dict(group, variables=list(specs), constraints=[])
    for c in group["constraints"]:
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
        lhs = sum(a * values[n] for n, a in c["terms"].items()) + sum(
            t["coef"] * values[t["a"]] * values[t["b"]] for t in c["quadratic"]
        )
        if not {"eq": lhs == c["rhs"], "le": lhs <= c["rhs"], "ge": lhs >= c["rhs"]}[
            c["sense"]
        ]:
            raise ValueError("Candidate exact row: " + c["name"])
    return sum(values["AB_" + c] for c in g["components"])
