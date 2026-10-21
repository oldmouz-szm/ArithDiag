"""Explained rational affine relations and cancellation of fixed shared products.

All values are exact integers/Fractions. Positive fixed products justify the
shared-factor cancellation; zero products never do. Failure/limits mean UNKNOWN.
The module returns only conflicts, never witnesses or numerical lower bounds.
"""
from collections import defaultdict,deque
from fractions import Fraction as F
import math,time
from arithdiag.preprocessing import normal_equations

METRICS=dict(relation_queries=0,relation_conflicts=0,relation_s=0.,relation_ratio_edges=0,
    relation_fixed_values=0,relation_univariate_refutations=0,relation_limit_unknown=0)
_prepared=None

class _Stopped(Exception):pass

def explain_relations(model,healthy,deadline=None,max_rounds=24):
    global _prepared
    started=time.perf_counter();METRICS['relation_queries']+=1
    healthy=frozenset(healthy)
    def check(value=None):
        if deadline is not None and time.perf_counter()>=deadline:raise _Stopped()
        if value is not None and (value.numerator.bit_length()>4096 or value.denominator.bit_length()>4096):raise _Stopped()
    def core(why):
        check();result=frozenset(why)
        if not result<=healthy:raise ValueError('Relation proof depends on relaxed health')
        METRICS['relation_conflicts']+=1
        return result
    try:
        check()
        if _prepared is None or _prepared[0] is not model:
            domains={v['name']:(v['lb'],v['ub']) for v in model['variables'] if v['role']!='abnormal'}
            _prepared=(model,domains,normal_equations(model))
        _,domains,allrows=_prepared
        rows=[r for r in allrows if r.get('ab') is None or r['ab'][3:] in healthy]
        known={n:(lo,frozenset()) for n,(lo,hi) in domains.items() if lo==hi}
        for _ in range(max_rounds):
            check();changed=False;simplified=[];linearrows=[];products=defaultdict(list)
            for raw in rows:
                check();why=set() if raw.get('ab') is None else {raw['ab'][3:]}
                rhs=raw['rhs'];lin=defaultdict(int);quad=defaultdict(int)
                for term in raw['linear']:
                    n,k=term['var'],term['coef']
                    if n in known:rhs-=k*known[n][0];why.update(known[n][1])
                    else:lin[n]+=k
                for term in raw['quadratic']:
                    a,b=term['vars'];k=term['coef']
                    if a in known and b in known:
                        rhs-=k*known[a][0]*known[b][0];why.update(known[a][1]);why.update(known[b][1])
                    elif a in known:lin[b]+=k*known[a][0];why.update(known[a][1])
                    elif b in known:lin[a]+=k*known[b][0];why.update(known[b][1])
                    else:quad[tuple(sorted((a,b)))]+=k
                lin={n:k for n,k in lin.items() if k};quad={p:k for p,k in quad.items() if k};why=frozenset(why)
                divisor=0
                for k in (*lin.values(),*quad.values()):divisor=math.gcd(divisor,abs(k))
                if divisor and rhs%divisor:return core(why)
                if not divisor:
                    if rhs:return core(why)
                    continue
                simplified.append((lin,quad,rhs,why))
                if not quad:linearrows.append((lin,rhs,why))
                elif not lin and len(quad)==1:
                    ((a,b),k),=quad.items()
                    if rhs%k:return core(why)
                    value=rhs//k
                    if value>0:
                        products[a].append((b,value,why))
                        if b!=a:products[b].append((a,value,why))
            # (u*v=P) & (u*w=Q), P,Q>0 -> Q*v-P*w=0.
            for incident in products.values():
                if len(incident)<2:continue
                a,p,first=incident[0]
                for b,q,second in incident[1:]:
                    check();lin=defaultdict(int);lin[a]+=q;lin[b]-=p
                    linearrows.append(({n:k for n,k in lin.items() if k},0,first|second))
                    METRICS['relation_ratio_edges']+=1
            graph=defaultdict(list)
            for lin,rhs,why in linearrows:
                check()
                if not lin:
                    if rhs:return core(why)
                elif len(lin)==1:
                    (n,k),=lin.items()
                    if rhs%k:return core(why)
                    value=rhs//k;lo,hi=domains[n]
                    if not lo<=value<=hi:return core(why)
                    if n in known and known[n][0]!=value:return core(why|known[n][1])
                    if n not in known:known[n]=(value,why);changed=True;METRICS['relation_fixed_values']+=1
                elif len(lin)==2:
                    (a,ka),(b,kb)=lin.items()
                    graph[b].append((a,F(-kb,ka),F(rhs,ka),why))
                    graph[a].append((b,F(-ka,kb),F(rhs,kb),why))
            if changed:continue
            representation={};groups={};root_bounds={};root_reasons={};fixed_roots={}
            for root in domains:
                if root in known or root in representation:continue
                check();representation[root]=(root,F(1),F(0),frozenset())
                queue=deque((root,));nodes=[];low=high=None;boundwhy=frozenset()
                fixed=None;fixedwhy=frozenset()
                while queue:
                    check();node=queue.popleft();nodes.append(node)
                    _,alpha,beta,path=representation[node]
                    lo,hi=domains[node]
                    rlo,rhi=(F(lo)-beta)/alpha,(F(hi)-beta)/alpha
                    if alpha<0:rlo,rhi=rhi,rlo
                    rlo,rhi=math.ceil(rlo),math.floor(rhi)
                    low=rlo if low is None else max(low,rlo);high=rhi if high is None else min(high,rhi)
                    boundwhy=boundwhy|path
                    if low>high:return core(boundwhy|fixedwhy)
                    for other,a,b,edge in graph[node]:
                        candidate_alpha=a*alpha;candidate_beta=a*beta+b
                        check(candidate_alpha);check(candidate_beta);why=path|edge
                        if other not in representation:
                            representation[other]=(root,candidate_alpha,candidate_beta,why);queue.append(other);continue
                        oldroot,oldalpha,oldbeta,oldwhy=representation[other]
                        if oldroot!=root:raise ValueError('Affine graph component mismatch')
                        coef=candidate_alpha-oldalpha;rhs=oldbeta-candidate_beta;why=why|oldwhy
                        if not coef:
                            if rhs:return core(why)
                        else:
                            value=rhs/coef
                            if value.denominator!=1:return core(why)
                            value=int(value)
                            if fixed is not None and value!=fixed:return core(why|fixedwhy)
                            fixed=value;fixedwhy=fixedwhy|why
                groups[root]=nodes;root_bounds[root]=(low,high);root_reasons[root]=boundwhy
                if fixed is None and low==high:fixed=low;fixedwhy=boundwhy
                if fixed is not None:fixed_roots[root]=({fixed},fixedwhy|boundwhy)
            candidates=dict(fixed_roots)
            for lin,quad,rhs,why in simplified:
                check();poly=defaultdict(F);poly[()]-=rhs;reason=why
                for n,k in lin.items():
                    root,a,b,path=representation[n];reason=reason|path
                    poly[(root,)]+=k*a;poly[()]+=k*b
                for (n,m),k in quad.items():
                    r,a,b,path=representation[n];s,c,d,other=representation[m];reason=reason|path|other
                    poly[tuple(sorted((r,s)))]+=k*a*c
                    poly[(r,)]+=k*a*d;poly[(s,)]+=k*b*c;poly[()]+=k*b*d
                poly={ns:k for ns,k in poly.items() if k}
                roots={n for ns in poly for n in ns}
                if not roots:
                    if poly.get((),0):return core(reason)
                    continue
                if len(roots)!=1:continue
                root=next(iter(roots));den=1
                for k in poly.values():check(k);den=math.lcm(den,k.denominator)
                a=int(poly.get((root,root),0)*den);b=int(poly.get((root,),0)*den);c=int(poly.get((),0)*den)
                values=set()
                if a:
                    disc=b*b-4*a*c
                    if disc>=0:
                        sq=math.isqrt(disc)
                        if sq*sq==disc:
                            for numerator in (-b-sq,-b+sq):
                                if numerator%(2*a)==0:values.add(numerator//(2*a))
                elif b and (-c)%b==0:values.add((-c)//b)
                lo,hi=root_bounds[root];values={v for v in values if lo<=v<=hi}
                reason=reason|root_reasons[root]
                if root in candidates:
                    previous,oldwhy=candidates[root];values&=previous;reason=reason|oldwhy
                candidates[root]=(values,reason)
            for root,(values,why) in candidates.items():
                check();valid=set()
                for value in values:
                    if not root_bounds[root][0]<=value<=root_bounds[root][1]:continue
                    okay=True
                    for node in groups[root]:
                        _,a,b,path=representation[node];v=a*value+b;lo,hi=domains[node]
                        why=why|path
                        if v.denominator!=1 or not lo<=v<=hi:okay=False;break
                    if okay:valid.add(value)
                if not valid:
                    METRICS['relation_univariate_refutations']+=1
                    return core(why|root_reasons[root])
                if len(valid)==1:
                    value=next(iter(valid))
                    for node in groups[root]:
                        _,a,b,path=representation[node];v=int(a*value+b)
                        if node not in known:known[node]=(v,why|path|root_reasons[root]);changed=True;METRICS['relation_fixed_values']+=1
            if not changed:break
        return None
    except _Stopped:
        METRICS['relation_limit_unknown']+=1
        return None
    finally:METRICS['relation_s']+=time.perf_counter()-started
