#!/usr/bin/env python3
"""Portable serial ArithDiag campaign runner; no external target certificates."""
import argparse, hashlib, json, math, os, platform, signal, subprocess, sys, time
from pathlib import Path
from resources import available, group_rss
ROOT=Path(__file__).resolve().parents[1]
METHODS=("baseline","structure","restart","semantic","full")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def valid_iid(iid):
    parts=iid.split("/")
    return len(parts)==2 and all(part and part not in (".","..") and
        all(c.isalnum() or c=="_" for c in part) for part in parts) and parts[1].startswith("observations_")

def kill_group(process):
    try:os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()

def run_one(method,iid,limit,seed,out,dataset_root):
    case,obs=iid.split("/")
    target=out/"instances"/method/("seed"+str(seed))/case/(obs+".json")
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():return json.loads(target.read_text())
    free=available()
    if free<2.5:raise RuntimeError("Available host RAM is below 2.5 GiB; campaign stopped")
    start=time.perf_counter()
    env=dict(os.environ,ARITHDIAG_DATASET_ROOT=str(dataset_root),
        MBD_PROCESS_START_TICK=str(start),PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1")
    cmd=[sys.executable,"-B",str(ROOT/"src/worker.py"),method,"benchmark",case,obs,
         str(limit),str(seed),"none",str(target)]
    peak=0.;cause=None
    with target.with_suffix(".stdout.log").open("w") as stdout, target.with_suffix(".stderr.log").open("w") as stderr:
        process=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        next_host=start+15
        try:
            while process.poll() is None:
                peak=max(peak,group_rss(process.pid));now=time.perf_counter()
                if peak>1536:cause="memory_limit"
                elif now-start>=limit:cause="budget_exhausted"
                elif now>=next_host and limit-(now-start)>3.1:
                    try:
                        if available(timeout=3)<1.5:cause="host_memory_low"
                    except Exception:cause="host_memory_check_failed"
                    next_host=time.perf_counter()+15
                if cause:
                    kill_group(process);break
                time.sleep(min(.05,max(.001,limit-(time.perf_counter()-start))))
        except BaseException:
            kill_group(process);raise
    elapsed=time.perf_counter()-start
    source=target if target.exists() else target.with_suffix(".progress.json")
    result=json.loads(source.read_text()) if source.exists() else dict(
        schema="arithdiag-v1",method=method,instance_id=iid,seed=seed,trace=[],
        has_verified_feasible=False,best_cardinality=None,own_optimality_certificate=False,
        outcome="error",termination="worker_exited_without_record")
    # Only witnesses fully verified before the deadline are eligible for scoring.
    timely=[e for e in result.get("trace",[]) if e["total_s"]<=limit]
    result["trace"]=timely
    result["has_verified_feasible"]=bool(timely)
    result["best_cardinality"]=min((e["cardinality"] for e in timely),default=None)
    if timely:
        result["first_feasible_total_s"]=timely[0]["total_s"]
        result["best_total_s"]=next(e["total_s"] for e in timely if e["cardinality"]==result["best_cardinality"])
    else:
        result.pop("best_total_s",None);result.pop("first_feasible_total_s",None)
    certified=bool(timely) and result.get("own_optimality_certificate",False) and result["best_cardinality"]==result.get("lower_bound") and result.get("optimality_certificate_total_s",float("inf"))<=limit
    result["own_optimality_certificate"]=certified
    for budget in (10,60,300):
        pts=[e["cardinality"] for e in timely if e["total_s"]<=budget]
        result["best_at_"+str(budget)+"s"]=min(pts,default=None) if elapsed>=budget or certified else None
    if cause:
        result["termination"]=cause
        result["outcome"]=("optimal_certified" if certified else "feasible_budget_end" if timely else "no_verified_feasible") if cause=="budget_exhausted" else cause
    elif result.get("outcome")!="error":
        result["outcome"]="optimal_certified" if certified else "feasible_budget_end" if timely else "no_verified_feasible"
    result.update(method=method,instance_id=iid,seed=seed,time_limit_s=limit,
        process_wall_s=elapsed,peak_rss_mib=peak,rss_limit_mib=1536,
        address_space_limit_mib=2048,host_available_before_gib=free,
        worker_exit_code=process.returncode,budget_overrun_s=max(0,elapsed-limit))
    target.write_text(json.dumps(result,indent=2)+"\n")
    return result

def main():
    parser=argparse.ArgumentParser(description="ArithDiag: arithmetic-aware component diagnosis")
    parser.add_argument("--dataset-root",type=Path,required=True,help="read-only directory containing cases/ and library/")
    parser.add_argument("--run-name",required=True)
    parser.add_argument("--time-limit",type=float,default=300)
    parser.add_argument("--methods",nargs="+",choices=METHODS,default=["full"])
    select=parser.add_mutually_exclusive_group(required=True)
    select.add_argument("--instances",nargs="+",help="case/observations_NNN IDs")
    select.add_argument("--all",action="store_true",help="all observations_*.jsonl under cases/")
    parser.add_argument("--seeds",nargs="+",type=int,default=[1])
    parser.add_argument("--output-dir",type=Path,help="default: results/<run-name>")
    args=parser.parse_args()
    if Path(args.run_name).name!=args.run_name or args.run_name in (".","..") or not 0<args.time_limit<=300 or not math.isfinite(args.time_limit):
        parser.error("Use a single directory name and a finite deadline in (0, 300]")
    if len(args.methods)!=len(set(args.methods)) or len(args.seeds)!=len(set(args.seeds)):
        parser.error("Duplicate methods or seeds")
    if any(not 0<=seed<2**31 for seed in args.seeds):parser.error("Seeds must be in [0, 2**31)")
    dataset_root=args.dataset_root.expanduser().resolve()
    if not (dataset_root/"cases").is_dir() or not (dataset_root/"library").is_dir():
        parser.error("Dataset root must contain cases/ and library/")
    ids=args.instances or [path.parent.name+"/"+path.stem for path in sorted((dataset_root/"cases").glob("*/observations_*.jsonl"))]
    if not ids or len(ids)!=len(set(ids)) or not all(valid_iid(iid) for iid in ids):
        parser.error("No observations, duplicate IDs, or invalid case/observation ID")
    data_files=set((dataset_root/"library").glob("*.v"))
    for iid in ids:
        case,obs=iid.split("/")
        for file in [dataset_root/"cases"/case/"netlist.v",dataset_root/"cases"/case/(obs+".jsonl")]:
            if not file.is_file() or not file.resolve().is_relative_to(dataset_root):
                parser.error("Missing or out-of-root input: "+str(file))
            data_files.add(file)
    for method in args.methods:
        folder="native/ls-iqcqp" if method in ("restart","semantic","full") else "baseline/native"
        if not (ROOT/folder/"build/LS-IQCQP").is_file():parser.error("Run make first; missing "+folder+"/build/LS-IQCQP")
    out=(args.output_dir.expanduser().resolve() if args.output_dir else ROOT/"results"/args.run_name)
    if out.is_relative_to(dataset_root):parser.error("Results must be outside the read-only dataset directory")
    out.mkdir(parents=True,exist_ok=True)
    code_files=[p for folder in ("src","vendor","native","baseline") for p in (ROOT/folder).rglob("*")
        if p.is_file() and p.suffix in (".py",".cpp",".h") and "__pycache__" not in p.parts]
    binaries=[ROOT/folder/"build/LS-IQCQP" for folder in ("native/ls-iqcqp","baseline/native")]
    code_files += [p for p in binaries if p.is_file()]
    settings=dict(methods=args.methods,instances=ids,seeds=args.seeds,time_limit_s=args.time_limit,
        dataset_root=str(dataset_root),source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(code_files)},
        data_hashes={str(p.relative_to(dataset_root)):sha(p) for p in sorted(data_files)},
        threads=1,sequential=True,external_reference_stopping=False,diagnosis_export=False,
        budget_scope="fresh worker startup, parsing, preprocessing, audits, all restarts, exact verification")
    manifest=out/"manifest.json"
    if manifest.exists() and json.loads(manifest.read_text())["settings"]!=settings:
        parser.error("Run settings or inputs changed; choose another run name")
    provenance=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),
        affinity=sorted(os.sched_getaffinity(0)),rss_sampling_period_s=.05)
    manifest.write_text(json.dumps(dict(status="running",settings=settings,environment=provenance),indent=2)+"\n")
    records=[]
    try:
        total=len(args.seeds)*len(ids)*len(args.methods)
        for si,seed in enumerate(args.seeds):
            for ii,iid in enumerate(ids):
                offset=(si+ii)%len(args.methods)
                for method in args.methods[offset:]+args.methods[:offset]:
                    result=run_one(method,iid,args.time_limit,seed,out,dataset_root);records.append(result)
                    (out/"records.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))
                    elapsed=result.get("best_total_s",result.get("total_s",result["process_wall_s"]))
                    print(f'{len(records)}/{total} {method} seed={seed} {iid}: {result["outcome"]} k={result.get("best_cardinality")} t={elapsed:.3f}s RSS={result["peak_rss_mib"]:.1f}MiB',flush=True)
                    if result.get("termination") in ("host_memory_low","host_memory_check_failed"):
                        raise RuntimeError("Host memory guard stopped the campaign")
        errors=sum(r["outcome"]=="error" for r in records)
        manifest.write_text(json.dumps(dict(status="completed",settings=settings,environment=provenance,records=len(records),errors=errors),indent=2)+"\n")
        return 2 if errors else 0
    except BaseException as exc:
        manifest.write_text(json.dumps(dict(status="stopped",settings=settings,environment=provenance,reason=repr(exc),records=len(records)),indent=2)+"\n")
        raise

if __name__=="__main__":
    sys.exit(main())
