#!/usr/bin/env python3
"""One budget; transient witnesses; exact original-circuit validation."""
import os,sys,time,resource,json,subprocess,select,signal,tempfile,traceback
from pathlib import Path
from decimal import Decimal
sys.dont_write_bytecode=True
START=float(os.environ.get("MBD_PROCESS_START_TICK",time.perf_counter()))
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
os.nice(10);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
from model_io import ROOT,render,audit,exact_int
from preprocess import load,transform,restore,initial,projected_initial,cone_conflicts,learn_conflicts,add_conflicts,conflict_bound,certified_conflict

CONFIGS={
"baseline":dict(structural=False,dominance=False,initial=False,restarts=False,semantic=False,conflicts=False),
"structure":dict(structural=True,dominance=True,initial=False,restarts=False,semantic=False,conflicts=False),
"restart":dict(structural=True,dominance=True,initial=True,restarts=True,semantic=False,conflicts=False),
"semantic":dict(structural=True,dominance=True,initial=True,restarts=True,semantic=True,conflicts=False),
"full":dict(structural=True,dominance=True,initial=True,restarts=True,semantic=True,conflicts=True),
}
def encode(pre,group):
    names={n:n if ":" not in n else "arithdiag_v_"+str(i) for i,n in enumerate(group["variables"])}
    specs={names[n]:dict(pre["specs"][n],name=names[n]) for n in group["variables"]}
    g=dict(group,variables=list(specs),constraints=[])
    for c in group["constraints"]:
        g["constraints"].append(dict(c,terms={names[n]:a for n,a in c["terms"].items()},
            quadratic=[dict(t,a=names[t["a"]],b=names[t["b"]]) for t in c.get("quadratic",[])]))
    return specs,g,names
def metadata(pre,group,names,seed,moves):
    rows=["MODE "+str(int(moves))]
    if seed:
        rows += ["I "+names[n]+" "+str(seed[n]) for n in group["variables"]]
    active=set(group["variables"])
    for e in pre["equations"]:
        ns=set(e["terms"])|{n for t in e["quadratic"] for n in (t["a"],t["b"])}
        if not ns<=active:continue
        if e["ab"] and e["ab"] not in active:continue
        terms=[(a,[names[n]]) for n,a in e["terms"].items()]+[(t["coef"],[names[t["a"]],names[t["b"]]]) for t in e["quadratic"]]
        rows.append("E "+(names[e["ab"]] if e["ab"] else "-")+" "+str(e["rhs"])+" "+str(len(terms))+" "+
            " ".join(str(a)+" "+str(len(ns))+" "+" ".join(ns) for a,ns in terms))
    return ("\n".join(rows)+"\n").encode()
def local_check(pre,g,values):
    if set(values)!=set(g["variables"]):raise ValueError("Candidate variable mismatch")
    for n,x in values.items():
        if not pre["specs"][n]["lb"]<=x<=pre["specs"][n]["ub"]:raise ValueError("Candidate domain")
    for c in g["constraints"]:
        lhs=sum(a*values[n] for n,a in c["terms"].items())+sum(t["coef"]*values[t["a"]]*values[t["b"]] for t in c["quadratic"])
        if not {"eq":lhs==c["rhs"],"le":lhs<=c["rhs"],"ge":lhs>=c["rhs"]}[c["sense"]]:raise ValueError("Candidate exact row: "+c["name"])
    return sum(values["AB_"+c] for c in g["components"])
