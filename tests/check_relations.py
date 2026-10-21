"""Independent finite unsigned arithmetic truth for new relation explanations."""
from pathlib import Path
import itertools,json,random,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from arithdiag.relation_conflicts import explain_relations

def model(products,upper=3):
    variables=[dict(name=n,role='wire',lb=0,ub=upper) for n in ('x','y','z')]
    rows=[];components=[]
    for i,(a,b,p) in enumerate(products):
        n='C'+str(i);components.append(dict(name=n,operation='multiply',a=a,b=b))
        rows.append(dict(kind='conditional_component',component=n,abnormal='AB_'+n,sense='eq',rhs=p,
            linear=[],quadratic=[dict(vars=[a,b],coef=1)]))
    return dict(variables=variables,components=components,constraints=rows)

cycle=[('x','y',2),('y','z',2),('z','x',2)]
assert explain_relations(model(cycle),{'C0','C1','C2'})==frozenset({'C0','C1','C2'})
assert explain_relations(model([('x','y',0),('y','z',0),('z','x',1)]),{'C0','C1','C2'}) is None
assert explain_relations(model([('x','y',6),('y','z',10),('z','x',15)],7),{'C0','C1','C2'}) is None
assert explain_relations(model(cycle),{'C0','C1','C2'},deadline=time.perf_counter()-1) is None
rng=random.Random(2026102101);queries=cores=0
for trial in range(200):
    products=[(a,b,rng.randrange(10)) for a,b in (('x','y'),('y','z'),('z','x'))]
    m=model(products)
    # A coefficient relation tests rational paths, not only +/-1 aliases.
    alpha,beta=rng.choice((1,2,3,-1)),rng.choice((1,2,-1,-2));rhs=rng.randrange(-6,13)
    m['components'].append(dict(name='C3',operation='add',a='x',b='z'))
    m['constraints'].append(dict(kind='conditional_component',component='C3',abnormal='AB_C3',sense='eq',rhs=rhs,
        linear=[dict(var='x',coef=alpha),dict(var='z',coef=beta)],quadratic=[]))
    truth=[]
    for x,y,z in itertools.product(range(4),repeat=3):
        values={'x':x,'y':y,'z':z}
        mask=sum((values[a]*values[b]==p)<<j for j,(a,b,p) in enumerate(products))
        mask|=(alpha*x+beta*z==rhs)<<3;truth.append(mask)
    for mask in range(16):
        healthy={'C'+str(j) for j in range(4) if mask>>j&1}
        core=explain_relations(m,healthy)
        if core is not None:
            bits=sum(1<<int(c[1:]) for c in core)
            assert core<=healthy and not any(state&bits==bits for state in truth),(trial,mask,core)
            cores+=1
        queries+=1
print(json.dumps(dict(passed=True,health_queries=queries,independent_conflicts=cores,
    shared_product_cycle_refuted=True,zero_factor_not_cancelled=True,expired_is_unknown=True)))
