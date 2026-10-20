"""ArithDiag-LS: integer quadratic Big-M encoding and adapted local search."""

import os, sys, time, json, resource
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
ROOT = Path(__file__).resolve().parents[1]
START = float(os.environ.get("ARITHDIAG_PROCESS_START_TICK", time.perf_counter()))
from arithdiag.preprocessing import (
    load,
    transform,
    restore,
    initial,
    projected_initial,
    cone_conflicts,
    add_conflicts,
    conflict_bound,
    learn_conflicts,
)
from arithdiag.proof_coordinator import ProofCoordinator
from arithdiag.internal_budget import selected_policy, policy_configuration, run_initial
from arithdiag.variants import configuration as variant_configuration
from native_adapter import run_backend


def configuration():
    allocation = policy_configuration(selected_policy())
    features = variant_configuration()
    return dict(
        backend="adapted_LS-IQCQP",
        internal_policy="component_guided",
        common_model="conditional_arithmetic_v2",
        structural=True,
        dominance=True,
        decomposition=True,
        joint_native_model=True,
        initial_refinement_limit_s=0.35 if features["internal_proof_enhancement"] else 0.0,
        pre_encoding_proof_request_s=allocation["initial_request_s"],
        proof_request_s=0.75,
        proof_interval_s=1.0,
        native_actions=True,
        native_restarts_s=[5, 10, 15],
        stagnation_s=3.0,
        pause_native_during_internal_proof=features["internal_callbacks"],
        dynamic_proved_cuts=False,
        initial_static_cones_only=True,
        external_reference_input=False,
        reference_stopping=False,
        **features,
        **allocation,
    )


