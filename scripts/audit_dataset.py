#!/usr/bin/env python3
"""Audit external dataset models without solving or exporting witnesses."""
import argparse, json, os, sys, time, resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--dataset-root",type=Path,required=True)
parser.add_argument("--all",action="store_true",help="otherwise audit the first observation of each circuit")
args=parser.parse_args()
os.environ["ARITHDIAG_DATASET_ROOT"]=str(args.dataset_root.expanduser().resolve())
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
os.nice(10)
sys.path.insert(0,str(ROOT/"src"))
from preprocess import load, transform, initial, projected_initial, restore, cone_conflicts, conflict_bound
from worker import local_check
begin=time.perf_counter();count=0;largest=0
for top in sorted((args.dataset_root/"cases").glob("*/netlist.v")):
    observations=sorted(top.parent.glob("observations_*.jsonl"))
    for obs in observations if args.all else observations[:1]:
        model=load("benchmark",top.parent.name,obs.stem)
        pre=transform(model,True,True)
        witness=initial(model);assert witness is not None
        reduced=projected_initial(pre,witness);assert reduced is not None
        _,k=restore(pre,reduced)
        for group in pre["groups"]:local_check(pre,group,{n:reduced[n] for n in group["variables"]})
        assert conflict_bound(cone_conflicts(model))<=k
        count+=1;largest=max(largest,len(model["components"]))
        print(f"{count}: {top.parent.name}/{obs.stem} model, reduction and exact witness checks passed",flush=True)
if not count:raise RuntimeError("No observations found")
print(json.dumps(dict(passed=True,observations=count,max_components=largest,elapsed_s=time.perf_counter()-begin)))
