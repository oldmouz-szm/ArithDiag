"""Transient, audited LS backend. Native and proof share one physical CPU."""

import hashlib, json, os, select, signal, subprocess, time
from pathlib import Path
from native_io import render, audit, exact_int, native_values
from native_helpers import encode, metadata, local_check


def consume_final_fragment(raw, consumer, on_truncated):
    """A terminated native writer may leave an incomplete last JSON record."""
    try:
        consumer(raw)
    except json.JSONDecodeError:
        on_truncated()


def run_backend(
    root, pre, deadline, seed, best, accept, strengthen, certify, publish, result
):
    native = root / "ArithDiag-LS/native/build/arithdiag-ls"
    # Encode one joint residual model, including every active abnormality variable.
    group = dict(
        id=0,
        variables=sorted(pre["specs"]),
        components=sorted(
            pre["specs"][n]["signal"]
            for n in pre["specs"]
            if pre["specs"][n]["role"] == "abnormal"
        ),
        constraints=[c for g in pre["groups"] for c in g["constraints"]],
    )
    t = time.perf_counter()
    specs, encoded, names = encode(pre, group)
    result['bigm_encoding_invocations'] += 1
    result['ls_encoded_constraints'] = len(encoded['constraints'])
    reverse = {v: k for k, v in names.items()}
    text = render(specs, encoded)
    result["native_model_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    path = Path(os.environ["ARITHDIAG_WORK_ROOT"]) / "joint-model.lp"
    path.write_text(text, newline="\n")
    result["encoding_s"] += time.perf_counter() - t
    left = deadline - time.perf_counter()
    if left <= 0.03:
        raise TimeoutError()
    t = time.perf_counter()
    check = subprocess.run(
        [str(native), "--audit", str(path)],
        capture_output=True,
        text=True,
        timeout=left,
    )
    if check.returncode:
        raise RuntimeError("native_input_audit_failed")
    report = audit(specs, encoded, json.loads(check.stdout))
    if not report["mathematically_equivalent_input"]:
        raise ValueError("native_input_not_equivalent")
    result.update(
        input_audit_s=time.perf_counter() - t,
        native_audit_invocations=1,
        strict_equivalent_input=True,
        native_safe_bigm_adjustments=report["safe_redundant_bigm_rounding_count"],
    )
    if time.perf_counter() >= deadline:
        raise TimeoutError()
    ri = 0
    last_proof = time.perf_counter()
    while time.perf_counter() < deadline - 0.04:
        ri += 1
        duration = min(5 * min(ri, 3), deadline - time.perf_counter() - 0.02)
        if duration <= 0.02:
            break
        round_seed = seed + 104729 * (ri - 1)
        meta = os.memfd_create("arithdiag-ls-transient-warmstart", 0)
        os.write(meta, metadata(pre, group, names, best[0], True))
        os.lseek(meta, 0, 0)
        err = os.memfd_create("arithdiag-ls-transient-diagnostics", os.MFD_CLOEXEC)
        command = [
            str(native),
            str(duration),
            "1",
            str(path),
            str(round_seed),
            "1",
            "/proc/self/fd/" + str(meta),
        ]
        p = None
        start = time.perf_counter()
        last_improvement = start
        paused = 0.0
        pending = b""
        attempts = accepted = 0
        ended = False
        why = "round_deadline"
        stop = False
        result["native_launch_pending"] = True
        publish()
        try:
            p = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=err, pass_fds=(meta,), bufsize=0
            )
            os.set_blocking(p.stdout.fileno(), False)
            result["native_invocations"] += 1
            result["native_launch_pending"] = False

            def line(raw):
                nonlocal attempts, accepted, ended, last_improvement, stop
                if raw.startswith(b"ARITHDIAG_TRACE "):
                    item = json.loads(raw[len(b"ARITHDIAG_TRACE ") :])
                    try:
                        values = {
                            reverse[n]: v
                            for n, v in native_values(
                                specs, encoded, item["values"]
                            ).items()
                        }
                        k = local_check(pre, group, values)
                    except ValueError:
                        result["invalid_candidate_count"] += 1
                        return
                    if k != exact_int(item["objective"]):
                        raise ValueError("native_objective_mismatch")
                    before = best[1]
                    accept(values, "ls_iqcqp_incumbent")
                    if best[1] is not None and (before is None or best[1] < before):
                        last_improvement = time.perf_counter()
                    if certify():
                        stop = True
                elif raw.startswith(b"ARITHDIAG_STATS "):
                    _, a, b = raw.split()
                    attempts = max(attempts, int(a))
                    accepted = max(accepted, int(b))
                elif raw.startswith(b"ARITHDIAG_END "):
                    item = json.loads(raw[len(b"ARITHDIAG_END ") :])
                    attempts = max(attempts, item.get("component_attempts", 0))
                    accepted = max(accepted, item.get("component_accepted", 0))
                    ended = True

            def drain(final=False):
                nonlocal pending
                for _ in range(1024 if final else 16):
                    try:
                        chunk = os.read(p.stdout.fileno(), 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        break
                    pending += chunk
                    lines = pending.split(b"\n")
                    pending = lines.pop()
                    for raw in lines:
                        line(raw)
                if final and pending:

                    def truncated():
                        result["native_truncated_final_records"] = (
                            result.get("native_truncated_final_records", 0) + 1
                        )

                    consume_final_fragment(pending, line, truncated)
                    pending = b""

            while time.perf_counter() < min(deadline, start + duration):
                select.select([p.stdout], [], [], 0.03)
                drain()
                if stop:
                    why = "certified_internal_bounds_match"
                    break
                if p.poll() is not None:
                    why = "native_exit"
                    break
                if (result["configuration"].get("internal_callbacks", True)
                    and time.perf_counter() - last_proof >= 1.0 and best[2] is not None):
                    tick = time.perf_counter()
                    before = best[1]
                    suspended = False
                    try:
                        if p.poll() is None:
                            os.kill(p.pid, signal.SIGSTOP)
                            suspended = True
                        strengthen(0.75)
                        if certify():
                            stop = True
                    finally:
                        if suspended and p.poll() is None:
                            os.kill(p.pid, signal.SIGCONT)
                        paused += time.perf_counter() - tick
                    last_proof = time.perf_counter()
                    publish()
                    if stop:
                        why = "certified_internal_bounds_match"
                        break
                    if best[1] < before:
                        why = "internal_candidate_warmstart"
                        break
                if time.perf_counter() - last_improvement >= 3.0:
                    why = "stagnation"
                    break
            if time.perf_counter() >= deadline:
                why = "instance_deadline"
        finally:
            result["native_launch_pending"] = False
            if p is not None:
                if p.poll() is None:
                    p.send_signal(signal.SIGCONT)
                    p.terminate()
                try:
                    p.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
                drain(final=True)
                p.stdout.close()
                os.lseek(err, 0, 0)
                error = os.read(err, 16384)
                if p.returncode not in (0, -15):
                    if b"std::bad_alloc" in error or b"Cannot allocate memory" in error:
                        raise MemoryError()
                    raise RuntimeError("native_search_exit_" + str(p.returncode))
            os.close(meta)
            os.close(err)
            result["search_s"] += max(0.0, time.perf_counter() - start - paused)
            result["native_component_attempts"] += attempts
            result["native_component_accepted"] += accepted
            result["native_statistics_complete"] = (
                result["native_statistics_complete"] and ended
            )
            result["rounds"].append(
                dict(
                    round=ri,
                    seed=round_seed,
                    wall_s=time.perf_counter() - start,
                    proof_pause_s=paused,
                    termination=why,
                    statistics_complete=ended,
                )
            )
        publish()
        if stop:
            return
