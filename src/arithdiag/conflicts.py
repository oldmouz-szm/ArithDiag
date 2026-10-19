"""Sound, incomplete integer propagation with in-memory healthy explanations.

Only an actual interval, square, or exhaustive finite-product contradiction
returns a conflict. Round/deadline exhaustion returns None (UNKNOWN). Reasons
are deliberately conservative unions; they need not be inclusion minimal.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict

from arithdiag.preprocessing import normal_equations


def _ceildiv(a: int, b: int) -> int:
    assert b > 0
    return -((-a) // b)


def _product_interval(a: str, b: str, bounds: dict) -> tuple[int, int]:
    al, ah, _ = bounds[a]
    bl, bh, _ = bounds[b]
    if a == b:
        return (0 if al <= 0 <= ah else min(al * al, ah * ah), max(al * al, ah * ah))
    corners = (al * bl, al * bh, ah * bl, ah * bh)
    return min(corners), max(corners)


def explain_conflict(model, healthy, deadline=None, max_rounds=24):
    """Return a proved conflicting subset of healthy, or None for UNKNOWN.

    An empty frozenset is a contradiction in permanent wiring/observations, and
    must not be treated as a one-fault conflict. No model or caller set is mutated.
    The caller must keep the returned support in memory, not export its members.
    """
    healthy = frozenset(healthy)
    component_names = {c["name"] for c in model["components"]}
    if not healthy <= component_names:
        raise ValueError("Unknown healthy component")

    def expired():
        return deadline is not None and time.perf_counter() >= deadline

    def proved(support):
        return None if expired() else frozenset(support)

    if expired():
        return None
    # Bounds and observations are unconditional facts, so initially need no
    # healthy assumptions. One support per interval simplifies safe unions.
    bounds = {}
    for v in model["variables"]:
        if v["role"] == "abnormal":
            continue
        lo, hi = v["lb"], v["ub"]
        if not isinstance(lo, int) or not isinstance(hi, int):
            raise ValueError("Exact integer variable bounds required")
        if lo > hi:
            return proved(())
        bounds[v["name"]] = (lo, hi, frozenset())

    equations = []
    for raw in normal_equations(model):
        ab = raw.get("ab")
        if ab is not None and ab[3:] not in healthy:
            continue
        linear = defaultdict(int)
        quadratic = defaultdict(int)
        for term in raw["linear"]:
            linear[term["var"]] += term["coef"]
        for term in raw["quadratic"]:
            quadratic[tuple(sorted(term["vars"]))] += term["coef"]
        linear = {n: k for n, k in linear.items() if k}
        quadratic = {pair: k for pair, k in quadratic.items() if k}
        if any(
            not isinstance(k, int) for k in (*linear.values(), *quadratic.values())
        ) or not isinstance(raw["rhs"], int):
            raise ValueError("Exact integer polynomial coefficients required")
        names = set(linear) | {n for pair in quadratic for n in pair}
        equations.append(
            (
                linear,
                quadratic,
                raw["rhs"],
                names,
                frozenset() if ab is None else frozenset((ab[3:],)),
            )
        )

    for _ in range(max_rounds):
        changed = False
        fixed_products = defaultdict(list)
        for linear, quadratic, rhs, names, base_reason in equations:
            if expired():
                return None

            def reason():
                why = set(base_reason)
                for n in names:
                    why.update(bounds[n][2])
                return frozenset(why)

            def rest(exclude_linear=None):
                low = high = 0
                for n, k in linear.items():
                    if n == exclude_linear:
                        continue
                    lo, hi, _ = bounds[n]
                    low += min(k * lo, k * hi)
                    high += max(k * lo, k * hi)
                for (a, b), k in quadratic.items():
                    lo, hi = _product_interval(a, b, bounds)
                    low += min(k * lo, k * hi)
                    high += max(k * lo, k * hi)
                return low, high

            def tighten(n, lo, hi):
                nonlocal changed
                old_lo, old_hi, old_reason = bounds[n]
                lo, hi = max(lo, old_lo), min(hi, old_hi)
                if lo > hi:
                    return reason() | old_reason
                if (lo, hi) != (old_lo, old_hi):
                    bounds[n] = (lo, hi, reason() | old_reason)
                    changed = True
                return None

            low, high = rest()
            if not low <= rhs <= high:
                return proved(reason())
            nonlinear_names = {n for pair in quadratic for n in pair}
            for n, coefficient in linear.items():
                if n in nonlinear_names:
                    continue
                low, high = rest(n)
                lo, hi = rhs - high, rhs - low
                k = coefficient
                if k < 0:
                    lo, hi, k = -hi, -lo, -k
                conflict = tighten(n, _ceildiv(lo, k), hi // k)
                if conflict is not None:
                    return proved(conflict)

            # A single quadratic term permits sound reverse product bounds.
            # The remaining linear expression may be an interval; correlation
            # only weakens that interval, never removes a feasible assignment.
            if len(quadratic) != 1:
                continue
            (a, b), coefficient = next(iter(quadratic.items()))
            linear_low = linear_high = 0
            for n, k in linear.items():
                lo, hi, _ = bounds[n]
                linear_low += min(k * lo, k * hi)
                linear_high += max(k * lo, k * hi)
            product_low, product_high = rhs - linear_high, rhs - linear_low
            k = coefficient
            if k < 0:
                product_low, product_high, k = -product_high, -product_low, -k
            product_low, product_high = _ceildiv(product_low, k), product_high // k
            if product_low > product_high:
                return proved(reason())
            al, ah, _ = bounds[a]
            bl, bh, _ = bounds[b]
            if al >= 0 and bl >= 0:
                product_low = max(0, product_low)
                if product_low > product_high:
                    return proved(reason())
                if a == b:
                    root_low = math.isqrt(product_low)
                    root_low += root_low * root_low < product_low
                    conflict = tighten(a, root_low, math.isqrt(product_high))
                    if conflict is not None:
                        return proved(conflict)
                else:
                    # Re-read after each tightening: the other factor may now
                    # have a positive lower bound. Never divide by zero.
                    for target, other in ((a, b), (b, a)):
                        tl, th, _ = bounds[target]
                        ol, oh, _ = bounds[other]
                        if oh == 0:
                            if product_low > 0:
                                return proved(reason())
                            continue
                        lo = _ceildiv(product_low, oh)
                        hi = product_high // ol if ol > 0 else th
                        conflict = tighten(target, lo, hi)
                        if conflict is not None:
                            return proved(conflict)

            # Complete bounded checking is deliberately limited by interval
            # cardinality. A deadline in this scan yields UNKNOWN, not a proof.
            # Linear terms involving a/b would correlate the target product,
            # so only check a fixed linear remainder independent of the factors.
            if (
                a in linear
                or b in linear
                or not all(bounds[n][0] == bounds[n][1] for n in linear)
            ):
                continue
            exact_product = rhs - sum(k * bounds[n][0] for n, k in linear.items())
            if exact_product % coefficient:
                return proved(reason())
            exact_product //= coefficient
            if exact_product > 0 and bounds[a][0] >= 0 and bounds[b][0] >= 0:
                why = reason()
                for n in {a, b}:
                    fixed_products[n].append((exact_product, why))
            if a == b:
                if exact_product < 0:
                    return proved(reason())
                root = math.isqrt(exact_product)
                lo, hi, _ = bounds[a]
                if root * root != exact_product or not (
                    lo <= root <= hi or lo <= -root <= hi
                ):
                    return proved(reason())
                continue
            if bounds[b][1] - bounds[b][0] < bounds[a][1] - bounds[a][0]:
                a, b = b, a
            al, ah, _ = bounds[a]
            bl, bh, _ = bounds[b]
            if ah - al <= 2048:
                found = False
                for index, value in enumerate(range(al, ah + 1)):
                    if index % 64 == 0 and expired():
                        return None
                    if (value == 0 and exact_product == 0) or (
                        value != 0
                        and exact_product % value == 0
                        and bl <= exact_product // value <= bh
                    ):
                        found = True
                        break
                if not found:
                    return proved(reason())
        # A shared nonnegative factor of fixed positive products divides their
        # gcd. Unlike independent product intervals this retains a useful piece
        # of cross-equation correlation. Bounded divisor enumeration is either
        # complete or unused; interruption can never certify no divisor exists.
        for n, products in fixed_products.items():
            if expired():
                return None
            old_lo, old_hi, old_reason = bounds[n]
            why = set(old_reason)
            common = 0
            for value, support in products:
                common = math.gcd(common, value)
                why.update(support)
            lo, hi = max(old_lo, 1), min(old_hi, common)
            if lo > hi:
                return proved(why)
            root = math.isqrt(common)
            if root <= 4096:
                minimum = maximum = None
                for divisor in range(1, root + 1):
                    if divisor % 64 == 0 and expired():
                        return None
                    if common % divisor:
                        continue
                    for candidate in {divisor, common // divisor}:
                        if lo <= candidate <= hi:
                            minimum = (
                                candidate
                                if minimum is None
                                else min(minimum, candidate)
                            )
                            maximum = (
                                candidate
                                if maximum is None
                                else max(maximum, candidate)
                            )
                if minimum is None:
                    return proved(why)
                lo, hi = minimum, maximum
            if (lo, hi) != (old_lo, old_hi):
                bounds[n] = (lo, hi, frozenset(why))
                changed = True
        if not changed:
            break
    return None
