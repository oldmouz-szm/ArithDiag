"""Source integrity, public-tree exclusions and the two supported configurations."""

from pathlib import Path
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arithdiag.runner import verify_sources, backend_configuration
from arithdiag.variants import VARIANTS
from arithdiag import __version__

manifest = verify_sources()
assert manifest["version"] == __version__ == "0.5.0"
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
assert ls["budget_policy"] == g["budget_policy"] == "interleaved50"
assert ls["proof_callback_placement"] == "between_native_rounds"
assert ls["pre_encoding_proof_request_s"] == 5.0
assert ls["advance_unused_credit_after_native_stagnation"]
assert ls["explained_shared_product_relations"]
assert ls["proof_master_optimization"] == "resumable_exact_family_and_rational_packing"
entry = (ROOT / "tools/check.py").read_text(encoding="utf-8")
for check in ("check_schedule.py", "check_relations.py", "check_resumable.py",
              "check_discovery_reserve.py", "check_master.py", "check_affine.py"):
    assert check in entry, "Missing default regression entry: " + check
for variant, (search, proof) in VARIANTS.items():
    cfg = backend_configuration("ArithDiag-LS", variant)
    assert cfg["internal_candidate_search"] == search
    assert cfg["internal_proof_enhancement"] == proof
    assert cfg["internal_callbacks"] == (search or proof)
    assert cfg["structural"] and cfg["dominance"] and cfg["decomposition"]
    assert cfg["circuit_initialisation"] and cfg["static_conflicts_enabled"] and cfg["basic_conflict_bound"]
    assert cfg["native_actions"] and not cfg["dynamic_proved_cuts"]
    assert cfg["budget_policy"] == "interleaved50"
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
