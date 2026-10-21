"""Exact-cover truth and interruption/resumption checks independent of DFS code."""
from pathlib import Path
import itertools,json,random,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from arithdiag import resumable_master as p
rng=random.Random(2026102102);queries=0;resumed=0
for trial in range(240):
    n=rng.randrange(3,10);edges=[]
    for _ in range(rng.randrange(2,22)):
        edges.append(frozenset(rng.sample(range(n),rng.randrange(1,min(n,5)+1))))
    optimum=next(k for k in range(n+1) if any(all(set(c)&e for e in edges) for c in itertools.combinations(range(n),k)))
    p.clear()
    observed=[];nodes=0
    for step in range(2500):
        row=p.improve(edges,deadline=None,max_nodes=1,on_candidate=observed.append)
        nodes+=row['nodes'];queries+=1
        assert row['conflict_lower_bound']<=optimum<=row['auxiliary_upper_bound']
        assert all(all(c&e for e in edges) for c in observed)
        if row['exact']:break
    else:raise AssertionError(('resumption failed to complete',trial))
    assert row['conflict_lower_bound']==row['auxiliary_upper_bound']==optimum
    if step:resumed+=1
    p.clear();single=p.improve(edges,max_nodes=None)
    assert single['exact'] and single['conflict_lower_bound']==optimum
    assert single['nodes']==nodes,('Repeated DFS expansion after resume',trial,single['nodes'],nodes)
    changed=edges+[frozenset({n})]
    second=p.improve(changed,max_nodes=None)
    assert second['exact'] and second['conflict_lower_bound']==optimum+1
p.clear();late=[]
row=p.improve([{0,1},{1,2}],deadline=time.monotonic()-1,on_candidate=late.append)
assert not row['exact'] and not late
assert resumed>0
print(json.dumps(dict(passed=True,random_hypergraphs=240,limited_queries=queries,
    resumed_graphs=resumed,no_repeated_expansion=True,changed_family_checked=True,late_is_unknown=True)))
