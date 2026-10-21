"""Independent exhaustive integer checks for every returned affine support."""
from pathlib import Path
import itertools,json,random,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from arithdiag.affine_conflicts import explain_affine
rng=random.Random(2026102103);queries=conflicts=0
for i in range(360):
    components=[dict(name='C'+str(j)) for j in range(4)]
    bounds=[(-2,3),(0,3),(0,3)]
    if i%3==0:bounds[i%3]=(i%4,i%4)
    variables=[dict(name='x'+str(j),role='wire',lb=lo,ub=hi) for j,(lo,hi) in enumerate(bounds)]
    rows=[]
    for j in range(4):
        lin=[dict(var='x'+str(v),coef=rng.choice((-2,-1,0,1,2))) for v in range(3)]
        quad=[] if i%2 else [dict(vars=['x'+str(rng.randrange(3)),'x'+str(rng.randrange(3))],coef=rng.choice((-2,-1,0,1,2)))]
        rows.append(dict(kind='conditional_component',component='C'+str(j),abnormal='AB_C'+str(j),sense='eq',rhs=rng.randrange(-5,13),linear=lin,quadratic=quad))
    model=dict(variables=variables,components=components,constraints=rows);states=[]
    for values in itertools.product(*(range(lo,hi+1) for lo,hi in bounds)):
        x={'x'+str(j):v for j,v in enumerate(values)};healthy=set()
        for j,row in enumerate(rows):
            lhs=sum(t['coef']*x[t['var']] for t in row['linear'])+sum(t['coef']*x[t['vars'][0]]*x[t['vars'][1]] for t in row['quadratic'])
            if lhs==row['rhs']:healthy.add('C'+str(j))
        states.append(healthy)
    for mask in range(16):
        healthy={c['name'] for j,c in enumerate(components) if mask>>j&1}
        core=explain_affine(model,healthy)
        if core is not None:
            assert core<=healthy and not any(core<=state for state in states),(i,mask)
            conflicts+=1
        queries+=1
    assert explain_affine(model,{c['name'] for c in components},deadline=time.perf_counter()-1) is None
# The sum cycle fixes all q to 5; 5 cannot equal an integer square.
variables=[dict(name=n,role='wire',lb=0,ub=16 if n!='t' else 4) for n in ('q0','q1','q2','t')]
rows=[dict(kind='conditional_component',component='C'+str(i),abnormal='AB_C'+str(i),sense='eq',rhs=10,
    linear=[dict(var=a,coef=1),dict(var=b,coef=1)],quadratic=[]) for i,(a,b) in enumerate((('q0','q1'),('q1','q2'),('q0','q2')))]
rows.append(dict(kind='conditional_component',component='C3',abnormal='AB_C3',sense='eq',rhs=0,
    linear=[dict(var='q0',coef=1)],quadratic=[dict(vars=['t','t'],coef=-1)]))
model=dict(variables=variables,components=[dict(name='C'+str(i)) for i in range(4)],constraints=rows)
assert explain_affine(model,{'C0','C1','C2','C3'})==frozenset(('C0','C1','C2','C3'))
# A free affine root still cannot satisfy two squares differing by two.
variables=[dict(name=n,role='wire',lb=0,ub=16 if n.startswith('q') else 4) for n in ('q0','q1','a','b')]
rows=[dict(kind='conditional_component',component='C0',abnormal='AB_C0',sense='eq',rhs=2,
    linear=[dict(var='q0',coef=1),dict(var='q1',coef=-1)],quadratic=[])]
for i,(q,v) in enumerate((('q0','a'),('q1','b')),1):
    rows.append(dict(kind='conditional_component',component='C'+str(i),abnormal='AB_C'+str(i),sense='eq',rhs=0,
        linear=[dict(var=q,coef=1)],quadratic=[dict(vars=[v,v],coef=-1)]))
model=dict(variables=variables,components=[dict(name='C'+str(i)) for i in range(3)],constraints=rows)
assert explain_affine(model,{'C0','C1','C2'})==frozenset(('C0','C1','C2'))
rows[0]['rhs']=3
assert explain_affine(model,{'C0','C1','C2'}) is None
print(json.dumps(dict(passed=True,integer_health_queries=queries,checked_conflicts=conflicts,linear_cycle_then_square=True,deadline_unknown=True)))