def run():
    method,dataset,case,obs,limit,seed,goal,target=sys.argv[1:]
    limit=float(limit);seed=int(seed);goal=None if goal=="none" else int(goal);target=Path(target);cfg=CONFIGS[method]
    deadline=START+limit;trace=[];best={};ks={};rounds=[];pre=None;conflicts=[];audits=[]
    result=dict(schema="arithdiag-v1",method=method,instance_id="/".join([case,obs]),seed=seed,
        configuration=cfg,threads=1,time_limit_s=limit,has_verified_feasible=False,best_cardinality=None,
        trace=trace,full_diagnosis_export=False,enumeration_complete=False,own_optimality_certificate=False,
        external_reference_minimum=goal,invalid_candidate_count=0,termination="budget_exhausted",rounds=rounds,
        native_component_attempts=0,native_component_accepted=0,native_invocations=0)
    def publish():
        result["total_s"]=time.perf_counter()-START
        target.with_suffix(".progress.json").write_text(json.dumps(result,indent=2)+"\n")
    def record(kind):
        if len(best)!=len(pre["groups"]):return False
        vals={n:v for group_values in best.values() for n,v in group_values.items()}
        _,k=restore(pre,vals)
        now=time.perf_counter()-START
        if result["best_cardinality"] is None or k<result["best_cardinality"]:
            if not result["has_verified_feasible"]:result["first_feasible_total_s"]=now
            result.update(has_verified_feasible=True,best_cardinality=k,best_total_s=now)
            trace.append(dict(total_s=now,cardinality=k,origin=kind))
            if goal is not None and k==goal:result["target_time_s"]=now
            if goal is not None and k<goal:raise ValueError("Contradicts independently certified reference")
            result["own_optimality_certificate"]=(k==result.get("lower_bound",0))
            publish()
        if k==result.get("lower_bound",0):result["own_optimality_certificate"]=True;result.setdefault("optimality_certificate_total_s",time.perf_counter()-START);result["termination"]="certified_bounds_match";publish();return True
        if goal is not None and k==goal:result["termination"]="external_target_reached";return True
        return False
    try:
        tick=time.perf_counter();model=load(dataset,case,obs);pre=transform(model,cfg["structural"],cfg["dominance"])
        if method=="baseline":
            pre["groups"]=[dict(id=0,variables=sorted(pre["specs"]),
                components=sorted(c for g in pre["groups"] for c in g["components"]),
                constraints=[c for g in pre["groups"] for c in g["constraints"]])]
        result.update(pre["stats"]);result["preprocessing_s"]=time.perf_counter()-tick
        if cfg["structural"]:
            tick=time.perf_counter()
            if cfg["conflicts"]:conflicts,result["conflict_oracle_checks"]=learn_conflicts(model,min(deadline,time.perf_counter()+.35))
            else:conflicts=cone_conflicts(model)
            result["conflict_analysis_s"]=time.perf_counter()-tick
        result["lower_bound"]=conflict_bound(conflicts)
        if cfg["conflicts"]:result["conflict_constraints_added"]=add_conflicts(pre,conflicts)
        result["certified_conflicts"]=len(conflicts)
        result["generated_variables"]=len(pre["specs"])
        result["constraints"]=sum(len(g["constraints"]) for g in pre["groups"])
        result["max_resident_group_variables"]=max((len(g["variables"]) for g in pre["groups"]),default=0)
        result["conflict_learning_events"]=0
        publish()
        full_init=None;init=None
        if cfg["initial"]:
            tick=time.perf_counter();full_init=initial(model);init=projected_initial(pre,full_init)
            result["initialisation_s"]=time.perf_counter()-tick
            if init:
                for g in pre["groups"]:best[g["id"]]={n:init[n] for n in g["variables"]};ks[g["id"]]=local_check(pre,g,best[g["id"]])
        # No LS needed if all free variables are ABs and every function is constant.
        if cfg["structural"] and all(v["role"]=="abnormal" for v in pre["specs"].values()):
            direct={n:0 for n in pre["specs"]}
            for e in pre["equations"]:
                if e["terms"] or e["quadratic"]:raise ValueError("Unexpected residual arithmetic")
                if e["ab"]:direct[e["ab"]]=int(e["rhs"]!=0)
                elif e["rhs"]:raise ValueError("Constant unconditional inconsistency")
            for g in pre["groups"]:best[g["id"]]={n:direct[n] for n in g["variables"]};ks[g["id"]]=local_check(pre,g,best[g["id"]])
            _,k=restore(pre,direct);result["lower_bound"]=k
            record("constant_function_preprocessing");result["termination"]="certified_constant_functions"
            result["native_invocations"]=0
        elif record("circuit_initialisation"):pass
        else:
            native=ROOT/("native/ls-iqcqp/build/LS-IQCQP" if cfg["initial"] or cfg["semantic"] else "baseline/native/build/LS-IQCQP")
            calls=0
            with tempfile.TemporaryDirectory(prefix="arithdiag-",dir=ROOT/"results") as tmp:
                tmp=Path(tmp)
                for gi,g in enumerate(pre["groups"]):
                    # Certified cone bounds restricted only after fixed AB=0 reductions.
                    local_conflicts=[]
                    for cs in conflicts:
                        rs={pre["rename"]["AB_"+c] for c in cs}
                        if any(pre["fixed"].get(n)==1 for n in rs):continue
                        free={n for n in rs if n not in pre["fixed"]}
                        if free and free<=set(g["variables"]):local_conflicts.append(frozenset(free))
                    lb=conflict_bound(local_conflicts)
                    if ks.get(g["id"])==lb:continue
                    allot=max(0.,deadline-time.perf_counter())/(len(pre["groups"])-gi)
                    group_end=min(deadline,time.perf_counter()+allot);ri=0
                    while time.perf_counter()<group_end-.02:
                        ri+=1;calls+=1
                        specs,encoded,names=encode(pre,g);reverse={v:k for k,v in names.items()}
                        lp=tmp/("g"+str(gi)+".lp");lp.write_text(render(specs,encoded),newline="\n")
                        if ri==1:
                            tick=time.perf_counter()
                            aa=subprocess.run([str(native),"--audit",str(lp)],capture_output=True,text=True,timeout=max(.02,deadline-time.perf_counter()))
                            if aa.returncode:raise ValueError("Native audit failed")
                            a=audit(specs,encoded,json.loads(aa.stdout));audits.append(a)
                            if not a["mathematically_equivalent_input"]:raise ValueError("Native input is not equivalent")
                            result["input_audit_s"]=result.get("input_audit_s",0)+time.perf_counter()-tick
                        remain=group_end-time.perf_counter()
                        if remain<=.02:break
                        duration=min(remain,5*(1+min(ri-1,2))) if cfg["restarts"] else remain
                        fd=None;fds=()
                        cmd=[str(native),str(duration),"1",str(lp),str(seed+104729*(ri-1)+gi),"1"]
                        if cfg["initial"] or cfg["semantic"]:
                            fd=os.memfd_create("arithdiag-transient-metadata",0);os.write(fd,metadata(pre,g,names,best.get(g["id"]),cfg["semantic"]));os.lseek(fd,0,0)
                            cmd.append("/proc/self/fd/"+str(fd));fds=(fd,)
                        tick=time.perf_counter();last_improved=tick;end=tick+duration
                        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,pass_fds=fds,bufsize=0)
                        result["native_invocations"]=calls
                        pending=b"";why="round_deadline";stop=False;native_attempts=0;native_accepted=0
                        try:
                            while time.perf_counter()<min(end,group_end,deadline):
                                if cfg["restarts"] and time.perf_counter()-last_improved>=3.0:why="stagnation";break
                                ready,_,_=select.select([p.stdout],[],[],.05)
                                if not ready:
                                    if p.poll() is not None:break
                                    continue
                                chunk=os.read(p.stdout.fileno(),65536)
                                if not chunk:
                                    if p.poll() is not None:break
                                    continue
                                pending+=chunk;lines=pending.split(b"\n");pending=lines.pop()
                                for line in lines:
                                    if line.startswith(b"MBDTRACE "):
                                        e=json.loads(line[9:])
                                        vals={reverse[n]:exact_int(v) for n,v in e["values"].items()}
                                        try:k=local_check(pre,g,vals)
                                        except ValueError:
                                            result["invalid_candidate_count"]+=1;continue
                                        if k!=exact_int(e["objective"]):raise ValueError("Objective inconsistent")
                                        if k<ks.get(g["id"],float("inf")):
                                            best[g["id"]]=vals;ks[g["id"]]=k;last_improved=time.perf_counter()
                                            result["verified_native_candidates"]=result.get("verified_native_candidates",0)+1
                                            if record("ls_iqcqp"):stop=True;break
                                        if k==lb:why="local_certified_bound";break
                                    elif line.startswith(b"CAIQSTATS "):
                                        _,a,b=line.decode().split();native_attempts=max(native_attempts,int(a));native_accepted=max(native_accepted,int(b))
                                    elif line.startswith(b"MBDEND "):
                                        e=json.loads(line[7:]);native_attempts=max(native_attempts,e.get("component_attempts",0));native_accepted=max(native_accepted,e.get("component_accepted",0))
                                if stop or why=="local_certified_bound":break
                        finally:
                            if p.poll() is None:p.terminate()
                            try:p.wait(timeout=.25)
                            except subprocess.TimeoutExpired:p.kill();p.wait()
                            if fd is not None:os.close(fd)
                        if p.returncode not in (0,-15):raise RuntimeError("Native search failed: "+str(p.returncode))
                        result["native_component_attempts"]+=native_attempts;result["native_component_accepted"]+=native_accepted
                        rounds.append(dict(group=gi,round=ri,seed=seed+104729*(ri-1)+gi,wall_s=time.perf_counter()-tick,termination=why,best_cardinality=ks.get(g["id"])))
                        publish()
                        if stop:break
                        if ks.get(g["id"])==lb or not cfg["restarts"]:break
                        if cfg["conflicts"] and len(best)==len(pre["groups"]):
                            combined={n:v for vv in best.values() for n,v in vv.items()}
                            complete,_=restore(pre,combined)
                            healthy={c["name"] for c in model["components"] if complete["AB_"+c["name"]]==0}
                            added=[];oracle_end=min(group_end,time.perf_counter()+.1)
                            for c in model["components"]:
                                if len(added)>=4 or len(conflicts)>=128 or time.perf_counter()>=oracle_end:break
                                if complete["AB_"+c["name"]]==0:continue
                                trial=healthy|{c["name"]}
                                if certified_conflict(model,trial):
                                    cc=frozenset(trial)
                                    if not any(old<=cc for old in conflicts):added.append(cc);conflicts.append(cc)
                            if added:
                                result["conflict_learning_events"]+=len(added)
                                result["conflict_constraints_added"]=result.get("conflict_constraints_added",0)+add_conflicts(pre,added)
                                result["lower_bound"]=conflict_bound(conflicts);result["certified_conflicts"]=len(conflicts)
                                if record("conflict_bounds"):stop=True;break
                    if stop:break
                result["native_invocations"]=calls
            record("final_merge")
        result["strict_equivalent_input"]=all(a["mathematically_equivalent_input"] for a in audits)
        result["generated_variables"]=len(pre["specs"])
        result["constraints"]=sum(len(g["constraints"]) for g in pre["groups"])
        result["max_resident_group_variables"]=max((len(g["variables"]) for g in pre["groups"]),default=0)
        result["audited_groups"]=len(audits)
        result["outcome"]="optimal_certified" if result["own_optimality_certificate"] else "target_reached" if result.get("target_time_s") is not None else "feasible_budget_end" if result["has_verified_feasible"] else "no_verified_feasible"
    except Exception as exc:
        result.update(outcome="error",error=repr(exc),traceback=traceback.format_exc())
    result["total_s"]=time.perf_counter()-START
    for budget in (10,60,300):
        pts=[e["cardinality"] for e in trace if e["total_s"]<=budget]
        result["best_at_"+str(budget)+"s"]=min(pts,default=None) if result["total_s"]>=budget or result["own_optimality_certificate"] or result.get("target_time_s") is not None else None
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in ("method","instance_id","outcome","best_cardinality","total_s")}),flush=True)
if __name__=="__main__":run()
