"""Check real grants, nonrenewing accounting, early return and exception safety."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag import internal_budget as mod

real_time = mod.time
count = 0
try:
    for policy in mod.POLICIES:
        for remaining in (120.0, 7.0, 0.0):
            for early in (False, True):
                tick = [100.0]
                mod.time = SimpleNamespace(perf_counter=lambda: tick[0])
                driver = SimpleNamespace(metrics={"proof_strengthening_s": 0.0}, proof_cap_s=48.0)

                def accrued(requested):
                    return min(requested, max(0, min(48, 1 + (tick[0] - 100) * 0.1) - driver.metrics["proof_strengthening_s"]))

                driver.available_budget = accrued
                coop = SimpleNamespace(driver=driver, lower=0)
                out = {}

                def strengthen(request):
                    allowed = driver.available_budget(request)
                    second = driver.available_budget(allowed)
                    consumed = min(second, 0.1) if early else second
                    tick[0] += consumed
                    driver.metrics["proof_strengthening_s"] += consumed
                    coop.lower = 1

                # Actual coordinator always clips its request to the deadline.
                def bounded(request):
                    strengthen(min(request, max(0, 100 + remaining - tick[0] - 0.03)))

                mod.run_initial(coop, policy, 100 + remaining, out, bounded, lambda: tick[0] - 100)
                remain = max(0, remaining - 0.03)
                expected = mod.FRACTIONS[policy] * remain
                assert abs(out["initial_phase_granted_s"] - expected) < 1e-8, out
                spent = min(expected, 0.1) if early else expected
                assert abs(out["initial_phase_proof_spent_s"] - spent) < 1e-8, out
                assert out["initial_phase_policy_restored"] == (policy not in mod.FRACTIONS)
                if policy in mod.FRACTIONS:
                    assert abs(driver.available_budget(1000) - (expected - spent)) < 1e-8
                    tick[0] += 5
                    assert abs(driver.available_budget(1000) - min(expected - spent, max(0, 100 + remaining - tick[0] - 0.03))) < 1e-8
                count += 1
    for policy in mod.POLICIES:
        tick = [100.0]
        mod.time = SimpleNamespace(perf_counter=lambda: tick[0])
        driver = SimpleNamespace(metrics={"proof_strengthening_s": 0.0}, proof_cap_s=48.0)
        original = lambda requested: min(1, requested)
        driver.available_budget = original
        coop = SimpleNamespace(driver=driver, lower=0)
        out = {}

        def fail(request):
            raise RuntimeError("injected")

        try:
            mod.run_initial(coop, policy, 220.0, out, fail, lambda: tick[0] - 100)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Exception was suppressed")
        assert driver.available_budget is not fail
        assert out["initial_phase_policy_restored"] == (policy not in mod.FRACTIONS)
        assert out["initial_phase_actual_s"] == 0
        count += 1
finally:
    mod.time = real_time

for retired in ("unknown", "current", "initial50", "fraction25", "fraction40"):
    try:
        mod.policy_configuration(retired)
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported policy accepted")
print(json.dumps(dict(passed=True, budget_accounting_cases=count, fraction_denominator="remaining_global_time", no_time_refund=True)))
