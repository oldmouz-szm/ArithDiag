"""Independent exhaustive checks of conditional IR and delayed LS lowering."""
import ast
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'ArithDiag-LS')]
from arithdiag.preprocessing import transform,normal_equations,initial,restore
from arithdiag.validation import validate
from native_helpers import encode,local_check
from check_correctness import toy
from fixture_data import partial_bus_model

def truth(row,x):
    if row.get('ab') and x[row['ab']]: return True
    lhs=sum(k*x[n] for n,k in row['terms'].items())+sum(t['coef']*x[t['a']]*x[t['b']] for t in row['quadratic'])
    return {'eq':lhs==row['rhs'],'le':lhs<=row['rhs'],'ge':lhs>=row['rhs']}[row['sense']]

def all_values(specs):
    vs=list(specs)
    for values in itertools.product(*(range(specs[n]['lb'],specs[n]['ub']+1) for n in vs)):
        yield dict(zip(vs,values))

# No numeric transport dependency is reachable through the shared module tree.
for p in (ROOT/'src/arithdiag').glob('*.py'):
    source=p.read_text(encoding='utf-8')
    assert not any(k in source for k in ['guarded_component','guard_pos_','big_m','native_io','native_helpers']),p.name
    ast.parse(source)

checks=0
for op in ('add','multiply'):
    for same in (False,True):
        specs={n:dict(name=n,signal=n,bits=[2,0],role='wire',type='integer',lb=0,ub=3) for n in ('a','b','o')}
        specs['AB_c']=dict(name='AB_c',signal='c',role='abnormal',type='binary',lb=0,ub=1)
        row=dict(name='conditional_c',kind='conditional_component',component='c',ab='AB_c',sense='eq',rhs=0,
                 terms=({'o':1,'a':-2} if same else {'o':1,'a':-1,'b':-1}) if op=='add' else {'o':1},
                 quadratic=[] if op=='add' else [dict(a='a',b='a' if same else 'b',coef=-1)])
        pre=dict(specs=specs)
        group=dict(variables=list(specs),components=['c'],constraints=[row])
        ss,g,names=encode(pre,group)
        for x in all_values(specs):
            expected=bool(x['AB_c'] or x['o']==(2*x['a'] if same and op=='add' else
                        x['a']+x['b'] if op=='add' else x['a']*(x['a'] if same else x['b'])))
            assert truth(row,x)==expected
            assert all(truth(r,x) for r in g['constraints'])==expected
            checks+=1

# In particular, an already fixed inconsistent output forces a fault rather
# than becoming an unconditional contradiction during reduction.
fixed_cases=0
for inputs,outputs in [((1,0,1),(2,7)),((1,1,1),(4,13)),((0,0,0),(0,1))]:
    m=toy(inputs,outputs,True)
    assert all(c['kind']!='guarded_component' for c in m['constraints'])
    for structural,dominance in [(False,False),(True,False),(True,True)]:
        pre=transform(m,structural,dominance)
        g=dict(variables=sorted(pre['specs']),components=[v['signal'] for v in pre['specs'].values() if v['role']=='abnormal'],
               constraints=[c for group in pre['groups'] for c in group['constraints']])
        _,encoded,names=encode(pre,g)
        for x in all_values(pre['specs']):
            semantic=all(truth(c,x) for c in g['constraints'])
            native=all(truth(c,{names[n]:v for n,v in x.items()}) for c in encoded['constraints'])
            assert semantic==native
            if semantic: restore(pre,x)
            checks+=1
        fixed_cases+=1

# Wide domains and a nonzero constant after observation substitution.
wide=0
from native_helpers import lower_rows
for bits in (4,16,32,65):
    u=(1<<bits)-1
    specs={'x':dict(lb=0,ub=u,type='integer'),'AB_c':dict(lb=0,ub=1,type='binary')}
    row=dict(name='r',kind='conditional_component',component='c',ab='AB_c',sense='eq',rhs=u-1,terms={'x':1},quadratic=[])
    encoded=lower_rows(specs,[row])
    for v,ab in itertools.product([0,1,u-1,u],(0,1)):
        x={'x':v,'AB_c':ab}
        assert truth(row,x)==all(truth(c,x) for c in encoded)
        wide+=1

# Original functions are stored directly and remain independent of a backend.
m=partial_bus_model()
assert m['schema']=='arithdiag-semantic-model-v2'
assert all('big_m' not in c for c in m['constraints'])
assert 'gurobipy' not in sys.modules
assert validate(m,initial(m))['objective_exact']==0
assert len([c for c in normal_equations(m) if c['ab']])==len(m['components'])
print(json.dumps(dict(passed=True,semantic_vs_ls_assignments=checks,conditional_constant_cases=fixed_cases,
                     wide_boundary_assignments=wide,shared_source_backend_free=True,gurobi_used=False)))
