"""Source integrity, public-tree exclusions and the two supported configurations."""

from pathlib import Path
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag.runner import verify_sources, backend_configuration
from arithdiag.variants import VARIANTS

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
assert ls["budget_policy"] == g["budget_policy"] == "fraction50"
for variant, (search, proof) in VARIANTS.items():
    cfg = backend_configuration("ArithDiag-LS", variant)
    assert cfg["internal_candidate_search"] == search
    assert cfg["internal_proof_enhancement"] == proof
    assert cfg["internal_callbacks"] == (search or proof)
    assert cfg["structural"] and cfg["dominance"] and cfg["decomposition"]
    assert cfg["circuit_initialisation"] and cfg["static_conflicts_enabled"] and cfg["basic_conflict_bound"]
    assert cfg["native_actions"] and not cfg["dynamic_proved_cuts"]
try:
    backend_configuration("ArithDiag-G", "backend-only")
except ValueError:
    pass
else:
    raise AssertionError("G adapter accepted an unsupported ablation")
assert "gurobipy" not in sys.modules
print(
    json.dumps(
        dict(
            passed=True,
            source_files=len(manifest["files"]),
            backends=["ArithDiag-G", "ArithDiag-LS"],
            main_backend="ArithDiag-LS",
            ls_variants=list(VARIANTS),
        )
    )
)
