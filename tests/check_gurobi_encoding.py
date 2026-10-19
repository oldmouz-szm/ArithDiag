"""Exhaustive small and wide integer encoding checks; one available license."""

from pathlib import Path
import itertools, json, os, resource, sys, time

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "ArithDiag-G"))
resource.setrlimit(resource.RLIMIT_AS, (8192 * 1024**2,) * 2)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
import gurobipy as gp
from limb_model import Encoding


def pre_model(op, ub=3):
    specs = {n: dict(name=n, lb=0, ub=ub, role="signal") for n in ("a", "b", "o")}
    specs["AB_c"] = dict(name="AB_c", lb=0, ub=1, role="abnormal")
    row = dict(
        name="r",
        kind="function",
        component="c",
        terms={"o": 1, "a": -1, "b": -1} if op == "add" else {"o": 1},
        quadratic=[] if op == "add" else [dict(a="a", b="b", coef=-1)],
        rhs=0,
        sense="eq",
        ab="AB_c",
    )
    return dict(specs=specs, equations=[row], fixed={}, groups=[])


def fixed_case(enc, x, expected):
    for n, ids in enc.maps.items():
        z = x[n]
        for i in ids:
            enc.vs[i].LB = enc.vs[i].UB = z % 256
            z //= 256
    enc.m.optimize()
    assert (enc.m.Status == gp.GRB.OPTIMAL) == expected
    if expected:
        assert (
            enc.decode(enc.m.getAttr("X", enc.vs)) == x
            and enc.decode(enc.assignment(x)) == x
        )


env = gp.Env(empty=True)
env.setParam("OutputFlag", 0)
env.setParam("WLSTokenDuration", 5)
env.setParam("WLSTokenRefresh", 1.0)
env.start()
small = wide = 0
try:
    for op in ("add", "mul"):
        enc = Encoding(pre_model(op), env, time.perf_counter() + 60)
        enc.audit()
        enc.m.Params.Threads = 1
        enc.m.Params.NonConvex = 2
        for a, b, o, ab in itertools.product(range(4), range(4), range(4), range(2)):
            fixed_case(
                enc,
                dict(a=a, b=b, o=o, AB_c=ab),
                bool(ab or o == (a + b if op == "add" else a * b)),
            )
            small += 1
        enc.m.dispose()
    for ab in (0, 1):
        for a, b in (((1 << 32) + 1, (1 << 32) - 1), ((1 << 31) + 3, (1 << 33) - 1)):
            for delta in (0, 1):
                x = dict(a=a, b=b, o=a * b + delta, AB_c=ab)
                enc = Encoding(
                    pre_model("mul", (1 << 65) - 1), env, time.perf_counter() + 60
                )
                enc.audit()
                enc.m.Params.Threads = 1
                enc.m.Params.NonConvex = 2
                fixed_case(enc, x, bool(ab or delta == 0))
                wide += 1
                enc.m.dispose()
    for rhs in ((1 << 64) + 3, -((1 << 64) + 3)):
        pre = pre_model("add", (1 << 65) - 1)
        pre["equations"][0].update(
            terms={"o": 1 if rhs > 0 else -1}, rhs=rhs, quadratic=[], ab=None
        )
        enc = Encoding(pre, env, time.perf_counter() + 60)
        enc.audit()
        x = dict(a=0, b=0, o=abs(rhs), AB_c=0)
        assert enc.decode(enc.assignment(x)) == x
        enc.m.dispose()
        wide += 1
finally:
    env.dispose()
print(
    json.dumps(
        dict(
            passed=True,
            small_encoding_assignments=small,
            wide_encoding_assignments=wide,
        )
    )
)
