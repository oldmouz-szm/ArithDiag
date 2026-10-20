"""Exercise real digit/indicator compiler using a recording stub, no Gurobi SDK.

This checks emitted algebra and witnesses, not Gurobi optimization or SDK readback.
"""
import itertools,json,sys,time,types
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'ArithDiag-G'),str(R/'src')]

class Var:
    def __init__(self,i): self.index=i
    def __mul__(self,b): return ('product',self.index,b.index)
    def __eq__(self,b): return ('equal',self.index,b)

class Expr:
    def __init__(self,coefs,vs): self.terms=list(zip([v.index for v in vs],coefs));self.constant=0
    def __add__(self,n): self.constant+=n;return self

class Model:
    def __init__(self,env=None): self.variables=[];self.linear=[];self.indicators=[];self.quadratic=[]
    def addVar(self,**kw):
        v=Var(len(self.variables));self.variables.append(kw);return v
    def addLConstr(self,e,s,r): self.linear.append((e,s,r))
    def addGenConstrIndicator(self,v,on,e,s,r): self.indicators.append((v.index,on,e,s,r))
    def addQConstr(self,e): self.quadratic.append(e)
    def setObjective(self,e,s): self.objective=e
    def update(self): pass

stub=types.ModuleType('gurobipy')
stub.Model=Model;stub.LinExpr=Expr
stub.GRB=types.SimpleNamespace(BINARY='B',INTEGER='I',EQUAL='=',LESS_EQUAL='<',GREATER_EQUAL='>',MINIMIZE=1)
sys.modules['gurobipy']=stub
from limb_model import Encoding,semantic_audit

def pre(op,ub):
    specs={n:dict(name=n,lb=0,ub=ub,role='signal') for n in ('a','b','o')}
    specs['AB_c']=dict(name='AB_c',lb=0,ub=1,role='abnormal')
    row=dict(terms={'o':1,'a':-1,'b':-1} if op=='add' else {'o':1},
             quadratic=[] if op=='add' else [dict(a='a',b='b',coef=-1)],rhs=0,sense='eq',ab='AB_c')
    return dict(specs=specs,equations=[row],fixed={},groups=[])

def emitted_holds(enc,z):
    for v,kw in zip(z,enc.m.variables):
        if not kw['lb']<=v<=kw['ub']:return False
    def row(e,s,r):
        lhs=sum(z[i]*k for i,k in e.terms)+e.constant
        return {'=':lhs==r,'<':lhs<=r,'>':lhs>=r}[s]
    for e,s,r in enc.m.linear:
        if not row(e,s,r):return False
    for ab,on,e,s,r in enc.m.indicators:
        if z[ab]==int(on) and not row(e,s,r):return False
    for _,p,(_,a,b) in enc.m.quadratic:
        if z[p]!=z[a]*z[b]:return False
    return True

small=wide=0
for op in ('add','mul'):
    e=Encoding(pre(op,3),None,time.perf_counter()+30)
    assert len(e.inds)==len(e.m.indicators) and len(e.rows)==len(e.m.linear)
    for a,b,o,ab in itertools.product(range(4),range(4),range(4),range(2)):
        x=dict(a=a,b=b,o=o,AB_c=ab)
        expected=bool(ab or o==(a+b if op=='add' else a*b))
        try:
            z=e.assignment(x)
            actual=emitted_holds(e,z) and e.decode(z)==x
        except ValueError: actual=False
        assert actual==expected
        small+=1
for ab in (0,1):
    for a,b in (((1<<32)+1,(1<<32)-1),((1<<31)+3,(1<<33)-1)):
        for delta in (0,1):
            x=dict(a=a,b=b,o=a*b+delta,AB_c=ab)
            e=Encoding(pre('mul',(1<<65)-1),None,time.perf_counter()+30)
            try:
                z=e.assignment(x);actual=emitted_holds(e,z) and e.decode(z)==x
            except ValueError:actual=False
            assert actual==bool(ab or delta==0)
            wide+=1
for rhs in ((1<<64)+3,-((1<<64)+3)):
    p=pre('add',(1<<65)-1)
    p['equations'][0].update(terms={'o':1 if rhs>0 else -1},rhs=rhs,quadratic=[],ab=None)
    e=Encoding(p,None,time.perf_counter()+30)
    x=dict(a=0,b=0,o=abs(rhs),AB_c=0)
    assert emitted_holds(e,e.assignment(x)) and e.decode(e.assignment(x))==x
    wide+=1
assert sys.modules['gurobipy'] is stub
from fixture_data import partial_bus_model
from arithdiag.preprocessing import transform,initial,projected_initial
original=partial_bus_model()
semantic_audit(original)
reduced=transform(original,True,True)
e=Encoding(reduced,None,time.perf_counter()+30)
x=projected_initial(reduced,initial(original))
assert emitted_holds(e,e.assignment(x)) and e.decode(e.assignment(x))==x
print(json.dumps(dict(passed=True,small_assignments=small,wide_assignments=wide,
                     semantic_pipeline_cases=1,actual_sdk_loaded=False,optimization_calls=0,license_sessions=0)))
