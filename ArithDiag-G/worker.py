"""ArithDiag-G: radix-256 integer encoding with indicator constraints and Gurobi."""

import os, sys, time, json, math, resource
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
from configuration import PARAMS, configuration
from limb_model import Encoding, guard_audit
from arithdiag.proof_coordinator import ProofCoordinator
import gurobipy as gp
from gurobipy import GRB


def main():
    dataset, instance, limit, seed, method, goal, target = sys.argv[1:]
    assert goal == "none"
    limit = float(limit)
    seed = int(seed)
    deadline = START + limit
    target = Path(target)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.nice(10)
    result = dict(
        schema="arithdiag-result-v1",
        method=method,
        configuration=configuration(method),
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
        callback_calls=0,
        numeric_warning_count=0,
        numeric_warning_categories=[],
        native_bounds_trusted=True,
        native_invocations=0,
        license_session_started=False,
        proof_cuts_root=0,
        proof_cuts_callback=0,
        proof_bound_cuts=0,
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
    )
    best = [None, None, None]
    internal = [0]
    native = [0]
    env = None
    enc = None
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
                raise ValueError("Bound exceeds verified incumbent")
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
            raise ValueError("Valid witness below internal proof bound")
        if best[1] is None or k < best[1]:
            best[:] = [dict(x), k, complete]
            result["trace"].append(dict(total_s=now(), cardinality=k, origin=origin))
            result.update(has_verified_feasible=True, best_cardinality=k)
            publish()
        return True

    def certify_internal():
        if (
            best[1] is not None
            and internal[0] == best[1]
            and (now() < limit)
            and (not result["invalid_candidate_count"])
            and (not result["callback_errors"])
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
        refined, checks = learn_conflicts(
            model, min(deadline - 0.03, t + 0.35), initial_conflicts=cores
        )
        result.update(
            initial_refinement_s=time.perf_counter() - t,
            initial_refinement_checks=checks,
        )
        internal[0] = max(internal[0], conflict_bound(refined))
        lower(internal[0], "certified_initial_refinement")
        coop = ProofCoordinator(
            model, pre, refined, limit, internal[0], best[2], known_cores=cores
        )
        strengthen(1.75)
        if certify_internal():
            return
        if now() >= limit - 0.05:
            raise TimeoutError()
        result["original_guard_audit"] = guard_audit(model)
        t = time.perf_counter()
        env = None
        if env is None:
            env = gp.Env(empty=True)
            env.setParam("OutputFlag", 0)
            env.setParam("WLSTokenDuration", 5)
            env.setParam("WLSTokenRefresh", 1.0)
            result["license_session_started"] = True
            env.start()
        result["license_ready_total_s"] = now()
        result["gurobi_version"] = list(gp.gurobi.version())
        enc = Encoding(pre, env, deadline)
        result["base_formulation_sha256"] = enc.digest
        result["model_audit"] = enc.audit()
        result["encoding_s"] = time.perf_counter() - t
        m = enc.m
        for k, v in PARAMS.items():
            m.setParam(k, seed if k == "Seed" else v)
        if best[0] is not None:
            for v, x in zip(enc.vs, enc.assignment(best[0])):
                v.Start = x
        last_proof = [now()]
        last_publish = [now()]

        def callback(m, where):
            result["callback_calls"] += 1
            if now() >= limit - 0.03:
                m.terminate()
                return
            try:
                bound = None
                if where == GRB.Callback.MESSAGE:
                    message = m.cbGet(GRB.Callback.MSG_STRING).lower()
                    flags = [
                        k
                        for k in (
                            "warning",
                            "numerical",
                            "large bounds",
                            "large matrix",
                            "large rhs",
                            "unscaled primal violation",
                            "max constraint violation",
                            "max bound violation",
                        )
                        if k in message
                    ]
                    if flags:
                        result["numeric_warning_count"] += 1
                        result["native_bounds_trusted"] = False
                        result["numeric_warning_categories"] = sorted(
                            set(result["numeric_warning_categories"]) | set(flags)
                        )
                        result["lower_bound_trace"][:] = [
                            p
                            for p in result["lower_bound_trace"]
                            if p["source"] != "gurobi_native_bound"
                        ]
                        result.update(
                            lower_bound=internal[0],
                            lower_bound_total_s=now(),
                            lower_bound_source="certified_internal_integer_bound",
                        )
                elif where == GRB.Callback.MIP:
                    bound = m.cbGet(GRB.Callback.MIP_OBJBND)
                elif where == GRB.Callback.MIPSOL:
                    bound = m.cbGet(GRB.Callback.MIPSOL_OBJBND)
                    try:
                        accept(enc.decode(m.cbGetSolution(enc.vs)), "gurobi_incumbent")
                    except ValueError:
                        result["invalid_candidate_count"] += 1
                elif where == GRB.Callback.MIPNODE:
                    bound = m.cbGet(GRB.Callback.MIPNODE_OBJBND)
                if (
                    result["native_bounds_trusted"]
                    and bound is not None
                    and math.isfinite(bound)
                    and (abs(bound) < 1e90)
                ):
                    native[0] = max(native[0], max(0, math.ceil(bound - 1e-05)))
                    lower(native[0], "gurobi_native_bound")
                if where in (
                    GRB.Callback.MIP,
                    GRB.Callback.MIPSOL,
                    GRB.Callback.MIPNODE,
                ):
                    if now() - last_proof[0] >= 1.0 and best[2] is not None:
                        last_proof[0] = now()
                        before_k = best[1]
                        strengthen(0.75)
                        if best[1] < before_k and now() < limit - 0.03:
                            m.cbSetSolution(enc.vs, enc.assignment(best[0]))
                            result["internal_heuristic_submissions"] = (
                                result.get("internal_heuristic_submissions", 0) + 1
                            )
                    if certify_internal():
                        m.terminate()
                        return
                if now() - last_publish[0] >= 0.5:
                    publish()
                    last_publish[0] = now()
            except Exception as exc:
                result["callback_errors"] += 1
                result["callback_error_class"] = type(exc).__name__
                result["callback_error_number"] = getattr(exc, "errno", None)
                m.terminate()

        if now() >= limit - 0.05:
            raise TimeoutError()
        m.Params.TimeLimit = max(0.001, deadline - time.perf_counter() - 0.03)
        publish()
        result["native_invocations"] = 1
        t = time.perf_counter()
        m.optimize(callback)
        result["search_s"] = time.perf_counter() - t
        result.update(
            gurobi_status=m.Status,
            gurobi_nodes=m.NodeCount,
            gurobi_solutions=m.SolCount,
        )
        if m.SolCount and now() < limit:
            try:
                accept(enc.decode(m.getAttr("X", enc.vs)), "gurobi_final")
            except ValueError:
                result["invalid_candidate_count"] += 1
        if (
            result["native_bounds_trusted"]
            and math.isfinite(m.ObjBound)
            and (abs(m.ObjBound) < 1e90)
        ):
            native[0] = max(native[0], max(0, math.ceil(m.ObjBound - 1e-05)))
            lower(native[0], "gurobi_native_bound")
        if result["own_optimality_certificate"]:
            pass
        elif certify_internal():
            pass
        elif (
            m.Status == GRB.OPTIMAL
            and best[1] is not None
            and (round(m.ObjVal) == best[1])
            and (result["lower_bound"] == best[1])
            and (now() < limit)
            and (not result["invalid_candidate_count"])
            and (not result["callback_errors"])
            and result["native_bounds_trusted"]
        ):
            result.update(
                own_optimality_certificate=True,
                proof_time_s=now(),
                optimality_certificate_total_s=now(),
                proof_kind="native_solver_report_on_audited_formulation_with_exact_original_witness",
                termination="solver_optimal",
                outcome="optimal_certified",
            )
        elif result["callback_errors"]:
            result.update(termination="worker_error", outcome="error")
        elif not result["native_bounds_trusted"]:
            result.update(
                termination="numerical_uncertain",
                outcome="verified_feasible" if best[1] is not None else "unknown",
            )
        else:
            result.update(
                termination=(
                    "budget_exhausted"
                    if m.Status in (GRB.TIME_LIMIT, GRB.INTERRUPTED)
                    else "solver_stopped"
                ),
                outcome="verified_feasible" if best[1] is not None else "unknown",
            )
    except TimeoutError:
        pass
    except MemoryError:
        result.update(termination="address_space_limit", outcome="memory_limit")
    except gp.GurobiError as exc:
        result.update(
            termination=(
                "license_environment_failure"
                if exc.errno in (10009, 10010)
                else "worker_error"
            ),
            outcome="error",
            error_class=type(exc).__name__,
            gurobi_error_number=exc.errno,
        )
    except Exception as exc:
        result.update(
            termination="worker_error", outcome="error", error_class=type(exc).__name__
        )
    finally:
        publish()
        if enc is not None:
            enc.m.dispose()
        if env is not None:
            env.dispose()


if __name__ == "__main__":
    main()
