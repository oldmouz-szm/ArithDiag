"""The production ArithDiag-G parameters; no alternative search policies."""

from arithdiag.internal_budget import selected_policy, policy_configuration
from arithdiag.variants import configuration as variant_configuration

PARAMS = dict(
    Threads=1,
    Seed=1,
    NonConvex=2,
    MIPGap=0.0,
    MIPGapAbs=0.0,
    IntFeasTol=1e-9,
    FeasibilityTol=1e-9,
    NumericFocus=2,
)


def configuration(method="ArithDiag-G"):
    if method != "ArithDiag-G":
        raise ValueError("Unsupported ArithDiag-G configuration")
    allocation = policy_configuration(selected_policy())
    features = variant_configuration()
    if features["variant"] != "full":
        raise ValueError("ArithDiag-G is the full-policy backend replacement adapter")
    return dict(
        backend="Gurobi",
        encoding="radix256_integer_quadratic_indicators",
        simplification="propagation_dominance_decomposition",
        static_conflicts="deterministic_observed_cones",
        initialisation="circuit_forward",
        internal_policy="component_guided",
        common_model="conditional_arithmetic_v2",
        native_parameters=dict(PARAMS),
        initial_refinement_limit_s=0.35,
        pre_encoding_proof_request_s=allocation["initial_request_s"],
        callback_proof_request_s=0.75,
        callback_proof_interval_s=1.0,
        native_component_moves=False,
        learned_conflicts_to_backend=False,
        external_proof_oracle=False,
        external_reference_input=False,
        numeric_policy="numerical warnings disable native lower bounds and native certificates",
        **features,
        **allocation,
    )
