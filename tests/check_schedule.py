"""Clock-controlled regression for early handoff and a nonrenewing 50% ledger."""
from pathlib import Path
from types import SimpleNamespace
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from arithdiag import internal_budget as mod
original=mod.time;count=0
try:
    for remaining in (120.,12.,.01):
        for early in (False,True):
            tick=[100.]
            mod.time=SimpleNamespace(perf_counter=lambda:tick[0])
            driver=SimpleNamespace(metrics={'proof_strengthening_s':0.},proof_cap_s=48.)
            driver.available_budget=lambda request:min(1.,request)
            coord=SimpleNamespace(driver=driver,lower=0)
            result={}
            def strengthen(request):
                grant=driver.available_budget(request)
                if early:grant=min(.1,grant)
                tick[0]+=grant;driver.metrics['proof_strengthening_s']+=grant
            mod.run_initial(coord,'interleaved50',100.+remaining,result,strengthen,lambda:tick[0]-100.)
            cap=.5*max(0.,remaining-.03)
            assert abs(result['internal_budget_total_s']-cap)<1e-8
            assert result['initial_phase_granted_s']<=min(5.,cap)+1e-8
            assert result['initial_phase_proof_spent_s']<=min(5.,cap)+1e-8
            assert driver.available_budget(1000.)<1e-8
            if remaining>12:
                tick[0]+=2.
                assert abs(driver.available_budget(1000.)-2.)<1e-8
                # A proof second consumes credit; it never earns itself credit.
                tick[0]+=1.;driver.metrics['proof_strengthening_s']+=1.
                assert abs(driver.available_budget(1000.)-1.)<1e-8
                tick[0]+=50.
                assert driver.available_budget(1000.)<=cap-driver.metrics['proof_strengthening_s']+1e-8
                driver.metrics['proof_strengthening_s']=cap
                tick[0]+=1.
                assert driver.available_budget(1000.)==0
            tick[0]=100.+remaining
            assert driver.available_budget(1000.)==0
            count+=1
finally:mod.time=original
# Borrowing advances only existing credit; it cannot refill the ledger.
original=mod.time
try:
    tick=[100.];mod.time=SimpleNamespace(perf_counter=lambda:tick[0])
    available=lambda request:0.
    driver=SimpleNamespace(metrics={'proof_strengthening_s':5.},proof_cap_s=60.,available_budget=available)
    coord=SimpleNamespace(driver=driver)
    def work(request):
        grant=driver.available_budget(request)
        assert grant<=55.
        tick[0]+=grant;driver.metrics['proof_strengthening_s']+=grant
    mod.borrow_remaining(coord,220.,work)
    assert driver.metrics['proof_strengthening_s']==60. and driver.available_budget is available
    mod.borrow_remaining(coord,220.,lambda request:(_ for _ in ()).throw(AssertionError('Renewed quota')))
    driver.metrics['proof_strengthening_s']=5.
    try:mod.borrow_remaining(coord,220.,lambda request:(_ for _ in ()).throw(RuntimeError('injected')))
    except RuntimeError:pass
    else:raise AssertionError('Suppressed exception')
    assert driver.available_budget is available
finally:mod.time=original
print(json.dumps(dict(passed=True,scheduling_cases=count,early_handoff=True,no_credit_from_proof_time=True,nonrenewing_cap=True)))
