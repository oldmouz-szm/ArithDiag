"""Source integrity, public-tree exclusions and the two supported configurations."""

from pathlib import Path
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag.runner import verify_sources, backend_configuration

manifest = verify_sources()
for relative in manifest["files"]:
    assert not any(
        part
        in {"datasets", "baseline", "baselines", "results", "secrets", "provenance"}
        for part in Path(relative).parts
    )
    assert Path(relative).suffix not in {
        ".lic",
        ".lp",
        ".log",
        ".pyc",
        ".o",
        ".so",
        ".gz",
        ".zip",
    }
    path = ROOT / relative
    if path.suffix == ".py":
        ast.parse(path.read_text(encoding="utf-8"))
g = backend_configuration("ArithDiag-G")
assert not g["native_component_moves"] and not g["learned_conflicts_to_backend"]
assert not g["external_reference_input"] and not g["external_proof_oracle"]
ls = backend_configuration("ArithDiag-LS")
assert ls["structural"] and ls["dominance"] and ls["decomposition"]
assert ls["native_actions"] and not ls["external_reference_input"]
assert ls["internal_policy"] == g["internal_policy"] == "component_guided"
assert "gurobipy" not in sys.modules
print(
    json.dumps(
        dict(
            passed=True,
            source_files=len(manifest["files"]),
            backends=["ArithDiag-G", "ArithDiag-LS"],
        )
    )
)
