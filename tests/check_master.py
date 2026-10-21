"""Independent exhaustive truth and duplicate-solve regression for the master."""
from pathlib import Path
import itertools,json,random,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from arithdiag import hitting_set as h,component_master as cm
rng=random.Random(20261021);checks=0
for i in range(350):
    n=1+i%8
    edges=[frozenset(v for v in range(n) if rng.random()<.4) for _ in range(i%16)]
    allsets=[frozenset(s) for k in range(n+1) for s in itertools.combinations(range(n),k)]
    feasible=[s for s in allsets if all(s&e for e in edges)]
    optimum=min(map(len,feasible)) if feasible else None
    for k in range(n+1):
        captured=[];row=h.has_hitting_set_at_most(edges,k,on_candidate=captured.append)
        assert row['status']==('SAT' if optimum is not None and optimum<=k else 'UNSAT')
        if captured:assert len(captured[0])<=k and all(captured[0]&e for e in edges)
        checks+=1
    captured=[];row=h.improve_bound(edges,on_candidate=captured.append)
    if optimum is not None:
        assert row['conflict_lower_bound']==optimum and row['exact']
        assert captured and min(map(len,captured))==optimum
        assert all(all(s&e for e in edges) for s in captured)
    else:assert row['infeasible']
    late=[];row=h.has_hitting_set_at_most(edges,n,deadline=time.monotonic()-1,on_candidate=late.append)
    assert row['status']=='UNKNOWN' and not late
# An odd cycle has packing 1 but a feasible half-weight dual proves 2.
triangle=[frozenset((0,1)),frozenset((1,2)),frozenset((0,2))]
row=h.improve_bound(triangle)
assert row['conflict_lower_bound']==2 and row['exact']
cm.CACHE.clear();cm.PARTS.clear()
edges=[frozenset((0,1)),frozenset((1,2)),frozenset((0,2))]
row=cm.improve(edges,deadline=time.monotonic()+2,max_nodes=10000)
assert row['conflict_lower_bound']==2 and row['exact']
saved=cm.ORIGINAL_DECIDE;calls=[0]
def count(*args,**kwargs):calls[0]+=1;return saved(*args,**kwargs)
cm.ORIGINAL_DECIDE=count
try:
    captured=[];row=cm.decide(edges,2,deadline=time.monotonic()+2,max_nodes=10000,on_candidate=captured.append)
    assert row['status']=='SAT' and len(captured[0])==2
    assert calls[0]==0,'An optimized exact part was solved again only to retrieve its cover'
    # Changing the edge family must invalidate the cached cover.
    captured=[];changed=edges+[frozenset((3,))]
    row=cm.decide(changed,3,deadline=time.monotonic()+2,max_nodes=10000,on_candidate=captured.append)
    assert row['status']=='SAT' and all(captured[0]&e for e in changed)
finally:cm.ORIGINAL_DECIDE=saved
print(json.dumps(dict(passed=True,exhaustive_queries=checks,cached_cover_reused=True,changed_family_checked=True,expired_is_unknown=True)))
