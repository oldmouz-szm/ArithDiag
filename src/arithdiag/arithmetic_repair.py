"""Incomplete arithmetic witness construction for an IHS health assignment.

Never proves UNSAT. Failed branches, bounded divisor scans and deadlines only
mean UNKNOWN. Only original-model exact validation authorizes a returned witness.
The witness and health/component sets are kept in worker memory only.
"""

import math, time
from collections import defaultdict
from arithdiag.preprocessing import normal_equations
from arithdiag.integer_io import validate


class Stopped(Exception):
    pass


class Failed(Exception):
    pass


class Repair:
    def __init__(self, model, preferred=None):
        self.model = model
        self.preferred = preferred or {}
        self.specs = {
            v["name"]: v for v in model["variables"] if v["role"] != "abnormal"
        }
        self.fixed = {n: v["lb"] for n, v in self.specs.items() if v["lb"] == v["ub"]}
        self.rows = []
        self.factor_cache = {}
        for e in normal_equations(model):
            terms = [(t["coef"], (t["var"],)) for t in e["linear"]] + [
                (t["coef"], tuple(t["vars"])) for t in e["quadratic"]
            ]
            self.rows.append(
                (None if e["ab"] is None else e["ab"][3:], terms, e["rhs"])
            )
        self.metrics = dict(
            repair_calls=0, repair_sat=0, repair_unknown=0, repair_s=0.0, repair_nodes=0
        )

    def find(self, healthy, deadline, max_nodes=256):
        start = time.perf_counter()
        self.metrics["repair_calls"] += 1
        nodes = 0
        rows = [(ts, rhs) for c, ts, rhs in self.rows if c is None or c in healthy]

        def check():
            if time.perf_counter() >= deadline or nodes >= max_nodes:
                raise Stopped()

        def options_for_product(target, a, b):
            va, vb = self.specs[a], self.specs[b]
            al, ah = va["lb"], va["ub"]
            bl, bh = vb["lb"], vb["ub"]
            key = (target, al, ah, bl, bh)
            if key in self.factor_cache:
                return self.factor_cache[key]
            out = []

            def add(x, y):
                if al <= x <= ah and bl <= y <= bh and (x, y) not in out:
                    out.append((x, y))

            if target == 0:
                add(0, self.preferred.get(b, bl))
                add(self.preferred.get(a, al), 0)
            elif target > 0:
                for x in (self.preferred.get(a, al), al, ah, 1):
                    if x and target % x == 0:
                        add(x, target // x)
                for y in (self.preferred.get(b, bl), bl, bh, 1):
                    if y and target % y == 0:
                        add(target // y, y)
                for d in range(1, min(math.isqrt(target), 20000) + 1):
                    if d % 64 == 0:
                        check()
                    if target % d == 0:
                        add(d, target // d)
                        add(target // d, d)
            self.factor_cache[key] = out
            return out

        def analyse(terms, rhs, values):
            constant = 0
            unknown = defaultdict(int)
            for coef, ns in terms:
                un = []
                z = coef
                for n in ns:
                    if n in values:
                        z *= values[n]
                    else:
                        un.append(n)
                if not un:
                    constant += z
                else:
                    unknown[tuple(sorted(un))] += z
            return {ns: c for ns, c in unknown.items() if c}, rhs - constant

        def bounded(n, x):
            return self.specs[n]["lb"] <= x <= self.specs[n]["ub"]

        def dfs(values, depth=0):
            nonlocal nodes
            check()
            nodes += 1
            if depth > 128:
                raise Stopped()
            while True:
                changed = False
                open_rows = []
                branch = None
                for terms, rhs in rows:
                    check()
                    poly, target = analyse(terms, rhs, values)
                    if not poly:
                        if target:
                            raise Failed()
                        continue
                    names = {n for ns in poly for n in ns}
                    if len(names) == 1:
                        n = next(iter(names))
                        a = poly.get((n, n), 0)
                        b = poly.get((n,), 0)
                        roots = []
                        if a:
                            disc = b * b + 4 * a * target
                            if disc >= 0:
                                root = math.isqrt(disc)
                                if root * root == disc:
                                    for sign in (-1, 1):
                                        num = -b + sign * root
                                        if num % (2 * a) == 0 and bounded(
                                            n, num // (2 * a)
                                        ):
                                            roots.append(num // (2 * a))
                        elif b and target % b == 0 and bounded(n, target // b):
                            roots = [target // b]
                        roots = list(dict.fromkeys(roots))
                        if not roots:
                            raise Failed()
                        if len(roots) == 1:
                            values[n] = roots[0]
                            changed = True
                            continue
                        branch = [{n: x} for x in roots]
                    open_rows.append((poly, target))
                if not changed:
                    break
            if not open_rows:
                complete = {
                    n: values.get(n, self.preferred.get(n, v["lb"]))
                    for n, v in self.specs.items()
                }
                complete.update(
                    {
                        "AB_" + c["name"]: int(c["name"] not in healthy)
                        for c in self.model["components"]
                    }
                )
                result = validate(self.model, complete)
                if result["valid"]:
                    return complete
                raise Failed()
            if branch is None:
                for poly, target in open_rows:
                    if len(poly) == 1:
                        ns, k = next(iter(poly.items()))
                        if len(ns) == 2 and ns[0] != ns[1] and target % k == 0:
                            a, b = ns
                            pairs = options_for_product(target // k, a, b)
                            branch = [{a: x, b: y} for x, y in pairs]
                            if not branch:
                                raise Failed()
                            break
            if branch is None:
                poly, target = min(open_rows, key=lambda z: len(z[0]))
                n = min(
                    {n for ns in poly for n in ns},
                    key=lambda n: self.specs[n]["ub"] - self.specs[n]["lb"],
                )
                v = self.specs[n]
                choices = list(
                    dict.fromkeys(
                        [
                            self.preferred.get(n, v["lb"]),
                            v["lb"],
                            v["ub"],
                            *range(v["lb"], min(v["ub"] + 1, v["lb"] + 8)),
                        ]
                    )
                )
                branch = [{n: x} for x in choices if bounded(n, x)]
            for assign in branch:
                try:
                    return dfs(dict(values, **assign), depth + 1)
                except Failed:
                    pass
            raise Failed()

        try:
            witness = dfs(dict(self.fixed))
            check()
            self.metrics["repair_sat"] += 1
            return witness
        except (Failed, Stopped):
            self.metrics["repair_unknown"] += 1
            return None
        finally:
            self.metrics["repair_nodes"] += nodes
            self.metrics["repair_s"] += time.perf_counter() - start


def install():
    from arithdiag import adaptive_proof

    step = adaptive_proof.AdaptiveIHSDriver.step
    explain = adaptive_proof.explain_conflict
    active = []

    def wrapped_step(self, *args, **kwargs):
        active.append(self)
        try:
            return step(self, *args, **kwargs)
        finally:
            active.pop()
            if hasattr(self, "repair_engine"):
                self.metrics.update(self.repair_engine.metrics)

    def wrapped_explain(model, healthy, deadline=None, **kwargs):
        result = explain(model, healthy, deadline=deadline, **kwargs)
        if (
            result is None
            and active
            and deadline is not None
            and deadline - time.perf_counter() > 0.01
        ):
            driver = active[-1]
            if not hasattr(driver, "repair_engine"):
                driver.repair_engine = Repair(model, getattr(driver, "preferred", None))
            witness = driver.repair_engine.find(
                healthy, min(deadline, time.perf_counter() + 0.15)
            )
            if witness is not None:
                driver.transient_candidate = witness
        return result

    adaptive_proof.AdaptiveIHSDriver.step = wrapped_step
    adaptive_proof.explain_conflict = wrapped_explain
