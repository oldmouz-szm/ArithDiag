"""Exact signed-affine equalities and univariate integer contradictions.

Every inferred value carries a union of healthy assumptions. Graph paths use
x=+/-r+d; cycles may determine r exactly. Bounds and integer square roots can
refute such a component. No choice of an unfixed root is a proof or a witness.
"""
from collections import defaultdict,deque
import math,time
from arithdiag.preprocessing import normal_equations

METRICS=dict(affine_queries=0,affine_conflicts=0,affine_s=0.0,affine_fixed_values=0,affine_square_enumerations=0,affine_square_values=0,affine_square_refutations=0)

def explain_affine(model,healthy,deadline=None,max_rounds=24):
    started=time.perf_counter();METRICS['affine_queries']+=1
    healthy=frozenset(healthy)
    def expired():return deadline is not None and time.perf_counter()>=deadline
    def conflict(support):
        if expired():return None
        core=frozenset(support)
        if not core<=healthy:raise ValueError('Affine conflict depends on relaxed health')
        METRICS['affine_conflicts']+=1
        return core
    try:
        if expired():return None
        domains={v['name']:(v['lb'],v['ub']) for v in model['variables'] if v['role']!='abnormal'}
        known={n:(lo,frozenset()) for n,(lo,hi) in domains.items() if lo==hi}
        equations=[row for row in normal_equations(model) if row.get('ab') is None or row['ab'][3:] in healthy]
        for _ in range(max_rounds):
            changed=False;graph=defaultdict(list);squares=[]
            for raw in equations:
                if expired():return None
                why=set() if raw.get('ab') is None else {raw['ab'][3:]}
                rhs=raw['rhs'];lin=defaultdict(int);quad=defaultdict(int)
                for term in raw['linear']:
                    n=term['var'];k=term['coef']
                    if n in known:
                        value,support=known[n];rhs-=k*value;why.update(support)
                    else:lin[n]+=k
                for term in raw['quadratic']:
                    a,b=term['vars'];k=term['coef']
                    if a in known and b in known:
                        rhs-=k*known[a][0]*known[b][0];why.update(known[a][1]);why.update(known[b][1])
                    elif a in known:lin[b]+=k*known[a][0];why.update(known[a][1])
                    elif b in known:lin[a]+=k*known[b][0];why.update(known[b][1])
                    else:quad[tuple(sorted((a,b)))]+=k
                lin={n:k for n,k in lin.items() if k};quad={p:k for p,k in quad.items() if k}
                names=set(lin)|{n for pair in quad for n in pair}
                divisor=0
                for k in (*lin.values(),*quad.values()):divisor=math.gcd(divisor,abs(k))
                if not divisor:
                    if rhs:return conflict(why)
                    continue
                if rhs%divisor:return conflict(why)
                rhs//=divisor;lin={n:k//divisor for n,k in lin.items()};quad={p:k//divisor for p,k in quad.items()}
                support=frozenset(why)
                if len(lin)==1 and len(quad)==1:
                    (out,coefficient),=lin.items();((a,b),product),=quad.items()
                    if a==b and out!=a:
                        squares.append((out,a,coefficient,product,rhs,support))
                if len(names)==1:
                    n=next(iter(names));a=quad.get((n,n),0);b=lin.get(n,0);c=-rhs
                    roots=set()
                    if a:
                        discriminant=b*b-4*a*c
                        if discriminant>=0:
                            root=math.isqrt(discriminant)
                            if root*root==discriminant:
                                for numerator in (-b-root,-b+root):
                                    if numerator%(2*a)==0:roots.add(numerator//(2*a))
                    elif b and (-c)%b==0:roots.add((-c)//b)
                    lo,hi=domains[n];roots={value for value in roots if lo<=value<=hi}
                    if not roots:return conflict(support)
                    if len(roots)==1:
                        value=next(iter(roots))
                        if n in known and known[n][0]!=value:return conflict(support|known[n][1])
                        if n not in known:known[n]=(value,support);changed=True;METRICS['affine_fixed_values']+=1
                elif not quad and len(lin)==2 and all(abs(k)==1 for k in lin.values()):
                    (a,ka),(b,kb)=lin.items()
                    # ka*a+kb*b=rhs -> a=(-ka*kb)*b+ka*rhs.
                    sign=-ka*kb;offset=ka*rhs
                    graph[b].append((a,sign,offset,support))
                    graph[a].append((b,sign,-sign*offset,support))
            # Newly fixed values can simplify an earlier row on the next pass.
            if changed:continue
            visited=set()
            for root in graph:
                if root in visited:continue
                representation={root:(1,0,frozenset())};queue=deque((root,));root_value=None;root_support=frozenset()
                low=high=None;range_support=frozenset()
                while queue:
                    if expired():return None
                    node=queue.popleft();visited.add(node);sign,offset,path=representation[node]
                    lo,hi=domains[node]
                    if node in known:
                        lo=hi=known[node][0];path=path|known[node][1]
                    rlo,rhi=(lo-offset,hi-offset) if sign==1 else (offset-hi,offset-lo)
                    low=rlo if low is None else max(low,rlo);high=rhi if high is None else min(high,rhi)
                    range_support=range_support|path
                    if low>high:return conflict(range_support|root_support)
                    for other,s,d,edge in graph[node]:
                        candidate=(s*sign,s*offset+d,path|edge)
                        if other not in representation:
                            representation[other]=candidate;queue.append(other);continue
                        old_sign,old_offset,old_path=representation[other]
                        coefficient=candidate[0]-old_sign;constant=old_offset-candidate[1]
                        reason=candidate[2]|old_path
                        if not coefficient:
                            if constant:return conflict(reason)
                        elif constant%coefficient:return conflict(reason)
                        else:
                            value=constant//coefficient
                            if root_value is not None and root_value!=value:return conflict(reason|root_support)
                            root_value=value;root_support=root_support|reason
                if root_value is None and low==high:root_value=low;root_support=range_support
                if root_value is None:
                    relevant=[row for row in squares if row[0] in representation]
                    bounded=[row for row in relevant if domains[row[1]][1]-domains[row[1]][0]+1<=4096]
                    if bounded:
                        selected=min(bounded,key=lambda row:domains[row[1]][1]-domains[row[1]][0])
                        out,factor,coefficient,product,rhs,why=selected
                        sign,offset,path=representation[out]
                        reason=range_support
                        for square in relevant:reason=reason|square[5]|representation[square[0]][2]
                        candidates=set();METRICS['affine_square_enumerations']+=1
                        for value in range(domains[factor][0],domains[factor][1]+1):
                            if expired():return None
                            METRICS['affine_square_values']+=1
                            numerator=rhs-product*value*value
                            if numerator%coefficient:continue
                            candidate=sign*(numerator//coefficient-offset)
                            if not low<=candidate<=high:continue
                            compatible=True
                            for q,v,k,c,b,support in relevant:
                                sqsign,sqoffset,_=representation[q]
                                numerator=b-k*(sqsign*candidate+sqoffset)
                                if numerator%c:
                                    compatible=False;break
                                square_value=numerator//c
                                if square_value<0:
                                    compatible=False;break
                                root_factor=math.isqrt(square_value)
                                lo,hi=domains[v]
                                if root_factor*root_factor!=square_value or not (lo<=root_factor<=hi or lo<=-root_factor<=hi):
                                    compatible=False;break
                                if v in representation:
                                    vsign,voffset,_=representation[v]
                                    if (vsign*candidate+voffset)**2!=square_value:
                                        compatible=False;break
                            if compatible:candidates.add(candidate)
                        # No proof or unique-root inference is made from a prefix.
                        if expired():return None
                        if not candidates:
                            METRICS['affine_square_refutations']+=1
                            return conflict(reason)
                        if len(candidates)==1:root_value=next(iter(candidates));root_support=reason
                if root_value is not None:
                    if not low<=root_value<=high:return conflict(root_support|range_support)
                    for node,(sign,offset,path) in representation.items():
                        value=sign*root_value+offset;reason=root_support|path|range_support
                        if node in known and known[node][0]!=value:return conflict(reason|known[node][1])
                        if node not in known:known[node]=(value,reason);changed=True;METRICS['affine_fixed_values']+=1
            if not changed:break
        return None
    finally:METRICS['affine_s']+=time.perf_counter()-started
