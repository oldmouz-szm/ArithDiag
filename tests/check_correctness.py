#!/usr/bin/env python3
"""Brute-force semantic checks, then audits across every supplied observation."""
import sys,itertools,json,time,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from preprocess import *
from worker import local_check
def toy(inputs,outputs,bypass):
    widths={"a":1,"b":1,"c":1,"u":2,"v":3,"y":5,"alias":2}
    specs=[]
    obs=dict(zip(["a","b","c"],inputs));obs["y"]=outputs[1]
    if bypass:obs["v"]=outputs[0]
    for n,w in widths.items():
        role="input" if n in ("a","b","c") else "output" if n in obs else "wire"
        specs.append(dict(name=n,signal=n,bits=[w-1,0],role=role,type="integer",lb=obs.get(n,0),ub=obs.get(n,(1<<w)-1)))
    def ref(n):return dict(signal=n,low=0,high=widths[n]-1)
    def ex(n):return dict(parts=[dict(width=widths[n],ref=ref(n))])
    comps=[dict(name="A0",operation="add",a=ex("a"),b=ex("b"),output=ref("u")),
           dict(name="A1",operation="add",a=ex("alias"),b=ex("c"),output=ref("v")),
           dict(name="M0",operation="multiply",a=ex("u"),b=ex("v"),output=ref("y"))]
    cs=[dict(name="wire_alias",kind="wiring",target=ref("alias"),source=ex("u"),sense="eq",rhs=0,
        linear=[dict(var="alias",coef=1),dict(var="u",coef=-1)],quadratic=[])]
    for co in comps:
        n=co["name"];specs.append(dict(name="AB_"+n,signal=n,role="abnormal",type="binary",lb=0,ub=1))
        terms=[dict(var=co["output"]["signal"],coef=1)]
        aa=co["a"]["parts"][0]["ref"]["signal"];bb=co["b"]["parts"][0]["ref"]["signal"]
        q=[dict(vars=[aa,bb],coef=-1)] if co["operation"]=="multiply" else []
        if not q:terms.extend([dict(var=aa,coef=-1),dict(var=bb,coef=-1)])
        for side,sgn in [("pos",1),("neg",-1)]:
            cs.append(dict(name="guard_"+side+"_"+n,kind="guarded_component",component=n,abnormal="AB_"+n,
                sense="le",rhs=0,linear=[dict(var=t["var"],coef=sgn*t["coef"]) for t in terms]+[dict(var="AB_"+n,coef=-64)],
                quadratic=[dict(vars=t["vars"],coef=sgn*t["coef"]) for t in q]))
    return dict(variables=specs,components=comps,constraints=cs,ports=[dict(name=n,direction="input" if n in ("a","b","c") else "output") for n in obs],observed_ports=obs)
def exhaustive(model):
    vs=model["variables"];free=[v for v in vs if v["lb"]!=v["ub"]];fixed={v["name"]:v["lb"] for v in vs if v["lb"]==v["ub"]}
    for vals in itertools.product(*(range(v["lb"],v["ub"]+1) for v in free)):
        x=dict(fixed,**{v["name"]:z for v,z in zip(free,vals)})
        if validate(model,x)["valid"]:yield x
def main():
    (ROOT/"results").mkdir(exist_ok=True)
    begun=time.perf_counter();counts=dict(toy_models=0,toy_feasible_witnesses=0,conflict_soundness_checks=0,transform_checks=0)
    fixture=ROOT/"tests/fixtures/partial_bus"
    partial=load_builder().build_diagnostic_model(fixture/"netlist.v",fixture/"observations_fixture.jsonl",ROOT/"tests/fixtures/library")
    assert initial_nominal(partial)["y"]==3
    assert not cone_conflicts(partial)
    assert validate(partial,initial(partial))["objective_exact"]==0
    counts["partial_bus_regression"]=True
    rng=random.Random(76041)
    for bypass in (False,True):
        for inputs in itertools.product(range(2),repeat=3):
            for _ in range(8):
                model=toy(inputs,(rng.randrange(8),rng.randrange(32)),bypass)
                feasible=list(exhaustive(model));minimum=min(sum(x["AB_"+c["name"]] for c in model["components"]) for x in feasible)
                counts["toy_models"]+=1;counts["toy_feasible_witnesses"]+=len(feasible)
                for structural,dominance in [(False,False),(True,False),(True,True)]:
                    pre=transform(model,structural,dominance);accepted=[]
                    for x in feasible:
                        if any(x[n]!=pre["fixed"][r] for n,r in pre["rename"].items() if r in pre["fixed"]):continue
                        if any(x[n]!=x[r] for n,r in pre["rename"].items()):continue
                        reduced={r:x[r] for r in pre["specs"]}
                        for g in pre["groups"]:local_check(pre,g,{n:reduced[n] for n in g["variables"]})
                        restored,k=restore(pre,reduced);assert restored==x;accepted.append(k)
                    assert accepted and min(accepted)==minimum,(bypass,inputs,minimum)
                    counts["transform_checks"]+=1
                conflicts=cone_conflicts(model)
                for mask in range(8):
                    healthy={c["name"] for i,c in enumerate(model["components"]) if mask>>i&1}
                    if certified_conflict(model,healthy):
                        assert not any(all(x["AB_"+n]==0 for n in healthy) for x in feasible)
                    counts["conflict_soundness_checks"]+=1
                for conflict in conflicts:
                    assert all(any(x["AB_"+n] for n in conflict) for x in feasible)
                init=initial(model);assert init is not None and validate(model,init)["valid"]
    result=dict(passed=True,**counts,all_initial_candidates_exact=True,elapsed_s=time.perf_counter()-begun)
    (ROOT/"results/correctness.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))
if __name__=="__main__":main()
