"""Exact radix-256 formulation of unsigned component weak-fault diagnosis.

No wide integer is converted to a float. Digit products are unconditional
definitions; only the component's functional carry equations are guarded.
Faulty outputs retain precisely their legal range. All witnesses stay in RAM.
"""

import hashlib, json, math, time
from collections import defaultdict
import gurobipy as gp
from gurobipy import GRB

B = 256


def digits(x):
    assert isinstance(x, int)
    sign = -1 if x < 0 else 1
    x = abs(x)
    out = []
    while x:
        out.append(sign * (x % B))
        x //= B
    return out or [0]



def semantic_audit(model):
    specs = {v["name"]: v for v in model["variables"]}
    seen = set()
    for row in model["constraints"]:
        if row["kind"] == "observation":
            assert row["sense"] == "eq" and not row["quadratic"] and len(row["linear"]) == 1
            t = row["linear"][0]
            s = specs[t["var"]]
            assert s["lb"] == s["ub"] and t["coef"] * s["lb"] == row["rhs"]
        elif row["kind"] == "wiring":
            assert row["sense"] == "eq"
        elif row["kind"] == "conditional_component":
            ab = row["abnormal"]
            assert ab == "AB_" + row["component"] and ab not in seen
            assert specs[ab]["type"] == "binary" and row["sense"] == "eq"
            assert all(t["var"] != ab for t in row["linear"])
            assert all(ab not in t["vars"] for t in row["quadratic"])
            seen.add(ab)
        else:
            raise ValueError("Unsupported semantic row category")
    assert seen == {"AB_"+c["name"] for c in model["components"]}
    return dict(conditional_components=len(seen), backend_neutral_semantics_audited=True)

