#!/usr/bin/env python3
"""Brute-force semantic checks, then audits across every supplied observation."""
import sys,itertools,json,time,random,tempfile
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

def check_builder_aliases():
    """Compare normalized polynomials with independent whole-signal arithmetic.

    Enumerate polynomial feasibility separately from the original-signal checker,
    so an incorrect normalization cannot be hidden by the final validator.
    """
    counts=dict(builder_alias_cases=0,builder_alias_feasible_witnesses=0,
                builder_alias_contradictions=0,builder_alias_transform_checks=0)
    with tempfile.TemporaryDirectory(prefix="alias-builder-",dir=ROOT/"results") as directory:
        base=Path(directory);library=base/"library";library.mkdir()
        # Interface fixtures exercise the integer frontend, not gate synthesis.
        (library/"u_rca8.v").write_text("module u_rca8(input [7:0] a, input [7:0] b, output [8:0] u_rca8_out);\nendmodule\n")
        (library/"u_arrmul4.v").write_text("module u_arrmul4(input [3:0] a, input [3:0] b, output [7:0] u_arrmul4_out);\nendmodule\n")
        def build(name,ports,body,inputs,outputs):
            case=base/name;case.mkdir(exist_ok=True)
            top=case/"netlist.v";top.write_text("module test("+ports+");\n"+body+"\nendmodule\n")
            obs=case/"observations_001.jsonl"
            obs.write_text("# "+json.dumps(dict(circuit=name))+"\n"+json.dumps(dict(inputs={k:hex(v) for k,v in inputs.items()},outputs={k:hex(v) for k,v in outputs.items()}))+"\n")
            return load_builder().build_diagnostic_model(top,obs,library)
        def check(model,signal,expected):
            free=[v for v in model["variables"] if v["lb"]!=v["ub"]]
            fixed={v["name"]:v["lb"] for v in model["variables"] if v["lb"]==v["ub"]}
            observed=set();feasible=[];ab="AB_"+model["components"][0]["name"]
            for values in itertools.product(*(range(v["lb"],v["ub"]+1) for v in free)):
                x=dict(fixed,**{v["name"]:value for v,value in zip(free,values)})
                def row(c):
                    lhs=sum(t["coef"]*x[t["var"]] for t in c["linear"])+sum(t["coef"]*x[t["vars"][0]]*x[t["vars"][1]] for t in c["quadratic"])
                    return {"eq":lhs==c["rhs"],"le":lhs<=c["rhs"],"ge":lhs>=c["rhs"]}[c["sense"]]
                if not all(row(c) for c in model["constraints"]):continue
                original=sum(x[s["name"]]<<s["low"] for s in signal_layout(model)[signal])
                observed.add((original,x[ab]));feasible.append(x)
                assert validate(model,x)["valid"]
            assert observed==expected,(model["circuit"],len(observed),len(expected))
            assert len(feasible)==len(expected),"Shared variables must not add witness multiplicity"
            assert model["normalization"]["aliases_merged"]>0
            assert len([v for v in model["variables"] if v["role"]=="abnormal"])==len(model["components"])
            for structural,dominance in ((False,False),(True,False),(True,True)):
                pre=transform(model,structural,dominance)
                assert all(n==r for n,r in pre["rename"].items()),"No downstream alias elimination"
                for x in feasible:
                    values={n:x[n] for n in pre["specs"]}
                    restored,_=restore(pre,values);assert restored==x
                counts["builder_alias_transform_checks"]+=1
            candidate=initial(model);assert candidate is not None and validate(model,candidate)["valid"]
            for conflict in cone_conflicts(model):
                assert all(any(x["AB_"+c] for c in conflict) for x in feasible)
            counts["builder_alias_cases"]+=1
            counts["builder_alias_feasible_witnesses"]+=len(feasible)
        def reject(*args):
            try:build(*args)
            except ValueError as exc:
                assert "connection" in str(exc),exc
                counts["builder_alias_contradictions"]+=1
            else:raise AssertionError("Contradictory aliased observations accepted")
        ports="input [7:0] a, input [7:0] b, output [1:0] y, output [1:0] z"
        body="""wire [8:0] u;
wire [8:0] t;
wire [8:0] r;
assign t = u;
assign r = t;
assign y = r[1:0];
assign z = {r[0], r[0]};
u_rca8 A0 (.a(a), .b(b), .u_rca8_out(u));"""
        for y,z in ((3,3),(2,0)):
            model=build("chain"+str(y),ports,body,dict(a=1,b=2),dict(y=y,z=z))
            check(model,"u",{(u,ab) for u in range(512) for ab in (0,1) if u%4==y and (u%2)*3==z and (ab or u==3)})
            assert all(c["kind"]!="wiring" for c in model["constraints"])
        reject("bad_duplicate",ports,body,dict(a=1,b=2),dict(y=3,z=1))
        ports="input [7:0] a, input [7:0] b, output [8:0] y, output [7:0] z"
        body="""wire [8:0] u;
assign y = u;
assign z = {7'b0, u[0]};
u_rca8 A0 (.a(a), .b(b), .u_rca8_out(u));"""
        for y,z in ((3,1),(2,0)):
            check(build("zero"+str(y),ports,body,dict(a=1,b=2),dict(y=y,z=z)),"u",{(y,ab) for ab in (0,1) if ab or y==3})
        reject("bad_zero",ports,body,dict(a=1,b=2),dict(y=2,z=2))
        reject("bad_shared_output",ports,body,dict(a=1,b=2),dict(y=2,z=1))
        # The lexicographic representative of input z is output a, exercising
        # reconstruction and nominal evaluation independently of variable roles.
        ports="input [7:0] z, input [7:0] b, output [7:0] a, output [8:0] y"
        body="""wire [7:0] t;
wire [8:0] u;
assign t = z;
assign a = t;
assign y = u;
u_rca8 A0 (.a(t), .b(b), .u_rca8_out(u));"""
        for y in (3,7):
            check(build("input_alias"+str(y),ports,body,dict(z=1,b=2),dict(a=1,y=y)),"u",{(y,ab) for ab in (0,1) if ab or y==3})
        reject("bad_input_alias",ports,body,dict(z=1,b=2),dict(a=2,y=3))
        ports="input [0:0] a, output [7:0] y"
        body="""wire [3:0] t;
assign t = {a, a, a, a};
u_arrmul4 M0 (.a(t), .b(t), .u_arrmul4_out(y));"""
        for y in (225,224):
            model=build("repeated"+str(y),ports,body,dict(a=1),dict(y=y))
            check(model,"y",{(y,ab) for ab in (0,1) if ab or y==225})
            healthy=next(c for c in model["constraints"] if c["name"]=="guard_pos_M0")
            assert healthy["quadratic"]==[dict(vars=["a","a"],coef=-225)]
    return counts

def main():
    (ROOT/"results").mkdir(exist_ok=True)
    begun=time.perf_counter();counts=dict(toy_models=0,toy_feasible_witnesses=0,conflict_soundness_checks=0,transform_checks=0)
    counts.update(check_builder_aliases())
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
