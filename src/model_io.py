"""Shared MBD model, native-input audit, and exact primal validation."""
import sys,time,json,hashlib,math,re,os
from pathlib import Path
from decimal import Decimal, getcontext
getcontext().prec=4096
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"vendor"))
import iqcqp_model as builder
from exact_verify import validate
from residual import split_nonlinear,residual_stats,verify_group
def load_builder():return builder
IQ=Path(os.environ.get("ARITHDIAG_DATASET_ROOT", str(ROOT/"data/benchmark"))).expanduser().resolve()
def prepare(dataset,case,obs):
 base=IQ/("nonlinear" if dataset=="nonlinear" else "")
 model=load_builder().build_diagnostic_model(base/"cases"/case/"netlist.v",base/"cases"/case/(obs+".jsonl"),IQ/"library")
 fixed,specs,groups=split_nonlinear(model)
 group=dict(components=sorted(c for g in groups for c in g["components"]),
   variables=sorted(specs),constraints=[c for g in groups for c in g["constraints"]])
 meta=dict(components=len(model["components"]),original_variables=len(model["variables"]),generated_variables=len(specs),
   constraints=len(group["constraints"]),independent_components=len(groups),**residual_stats(groups),
   max_variable_bits=max((int(v["ub"]).bit_length() for v in specs.values()),default=0),
   max_coefficient_bits=max((abs(a).bit_length() for c in group["constraints"] for a in c["terms"].values()),default=0),
   max_rhs_bits=max((abs(c["rhs"]).bit_length() for c in group["constraints"]),default=0))
 # Native LP readers treat ':' inside slice names as a constraint label.
 # Use reversible scalar aliases without changing arithmetic or domains.
 aliases={n:n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",n) else "mbd_scalar_"+str(i) for i,n in enumerate(group["variables"])}
 specs={aliases[n]:dict(v,name=aliases[n],original_name=n) for n,v in specs.items()}
 group["variables"]=[aliases[n] for n in group["variables"]]
 group["constraints"]=[dict(c,terms={aliases[n]:a for n,a in c["terms"].items()},
  quadratic=[dict(t,a=aliases[t["a"]],b=aliases[t["b"]]) for t in c.get("quadratic",[])]) for c in group["constraints"]]
 return model,fixed,specs,group,meta
def expression(terms):
 parts=[]
 for name,coef in terms:
  if not coef:continue
  sign="+" if coef>0 else "-"
  parts.append(f"{sign} {abs(coef)} {name}")
 return " ".join(parts) or "0"
def render(specs,group):
 out=["Minimize"," obj: "+expression(("AB_"+c,1) for c in group["components"]),"Subject To"]
 for c in group["constraints"]:
  lin=expression(c["terms"].items())
  quad=c.get("quadratic",[])
  if quad:
   q=expression((t["a"]+" * "+t["b"],t["coef"]) for t in quad)
   lin=(lin if lin!="0" else "")+" + [ "+q+" ]"
   lin=lin.strip()
   if lin.startswith("+ ["):lin=lin[2:]
  out.append(" "+c["name"]+": "+lin+" "+{"eq":"=","le":"<=","ge":">="}[c["sense"]]+" "+str(c["rhs"]))
 out+=["Bounds"]+[f" {specs[n]['lb']} <= {n} <= {specs[n]['ub']}" for n in group["variables"]]
 out+=["Binaries"]+[" "+n for n in group["variables"] if specs[n]["type"]=="binary"]
 out+=["Generals"]+[" "+n for n in group["variables"] if specs[n]["type"]!="binary"]+["End",""]
 return "\n".join(out)
def exact_int(x):
 d=Decimal(str(x))
 if not d.is_finite() or d!=d.to_integral_value():raise ValueError("Nonintegral numeric value")
 return int(d)
def verify(model,fixed,specs,group,raw,objective):
 values={n:exact_int(x) for n,x in raw.items()}
 if set(values)!=set(group["variables"]):raise ValueError("Missing/extra candidate variables")
 for n,v in values.items():
  if not specs[n]["lb"]<=v<=specs[n]["ub"]:raise ValueError("Candidate bound violation")
 verify_group(group,values)
 k=sum(values["AB_"+c] for c in group["components"])
 if k!=exact_int(objective):raise ValueError("Objective/AB cardinality mismatch")
 complete=dict(fixed);complete.update({specs[n].get("original_name",n):v for n,v in values.items()});check=validate(model,complete,k)
 if not check["valid"]:raise ValueError("Original circuit check: "+repr(check["errors"][:3]))
 return k
def canonical_monos(items):
 result={}
 for item in items:
  key=tuple(sorted(item["vars"]));result[key]=result.get(key,0)+Decimal(str(item["coef"]))
 return {k:v for k,v in result.items() if v}
def audit(specs,group,native):
 structural=[];numeric=[];safe=[]
 wanted={n:(v["type"],v["lb"],v["ub"]) for n,v in specs.items()}
 got={v["name"]:(v["type"],Decimal(v["lb"]),Decimal(v["ub"])) for v in native["variables"]}
 if set(wanted)!=set(got):structural.append("Variable names differ")
 for n in wanted.keys()&got.keys():
  if wanted[n][0]!=got[n][0]:structural.append("Variable type differs: "+n)
  for index in (1,2):
   if wanted[n][index]!=got[n][index]:numeric.append(dict(field="bound",variable=n,expected=str(wanted[n][index]),parsed=str(got[n][index])))
 expected={c["name"]:c for c in group["constraints"]};actual={c["name"]:c for c in native["constraints"]}
 if expected.keys()!=actual.keys():structural.append("Constraint names/count differ")
 for name in expected.keys()&actual.keys():
  a,b=expected[name],actual[name]
  if a["sense"]!=b["sense"]:structural.append("Constraint sense differs: "+name)
  if Decimal(b["rhs"])!=a["rhs"]:numeric.append(dict(field="rhs",constraint=name,expected=str(a["rhs"]),parsed=b["rhs"]))
  ms=[dict(vars=[n],coef=x) for n,x in a["terms"].items()]+[dict(vars=[t["a"],t["b"]],coef=t["coef"]) for t in a.get("quadratic",[])]
  x,y=canonical_monos(ms),canonical_monos(b["monomials"])
  if x.keys()!=y.keys():structural.append("Monomial variables differ: "+name)
  elif x!=y:
   numeric.append(dict(field="coefficients",constraint=name))
   changed=[key for key in x if x[key]!=y[key]]
   if len(changed)==1 and len(changed[0])==1 and changed[0][0].startswith("AB_") and a["sense"]=="le":
    ab=changed[0][0]
    if specs[ab]["type"]=="binary":
     high=y[changed[0]]
     for key,coef in y.items():
      if key==changed[0]:continue
      if len(key)==1:
       lo,hi=specs[key[0]]["lb"],specs[key[0]]["ub"]
      else:
       v1,v2=specs[key[0]],specs[key[1]]
       assert v1["lb"]>=0 and v2["lb"]>=0
       lo,hi=v1["lb"]*v2["lb"],v1["ub"]*v2["ub"]
      high+=coef*(hi if coef>=0 else lo)
     if high<=a["rhs"] and high-y[changed[0]]+x[changed[0]]<=a["rhs"]:safe.append(name)
 obj=canonical_monos(native["objective"])
 if obj!={("AB_"+c,):Decimal(1) for c in group["components"]}:structural.append("Objective differs")
 return dict(structurally_correct=not structural,parsed_numbers_exact=not numeric,
   mathematically_equivalent_input=not structural and len(numeric)==len(safe),safe_redundant_bigm_rounding_count=len(safe),
   structural_errors=structural[:20],structural_error_count=len(structural),numeric_mismatches=numeric[:20],numeric_mismatch_count=len(numeric),
   native_float_mantissa_bits=native["float_mantissa_bits"])
