"""Apply Linux resource limits before importing either backend."""

from pathlib import Path
import os
import resource
import runpy
import sys

ROOT = Path(__file__).resolve().parent
address_space, backend, dataset, instance, limit, seed, target = sys.argv[1:]
if backend not in ("ArithDiag-G", "ArithDiag-LS"):
    raise ValueError("Unsupported ArithDiag backend")
resource.setrlimit(resource.RLIMIT_AS, (int(address_space) * 1024**2,) * 2)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
os.sched_setaffinity(0, {int(os.environ["ARITHDIAG_AFFINITY_CPU"])})
os.environ["ARITHDIAG_ADDRESS_SPACE_MIB"] = address_space
script = ROOT / backend / "worker.py"
sys.path[:0] = [str(script.parent), str(ROOT / "src")]
sys.argv = [str(script), dataset, instance, limit, seed, backend, "none", target]
runpy.run_path(str(script), run_name="__main__")
