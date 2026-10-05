from collections import defaultdict
def split_nonlinear(model):
    fixed={v["name"]:v["lb"] for v in model["variables"] if v["lb"]==v["ub"]}
    specs={v["name"]:v for v in model["variables"] if v["name"] not in fixed}
    parent={n:n for n in specs}
    def find(n):
        while parent[n]!=n:
            parent[n]=parent[parent[n]];n=parent[n]
        return n
    residual=[]
    for c in model["constraints"]:
        constant=0
        terms=defaultdict(int)
        quad=defaultdict(int)
        for t in c["linear"]:
            n,coef=t["var"],t["coef"]
            if n in fixed:constant+=coef*fixed[n]
            else:terms[n]+=coef
        for t in c["quadratic"]:
            a,b=t["vars"];coef=t["coef"]
            if a in fixed and b in fixed:constant+=coef*fixed[a]*fixed[b]
            elif a in fixed:terms[b]+=coef*fixed[a]
            elif b in fixed:terms[a]+=coef*fixed[b]
            else:quad[tuple(sorted((a,b)))]+=coef
        terms={n:v for n,v in terms.items() if v}
        quadratic=[dict(a=a,b=b,coef=v) for (a,b),v in sorted(quad.items()) if v]
        rhs=c["rhs"]-constant
        names=set(terms)|{n for t in quadratic for n in (t["a"],t["b"])}
        if not names:
            if not {"eq":0==rhs,"le":0<=rhs,"ge":0>=rhs}[c["sense"]]:
                raise ValueError("Infeasible constant constraint")
            continue
        names=sorted(names)
        for n in names[1:]:parent[find(n)]=find(names[0])
        residual.append(dict(name=c["name"],terms=terms,quadratic=quadratic,sense=c["sense"],rhs=rhs))
    groups=defaultdict(lambda:dict(variables=[],constraints=[]))
    for n in specs:groups[find(n)]["variables"].append(n)
    for c in residual:
        names=set(c["terms"])|{n for t in c["quadratic"] for n in (t["a"],t["b"])}
        roots={find(n) for n in names}
        assert len(roots)==1
        groups[next(iter(roots))]["constraints"].append(c)
    factors=sorted(groups.values(),key=lambda g:min(g["variables"]))
    for i,g in enumerate(factors):
        g["id"]=i;g["variables"].sort()
        g["components"]=sorted(specs[n]["signal"] for n in g["variables"] if specs[n]["role"]=="abnormal")
    return fixed,specs,factors

def unused_legacy_prepare(circuit,observation):
    b=load_builder()
    model=b.build_diagnostic_model(DATA/"source/cases"/circuit/"netlist.v",
        DATA/"observations"/circuit/(observation.replace("observations_","gate_observations_")+".jsonl"),
        DATA/"source/library")
    return (model,*split_nonlinear(model))

def verify_group(group,values):
    if set(values)!=set(group["variables"]):raise ValueError("Missing nonlinear factor variables")
    for c in group["constraints"]:
        if c.get("conditional_ab") and values[c["conditional_ab"]]:continue
        lhs=sum(a*values[n] for n,a in c["terms"].items())
        lhs+=sum(t["coef"]*values[t["a"]]*values[t["b"]] for t in c.get("quadratic",[]))
        if not {"eq":lhs==c["rhs"],"le":lhs<=c["rhs"],"ge":lhs>=c["rhs"]}[c["sense"]]:
            raise ValueError("Exact nonlinear check failed: "+c["name"])

def residual_stats(groups):
    qs=[t for g in groups for c in g["constraints"] for t in c["quadratic"]]
    return dict(residual_quadratic_terms=len(qs),
        distinct_unknown_products=len({tuple(sorted((t["a"],t["b"]))) for t in qs}),
        all_quadratic_factors_fixed=not qs)