class Encoding:
    def __init__(self, pre, env, deadline):
        self.pre = pre
        self.deadline = deadline
        self.m = gp.Model(env=env)
        self.vs = []
        self.bounds = []
        self.maps = {}
        self.products = {}
        self.columns = []
        self.rows = []
        self.qrows = []
        self.inds = []
        self.slacks = []
        self.max_number = 0
        for n, s in pre["specs"].items():
            self.check()
            assert s["lb"] >= 0
            if s["role"] == "abnormal":
                self.maps[n] = [self.var(0, 1, True)]
            else:
                count = max(1, (s["ub"].bit_length() + 7) // 8)
                self.maps[n] = [
                    self.var(0, min(B - 1, s["ub"] // (B**i))) for i in range(count)
                ]
                if s["ub"] != (1 << (s["ub"].bit_length())) - 1:
                    slack = [
                        self.var(0, min(B - 1, s["ub"] // (B**i))) for i in range(count)
                    ]
                    self.slacks.append((n, slack, s["ub"], 1))
                    self.polynomial([(1, self.maps[n]), (1, slack)], [], s["ub"], None)
                if s["lb"]:
                    slack = [self.var(0, B - 1) for _ in range(count)]
                    self.slacks.append((n, slack, s["lb"], -1))
                    self.polynomial([(1, self.maps[n]), (-1, slack)], [], s["lb"], None)
        for e in pre["equations"]:
            self.check()
            assert e["sense"] == "eq"
            self.polynomial(
                [(k, self.maps[n]) for n, k in e["terms"].items()],
                [
                    (t["coef"], self.maps[t["a"]], self.maps[t["b"]])
                    for t in e["quadratic"]
                ],
                e["rhs"],
                None if e["ab"] is None else self.maps[e["ab"]][0],
            )
        for g in pre["groups"]:
            for r in g["constraints"]:
                if r["kind"] == "certified_conflict":
                    terms = {self.maps[n][0]: k for n, k in r["terms"].items()}
                    self.linear(terms, r["sense"], r["rhs"])
        objective = gp.LinExpr(
            [1] * sum(s["role"] == "abnormal" for s in pre["specs"].values()),
            [
                self.vs[self.maps[n][0]]
                for n, s in pre["specs"].items()
                if s["role"] == "abnormal"
            ],
        )
        self.offset = sum(x for n, x in pre["fixed"].items() if n.startswith("AB_"))
        self.m.setObjective(objective + self.offset, GRB.MINIMIZE)
        self.m.update()
        payload = dict(
            bounds=self.bounds,
            linear=self.rows,
            indicators=self.inds,
            quadratic=self.qrows,
            offset=self.offset,
            mapping=self.maps,
        )
        self.digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError("model deadline")

    def number(self, x):
        assert isinstance(x, int) and abs(x) < 2**53
        assert int(float(x)) == x
        assert abs(x) <= 1000000, "Native input exceeds the tested safe numeric range"
        self.max_number = max(self.max_number, abs(x))
        return x

    def var(self, lo, hi, binary=False):
        lo = self.number(lo)
        hi = self.number(hi)
        assert lo <= hi
        i = len(self.vs)
        self.vs.append(
            self.m.addVar(
                lb=lo,
                ub=hi,
                vtype=GRB.BINARY if binary else GRB.INTEGER,
                name="v" + str(i),
            )
        )
        self.bounds.append((lo, hi, "B" if binary else "I"))
        return i

    def expr(self, terms):
        return gp.LinExpr(
            [self.number(k) for k in terms.values()], [self.vs[i] for i in terms]
        )

    def linear(self, terms, sense, rhs, ab=None):
        terms = {i: k for i, k in terms.items() if k}
        rhs = self.number(rhs)
        expr = self.expr(terms)
        if ab is not None:
            assert sense == "eq"
            self.m.addGenConstrIndicator(self.vs[ab], False, expr, GRB.EQUAL, rhs)
            self.inds.append((ab, sorted(terms.items()), rhs))
        else:
            self.m.addLConstr(
                expr,
                {"eq": GRB.EQUAL, "le": GRB.LESS_EQUAL, "ge": GRB.GREATER_EQUAL}[sense],
                rhs,
            )
            self.rows.append((sorted(terms.items()), sense, rhs))

    def product(self, a, b):
        key = tuple(sorted((a, b)))
        if key not in self.products:
            assert self.bounds[a][0] >= 0 and self.bounds[b][0] >= 0
            p = self.var(0, self.bounds[a][1] * self.bounds[b][1])
            self.products[key] = p
            self.m.addQConstr(self.vs[p] == self.vs[a] * self.vs[b])
            self.qrows.append((p, a, b))
        return self.products[key]

    def polynomial(self, linear, quad, rhs, ab):
        cols = defaultdict(lambda: defaultdict(int))
        for coef, vs in linear:
            for j, k in enumerate(digits(coef)):
                if k:
                    for i, v in enumerate(vs):
                        cols[i + j][v] += k
        for coef, aa, bb in quad:
            for j, k in enumerate(digits(coef)):
                if k:
                    for a, x in enumerate(aa):
                        for b, y in enumerate(bb):
                            cols[a + b + j][self.product(x, y)] += k
        rd = digits(rhs)
        count = max(max(cols, default=0) + 1, len(rd))
        carry = None
        for i in range(count):
            terms = dict(cols[i])
            r = rd[i] if i < len(rd) else 0
            if carry is not None:
                terms[carry] = terms.get(carry, 0) + 1
            raw = dict(terms)
            out = None
            if i < count - 1:
                lo = (
                    sum(
                        min(k * self.bounds[v][0], k * self.bounds[v][1])
                        for v, k in terms.items()
                    )
                    - r
                )
                hi = (
                    sum(
                        max(k * self.bounds[v][0], k * self.bounds[v][1])
                        for v, k in terms.items()
                    )
                    - r
                )
                out = self.var(min(0, lo // B - 1), max(0, -(-hi // B) + 1))
                terms[out] = -B
            self.linear(terms, "eq", r, ab)
            self.columns.append((ab, raw, r, out))
            carry = out

    def audit(self):
        m = self.m
        m.update()
        assert len(self.vs) == m.NumVars
        assert (
            len(self.rows) == m.NumConstrs
            and len(self.inds) == m.NumGenConstrs
            and len(self.qrows) == m.NumQConstrs
        )
        assert m.ModelSense == GRB.MINIMIZE and m.ObjCon == self.offset
        objective = {
            self.maps[n][0]
            for n, s in self.pre["specs"].items()
            if s["role"] == "abnormal"
        }
        assert all(v.Obj == int(i in objective) for i, v in enumerate(self.vs))
        for v, (lo, hi, typ) in zip(self.vs, self.bounds):
            assert v.LB == lo and v.UB == hi and v.VType == typ
        for c, (terms, sense, rhs) in zip(m.getConstrs(), self.rows):
            assert c.RHS == rhs and c.Sense == {"eq": "=", "ge": ">", "le": "<"}[sense]
            r = m.getRow(c)
            actual = {r.getVar(i).index: r.getCoeff(i) for i in range(r.size())}
            assert actual == dict(terms)
        for c, (ab, terms, rhs) in zip(m.getGenConstrs(), self.inds):
            v, value, expr, sense, r = m.getGenConstrIndicator(c)
            assert v.index == ab and value == 0 and sense == "=" and r == rhs
            assert {
                expr.getVar(i).index: expr.getCoeff(i) for i in range(expr.size())
            } == dict(terms)
        for c, (p, a, b) in zip(m.getQConstrs(), self.qrows):
            q = m.getQCRow(c)
            lin = q.getLinExpr()
            assert c.QCRHS == 0 and c.QCSense == "="
            lc = {lin.getVar(i).index: lin.getCoeff(i) for i in range(lin.size())}
            assert q.size() == 1 and q.getCoeff(0) in (-1, 1)
            assert sorted((q.getVar1(0).index, q.getVar2(0).index)) == sorted((a, b))
            assert lc == {p: -q.getCoeff(0)}
        return dict(
            formulation="radix256_exact_carries_indicator_weak_fault",
            model_sha256=self.digest,
            readback_audit=True,
            variables=m.NumVars,
            linear_constraints=m.NumConstrs,
            indicator_constraints=m.NumGenConstrs,
            quadratic_constraints=m.NumQConstrs,
            largest_transported_integer=self.max_number,
        )

    def decode(self, values):
        vals = []
        for x, (lo, hi, _) in zip(values, self.bounds):
            if not math.isfinite(x) or abs(x - round(x)) > 1e-5:
                raise ValueError("nonintegral native candidate")
            n = round(x)
            if not lo <= n <= hi:
                raise ValueError("native candidate range")
            vals.append(n)
        return {
            n: sum(vals[v] * B**i for i, v in enumerate(vs))
            for n, vs in self.maps.items()
        }

    def assignment(self, values):
        z = [0] * len(self.vs)
        for n, vs in self.maps.items():
            value = values[n]
            for v in vs:
                z[v] = value % B
                value //= B
            if value:
                raise ValueError("candidate width")
        for n, vs, bound, sign in self.slacks:
            value = (bound - values[n]) * sign
            for v in vs:
                z[v] = value % B
                value //= B
            if value:
                raise ValueError("candidate bound slack")
        for (a, b), p in self.products.items():
            z[p] = z[a] * z[b]
        for ab, terms, r, out in self.columns:
            if ab is not None and z[ab]:
                if out is not None:
                    z[out] = 0
                continue
            num = sum(k * z[v] for v, k in terms.items()) - r
            if out is None:
                if num:
                    raise ValueError("candidate final carry")
            else:
                if num % B:
                    raise ValueError("candidate nonintegral carry")
                z[out] = num // B
        for x, (lo, hi, _) in zip(z, self.bounds):
            if not lo <= x <= hi:
                raise ValueError("candidate aux range")
        return z