def main():
    dataset, instance, limit, seed, method, goal, target = sys.argv[1:]
    assert method == "ArithDiag-LS" and goal == "none"
    limit = float(limit)
    seed = int(seed)
    deadline = START + limit
    target = Path(target)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.nice(10)
    result = dict(
        schema="arithdiag-result-v1",
        method=method,
        configuration=configuration(),
        instance_id=instance,
        seed=seed,
        time_limit_s=limit,
        trace=[],
        lower_bound=0,
        lower_bound_total_s=0.0,
        lower_bound_trace=[
            dict(total_s=0.0, value=0, source="nonnegative_fault_count")
        ],
        own_optimality_certificate=False,
        termination="budget_exhausted",
        outcome="unknown",
        invalid_candidate_count=0,
        callback_errors=0,
        native_invocations=0,
        bigm_encoding_invocations=0,
        native_audit_invocations=0,
        native_component_attempts=0,
        native_component_accepted=0,
        native_statistics_complete=True,
        rounds=[],
        model_loading_s=0.0,
        simplification_s=0.0,
        encoding_s=0.0,
        search_s=0.0,
        exact_validation_s=0.0,
        proof_kind=None,
        proof_independently_checked=False,
        reference_input_to_solver=False,
        assignment_export=False,
        diagnosis_export=False,
        gurobi_imported=False,
    )
    best = [None, None, None]
    internal = [0]
    coop = None

    def now():
        return time.perf_counter() - START

    def publish():
        if coop:
            result.update(coop.telemetry())
        result["total_s"] = now()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2))
        os.replace(tmp, target)

    def lower(value, source):
        if now() <= limit and value > result["lower_bound"]:
            if best[1] is not None and value > best[1]:
                raise ValueError("bound_exceeds_verified_incumbent")
            result.update(
                lower_bound=value, lower_bound_total_s=now(), lower_bound_source=source
            )
            result["lower_bound_trace"].append(
                dict(total_s=now(), value=value, source=source)
            )

    def accept(x, origin):
        t = time.perf_counter()
        try:
            complete, k = restore(pre, x)
        except ValueError:
            result["invalid_candidate_count"] += 1
            return False
        finally:
            result["exact_validation_s"] += time.perf_counter() - t
        if now() > limit:
            return False
        if k < internal[0]:
            raise ValueError("witness_below_internal_bound")
        if best[1] is None or k < best[1]:
            best[:] = [dict(x), k, complete]
            result["trace"].append(dict(total_s=now(), cardinality=k, origin=origin))
            result.update(has_verified_feasible=True, best_cardinality=k)
            publish()
        return True

    def certify():
        if (
            best[1] is not None
            and internal[0] == best[1]
            and now() < limit
            and not result["invalid_candidate_count"]
            and not result["callback_errors"]
        ):
            result.update(
                own_optimality_certificate=True,
                proof_time_s=now(),
                optimality_certificate_total_s=now(),
                termination="certified_internal_bounds_match",
                outcome="optimal_certified",
                proof_kind="certified_integer_conflicts_and_exact_original_witness",
            )
            publish()
            return True
        return False

    def strengthen(request):
        if coop is None or best[2] is None:
            return
        value = coop.step(best[2], best[1], request, deadline, accept)
        if now() < limit:
            internal[0] = max(internal[0], value)
            lower(internal[0], "certified_internal_integer_bound")

    try:
        t = time.perf_counter()
        model = load("benchmark", *instance.split("/"))
        result["model_loading_s"] = time.perf_counter() - t
        t = time.perf_counter()
        pre = transform(model, True, True, True)
        result["simplification_s"] = time.perf_counter() - t
        result.update(pre["stats"])
        cores = cone_conflicts(model)
        add_conflicts(pre, cores)
        internal[0] = conflict_bound(cores)
        lower(internal[0], "certified_observed_cone_disjoint_packing")
        init = projected_initial(pre, initial(model))
        if init is not None:
            accept(init, "circuit_initialisation")
        t = time.perf_counter()
        features = result["configuration"]
        refined, checks = (
            learn_conflicts(model, min(deadline - 0.03, t + 0.35), initial_conflicts=cores)
            if features["internal_proof_enhancement"] else (cores, 0)
        )
        result.update(
            initial_refinement_s=time.perf_counter() - t,
            initial_refinement_checks=checks,
        )
        internal[0] = max(internal[0], conflict_bound(refined))
        lower(internal[0], "certified_initial_refinement")
        result["initial_phase_upper_before"] = best[1]
        if features["internal_callbacks"]:
            coop = ProofCoordinator(
                model, pre, refined, limit, internal[0], best[2], known_cores=cores,
                candidate_search=features["internal_candidate_search"],
                proof_enhancement=features["internal_proof_enhancement"],
            )
            run_initial(coop, selected_policy(), deadline, result, strengthen, now)
        else:
            result.update(internal_budget_total_s=0.0, coordination_calls=0,
                          coordination_candidates=0, coordination_new_conflicts=0,
                          proof_strengthening_s=0.0, initial_phase_actual_s=0.0)
        result["initial_phase_upper_after"] = best[1]
        result["resolved_before_backend"] = False
        if certify():
            result["resolved_before_backend"] = True
            publish()
            return
        if now() >= limit - 0.05:
            raise TimeoutError()
        result["backend_handoff_total_s"] = now()
        publish()
        run_backend(
            ROOT,
            pre,
            deadline,
            seed,
            best,
            accept,
            strengthen,
            certify,
            publish,
            result,
        )
        if not certify():
            result["outcome"] = (
                "verified_feasible" if best[1] is not None else "unknown"
            )
    except TimeoutError:
        pass
    except MemoryError:
        result.update(termination="address_space_limit", outcome="memory_limit")
    except Exception as exc:
        result.update(
            termination="worker_error",
            outcome="error",
            error_class=type(exc).__name__,
            error_category=(
                str(exc)
                if str(exc).startswith(("native_", "bound_", "witness_"))
                else "worker_exception"
            ),
        )
    finally:
        result["gurobi_imported"] = any(
            n == "gurobipy" or n.startswith("gurobipy.") for n in sys.modules
        )
        if result["gurobi_imported"]:
            result.update(
                termination="worker_error",
                outcome="error",
                error_category="forbidden_gurobi_import",
            )
        publish()


if __name__ == "__main__":
    main()
