"""An above-goal cover only proposes a health query after an UNKNOWN master."""
from pathlib import Path
import json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from arithdiag import adaptive_proof as m
from arithdiag.proof import ProofDriver
saved=(ProofDriver.step,m.has_hitting_set_at_most,m.explain_conflict,m.explain_relations)
try:
    ProofDriver.step=lambda self,l,u,h,b:l
    m.explain_relations=lambda *a,**k:None
    calls=[]
    def query(edges,k,**options):
        assert k==0 and options['deadline']<time.monotonic()+.075
        return dict(status='UNKNOWN',nodes=0)
    m.has_hitting_set_at_most=query
    for refute in (False,True):
        m.explain_conflict=lambda model,healthy,**kwargs:(calls.append(frozenset(healthy)) or (frozenset({'C2'}) if refute else None))
        model=dict(components=[dict(name='C'+str(i),operation='add') for i in range(3)])
        driver=m.AdaptiveIHSDriver(model,{},[frozenset({'C0'}),frozenset({'C1'})],inject_ls_cuts=False)
        driver.available_budget=lambda request:request
        driver._master=lambda l,u,d:l
        lower=driver.step(0,3,{'C0','C1','C2'},.1)
        assert lower==0 and driver.metrics['ihs_refuted_cardinality_queries']==0
        assert driver.metrics['ihs_last_master_status']=='UNKNOWN'
        assert driver.metrics['cover_proposals']==1 and calls[-1]==frozenset({'C2'})
        assert driver.metrics['proposal_conflicts']==int(refute)
finally:ProofDriver.step,m.has_hitting_set_at_most,m.explain_conflict,m.explain_relations=saved
print(json.dumps(dict(passed=True,larger_cover_is_not_goal_sat=True,
    proposal_refutation_not_a_goal_unsat=True,reserved_integer_check_exercised=True)))
