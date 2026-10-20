#!/usr/bin/env python3
"""Linux process-group supervision, deadline accounting and resumable attempt records.

Calls the existing worker with goal=none. A single event loop guards every
worker process group; one /proc scan measures all active groups per sample.
"""
from __future__ import annotations
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = {
    "diagnosis",
    "diagnoses",
    "diagnosis_members",
    "faults",
    "faulty_components",
    "assignment",
    "assignments",
    "values",
    "witness",
    "model",
    "sat_model",
    "signal_values",
    "stderr_tail",
    "raw_stdout",
    "raw_stderr",
}
ENV_FAILURES = {
    "interrupted",
    "controller_recovered_interrupted_attempt",
    "host_memory_low",
    "host_memory_low_before_launch",
    "host_memory_check_failed",
    "host_memory_check_failed_before_launch",
    "controller_guard_failed",
    "controller_launch_error",
    "license_environment_failure",
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: sanitize(item) for key, item in value.items() if key not in PRIVATE
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def cardinality(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def available_gib():
    # On native Linux, MemAvailable estimates usable RAM without swapping.
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            value = int(line.split()[1]) / 1024**2
            if not math.isfinite(value) or value < 0:
                break
            return value
    raise RuntimeError("Linux MemAvailable query failed")


def process_identity(pid):
    text = Path("/proc", str(pid), "stat").read_text()
    fields = text.rsplit(")", 1)[1].split()
    return dict(
        pid=int(pid),
        pgid=int(fields[2]),
        session=int(fields[3]),
        start_ticks=int(fields[19]),
    )


def rss_groups(pgids):
    """One /proc census, including all descendants in each owned session group.

    Missing processes are expected races; permission and parse failures raise
    rather than silently disable a memory guard.
    """
    totals = {pgid: 0.0 for pgid in pgids}
    members = {pgid: [] for pgid in pgids}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            ident = process_identity(directory.name)
            group = ident["pgid"]
            if group not in totals:
                continue
            status = (directory / "status").read_text().splitlines()
            rss = next(
                (
                    int(row.split()[1]) / 1024
                    for row in status
                    if row.startswith("VmRSS:")
                ),
                0.0,
            )
            totals[group] += rss
            members[group].append(int(directory.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return totals, members


def leader_rss(pid):
    """A cheap launch-time lower-bound sample before an NFS header fsync."""
    try:
        for line in Path("/proc", str(pid), "status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except (FileNotFoundError, ProcessLookupError):
        return None
    return None


def consume_pipe(item, stream, max_chunks=4):
    """Discard available bytes; recognize only explicit stderr allocator text.

    The bounded overlap exists only in controller memory. It is never a record
    field. At normal polling, the read cap preserves deadline responsiveness.
    After session exit the pipe is finite and is drained to EOF.
    """
    for _ in range(max_chunks):
        try:
            chunk = os.read(stream.fileno(), 65536)
        except BlockingIOError:
            return False
        if not chunk:
            return True
        if stream is item["process"].stderr:
            joined = item.get("allocator_overlap", b"") + chunk
            if any(
                marker in joined
                for marker in (
                    b"std::bad_alloc",
                    b"MemoryError",
                    b"Cannot allocate memory",
                )
            ):
                item["allocator_failure"] = True
            item["allocator_overlap"] = joined[-32:]
    return False


def own_groups(token):
    """Locate only this attempt's inherited token; never touch sibling projects."""
    expected = ("ARITHDIAG_ATTEMPT_TOKEN=" + token).encode()
    groups = set()
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            if expected not in (directory / "environ").read_bytes().split(b"\0"):
                continue
            ident = process_identity(directory.name)
            if ident["session"] != ident["pgid"]:
                raise RuntimeError(
                    "Owned descendant unexpectedly left its worker session"
                )
            groups.add(ident["pgid"])
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    if os.getpgrp() in groups:
        raise RuntimeError("Refusing to signal the controller process group")
    return groups


def kill_owned(token):
    for pgid in own_groups(token):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def environment():
    tools = {}
    for name in ("g++", "gcc", "ld", "make"):
        path = shutil.which(name)
        if path:
            resolved = Path(path).resolve()
            tools[name] = dict(
                path=str(resolved),
                sha256=sha(resolved),
                version=subprocess.check_output(
                    [path, "--version"], text=True
                ).splitlines()[0],
            )
    return dict(
        created_utc=utc(),
        hostname=platform.node(),
        platform=platform.platform(),
        python=sys.version,
        executable=sys.executable,
        uid=os.getuid(),
        affinity=sorted(os.sched_getaffinity(0)),
        cpu_count=os.cpu_count(),
        cpuinfo=Path("/proc/cpuinfo").read_text(),
        meminfo=Path("/proc/meminfo").read_text(),
        loadavg=Path("/proc/loadavg").read_text().strip(),
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        cgroup=Path("/proc/self/cgroup").read_text(),
        os_release=(
            Path("/etc/os-release").read_text()
            if Path("/etc/os-release").exists()
            else None
        ),
        build_tools=tools,
    )


def parse_cpus(text):
    result = []
    for segment in text.split(","):
        if "-" in segment:
            first, last = map(int, segment.split("-"))
            result.extend(range(first, last + 1))
        else:
            result.append(int(segment))
    if not result or len(result) != len(set(result)) or min(result) < 0:
        raise ValueError("CPU list must contain distinct nonnegative CPU IDs")
    return result


def check(manifest):
    for field in ("source_hashes", "input_hashes"):
        for path, expected in manifest[field].items():
            if not Path(path).is_file() or sha(path) != expected:
                raise RuntimeError("Frozen file changed: " + path)


def read_worker(target):
    for path in (target, target.with_suffix(".progress.json")):
        try:
            value = read(path)
            if isinstance(value, dict):
                return sanitize(value)
        except (OSError, ValueError):
            pass
    return {}


def normalize(raw, run, settings, elapsed, peak, cause, returncode, free):
    raw = sanitize(raw)
    limit = settings["time_limit_s"]
    if raw:
        for key, expected in (
            ("method", run["configuration"]),
            ("instance_id", run["instance_id"]),
            ("seed", run["seed"]),
            ("time_limit_s", limit),
            ("configuration", run["effective_configuration"]),
        ):
            if raw.get(key) != expected:
                raise ValueError(
                    "Worker record identity/configuration mismatch: " + key
                )
        raw["worker_method"] = raw["method"]
        raw["worker_configuration"] = raw["configuration"]
    trace, best = [], None
    for point in sorted(
        raw.get("trace", []), key=lambda row: row.get("total_s", math.inf)
    ):
        value, at = point.get("cardinality"), point.get("total_s")
        if (
            cardinality(value)
            and finite(at)
            and 0 <= at <= limit
            and (best is None or value < best)
        ):
            trace.append(
                dict(total_s=at, cardinality=value, origin=point.get("origin"))
            )
            best = value
    lowers = [
        point
        for point in raw.get("lower_bound_trace", [])
        if cardinality(point.get("value"))
        and finite(point.get("total_s"))
        and 0 <= point["total_s"] <= limit
    ]
    lower = max((point["value"] for point in lowers), default=None)
    if (
        cardinality(raw.get("lower_bound"))
        and finite(raw.get("lower_bound_total_s"))
        and 0 <= raw["lower_bound_total_s"] <= limit
    ):
        lower = max(lower or 0, raw["lower_bound"])
    proof_at = raw.get("optimality_certificate_total_s", raw.get("proof_time_s"))
    own = (
        bool(trace)
        and bool(raw.get("own_optimality_certificate"))
        and finite(proof_at)
        and 0 <= proof_at <= limit
    )
    if own and raw.get("lower_bound") != best:
        raise ValueError("Certificate does not match verified incumbent")
    if lower is not None and best is not None and lower > best:
        raise ValueError("Reliable lower bound exceeds verified incumbent")
    if cause:
        termination = cause
    elif raw.get("outcome") == "memory_limit":
        termination = "address_space_limit"
    elif returncode not in (0, None) or not raw:
        termination = "worker_error"
    else:
        termination = raw.get("termination", "completed")
    errors = termination == "worker_error" or raw.get("outcome") == "error"
    eligible = termination not in ENV_FAILURES and not errors
    if not own:
        for field in (
            "minimum_cardinality",
            "proof_kind",
            "optimality_certificate_total_s",
            "proof_time_s",
        ):
            raw.pop(field, None)
    raw.update(
        run,
        schema="arithdiag-result-v1",
        trace=trace,
        lower_bound_trace=lowers,
        best_cardinality=best,
        has_verified_feasible=bool(trace),
        first_feasible_total_s=trace[0]["total_s"] if trace else None,
        best_total_s=trace[-1]["total_s"] if trace else None,
        lower_bound=lower,
        own_optimality_certificate=own,
        proof_time_s=proof_at if own else None,
        process_wall_s=elapsed,
        peak_rss_mib=peak,
        worker_exit_code=returncode,
        termination=termination,
        score_eligible=eligible,
        outcome=(
            "environment_interrupted"
            if termination in ENV_FAILURES
            else (
                "error"
                if errors
                else (
                    "memory_limit"
                    if termination in ("memory_limit", "address_space_limit")
                    else (
                        "optimal_certified"
                        if own
                        else "verified_feasible" if trace else "unknown"
                    )
                )
            )
        ),
        host_available_before_gib=free,
        time_limit_s=limit,
        budget_overrun_s=max(0.0, elapsed - limit),
        completed_utc=utc(),
        diagnosis_export=False,
        assignment_export=False,
        raw_streams_persisted=False,
        external_reference_stopping=False,
        checkpoints={
            str(at): min(
                (point["cardinality"] for point in trace if point["total_s"] <= at),
                default=None,
            )
            for at in (1, 5, 10, 30, 60, 120, 300)
            if at <= limit
        },
    )
    return raw


def cleanup_work(out, directory):
    directory = Path(directory).resolve()
    base = (out / "work").resolve()
    if (
        not directory.is_relative_to(base)
        or len(directory.relative_to(base).parts) != 2
    ):
        raise ValueError("Refusing non-attempt cleanup: " + str(directory))
    if directory.exists():
        shutil.rmtree(directory)


def recover(out, manifest, manifest_sha):
    recovered = 0
    for path in sorted((out / "attempts").glob("*/*.json")):
        attempt = read(path)
        if attempt.get("attempt_status") != "started":
            continue
        token = attempt["attempt_id"]
        kill_owned(token)
        # SIGKILL delivery precedes cleanup; check ownership tokens until gone.
        until = time.monotonic() + 5
        while own_groups(token) and time.monotonic() < until:
            time.sleep(0.02)
        if own_groups(token):
            raise RuntimeError("Recovered worker descendants remain alive")
        run = next(
            row for row in manifest["plan"] if row["run_id"] == attempt["run_id"]
        )
        run = dict(run, affinity_cpu=attempt.get("affinity_cpu", run["affinity_cpu"]))
        directory = out / "work" / run["run_id"] / token
        row = normalize(
            read_worker(directory / "worker.json"),
            run,
            manifest["settings"],
            0.0,
            attempt.get("peak_rss_mib", 0.0),
            "controller_recovered_interrupted_attempt",
            None,
            attempt.get("host_available_before_gib"),
        )
        row.update(
            attempt_id=token,
            attempt_status="finished",
            started_utc=attempt["started_utc"],
            source_manifest_sha256=manifest_sha,
            recovered_utc=utc(),
        )
        save(path, row)
        cleanup_work(out, directory)
        recovered += 1
    return recovered


def execute(out, manifest):
    check(manifest)
    settings = manifest["settings"]
    manifest_sha = sha(out / "manifest.json")
    recover(out, manifest, manifest_sha)
    completed = {}
    plan_by_id = {row["run_id"]: row for row in manifest["plan"]}
    for path in (out / "records").glob("*.json"):
        row = read(path)
        if (
            row.get("source_manifest_sha256") != manifest_sha
            or row["run_id"] not in plan_by_id
        ):
            raise ValueError("Foreign retained record")
        if row["score_eligible"]:
            completed[row["run_id"]] = row
    environment_event_id = str(uuid.uuid4())
    save(out / "environments" / (environment_event_id + ".json"), environment())
    previous_status = (
        read(out / "status.json") if (out / "status.json").is_file() else {}
    )
    if previous_status.get("environment_event_id"):
        save(
            out
            / "controller-events"
            / (previous_status["environment_event_id"] + ".json"),
            previous_status,
        )
    status = dict(
        state="running",
        controller_pid=os.getpid(),
        started_utc=utc(),
        total_runs=len(manifest["plan"]),
        completed_runs=len(completed),
        peak_concurrency=previous_status.get("peak_concurrency", 0),
        peak_unreaped_attempts=previous_status.get("peak_unreaped_attempts", 0),
        concurrency_observations=0,
        environment_event_id=environment_event_id,
        active_runs=[],
        min_host_available_gib=None,
        rss_sampling_max_gap_s=previous_status.get("rss_sampling_max_gap_s", 0.0),
        rss_scan_max_s=previous_status.get("rss_scan_max_s", 0.0),
        interrupted_attempts=0,
    )
    active = {}
    selector = selectors.DefaultSelector()
    failure = None
    wanted_stop = [None]
    old_handlers = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        old_handlers[number] = signal.signal(
            number, lambda signum, frame: wanted_stop.__setitem__(0, "interrupted")
        )
    last_sample = time.perf_counter()
    next_host = last_sample
    next_status = last_sample
    wave_numbers = sorted({row["wave"] for row in manifest["plan"]})

    def observe_concurrency():
        live = sum(item["process"].poll() is None for item in active.values())
        status["peak_concurrency"] = max(status["peak_concurrency"], live)
        status["peak_unreaped_attempts"] = max(
            status["peak_unreaped_attempts"], len(active)
        )
        status["concurrency_observations"] += 1
        status["last_live_worker_count"] = live
        assigned = [item["run"]["affinity_cpu"] for item in active.values()]
        if len(set(assigned)) != len(assigned):
            raise RuntimeError("Concurrent CPU collision")
        status["cpu_collisions_observed"] = 0

    def wls_can_start(run):
        if not run["method"] == "ArithDiag-G":
            return True
        path = ROOT / ".state/wls-leases.json"
        leases = read(path) if path.exists() else []
        return sum(r["until_unix"] > time.time() for r in leases) < settings.get(
            "wls_max_sessions", 2
        )

    def start(run):
        nonlocal failure
        used = {item["run"]["affinity_cpu"] for item in active.values()}
        if len(used) != len(active):
            raise RuntimeError("Active workers share a CPU")
        free_cpus = [cpu for cpu in settings["cpus"] if cpu not in used]
        if not free_cpus:
            raise RuntimeError("No unoccupied configured CPU")
        run = dict(
            run,
            affinity_cpu=(
                run["affinity_cpu"]
                if run["affinity_cpu"] in free_cpus
                else free_cpus[0]
            ),
        )
        free = None
        try:
            free = available_gib()
            cause = (
                "host_memory_low_before_launch"
                if free < settings["host_start_min_gib"]
                else None
            )
        except Exception:
            cause = "host_memory_check_failed_before_launch"
        token = str(uuid.uuid4())
        directory = out / "work" / run["run_id"] / token
        directory.mkdir(parents=True)
        target = directory / "worker.json"
        attempt_path = out / "attempts" / run["run_id"] / (token + ".json")
        header = dict(
            run,
            attempt_id=token,
            attempt_status="started",
            score_eligible=False,
            started_utc=utc(),
            host_available_before_gib=free,
            environment_event_id=environment_event_id,
            source_manifest_sha256=manifest_sha,
        )
        save(attempt_path, header)
        if cause:
            row = normalize({}, run, settings, 0, 0, cause, None, free)
            row.update(header, attempt_status="finished", termination=cause)
            save(attempt_path, row)
            cleanup_work(out, directory)
            failure = cause
            return
        tick = time.perf_counter()
        start_unix = time.time()
        if run["method"] == "ArithDiag-G":
            lease_path = ROOT / ".state/wls-leases.json"
            leases = read(lease_path) if lease_path.exists() else []
            leases = [r for r in leases if r["until_unix"] > start_unix]
            leases.append(
                dict(
                    attempt_id=token, until_unix=start_unix + 630, start_unix=start_unix
                )
            )
            save(lease_path, leases)
        header["start_unix"] = start_unix
        env = dict(
            os.environ,
            ARITHDIAG_PROCESS_START_TICK=str(tick),
            ARITHDIAG_AFFINITY_CPU=str(run["affinity_cpu"]),
            ARITHDIAG_ATTEMPT_TOKEN=token,
            ARITHDIAG_DATASET_ROOT=settings["dataset_roots"][run["dataset"]],
            ARITHDIAG_WORK_ROOT=str(directory),
            ARITHDIAG_INTERNAL_BUDGET_POLICY=run["effective_configuration"].get("budget_policy", "fraction50"),
            ARITHDIAG_VARIANT=run.get("variant", "full"),
            TMPDIR=str(directory),
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONHASHSEED="0",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            VECLIB_MAXIMUM_THREADS="1",
        )
        command = worker_command(manifest, run, target)
        if run["method"] not in ("ArithDiag-G", "ArithDiag-LS"):
            raise ValueError("Unsupported ArithDiag backend")
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except Exception as exc:
            row = normalize(
                {},
                run,
                settings,
                time.perf_counter() - tick,
                0.0,
                "controller_launch_error",
                None,
                free,
            )
            row.update(
                header,
                attempt_status="finished",
                controller_error_class=type(exc).__name__,
            )
            save(attempt_path, row)
            cleanup_work(out, directory)
            failure = "controller_launch_error"
            return
        header.update(pid=process.pid, pgid=process.pid, process_start_tick=tick)
        active[process.pid] = dict(
            run=run,
            process=process,
            target=target,
            directory=directory,
            token=token,
            attempt_path=attempt_path,
            header=header,
            start=tick,
            deadline=tick + settings["time_limit_s"],
            peak=0.0,
            cause=None,
            allocator_failure=False,
            allocator_overlap=b"",
            members=[],
            rss_group_sample_count=0,
            rss_group_resident_sample_count=0,
            rss_leader_initial_mib=None,
        )
        # Register ownership before any diagnostic or NFS operation can fail.
        header["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, process.pid)
        initial_rss = leader_rss(process.pid)
        active[process.pid]["rss_leader_initial_mib"] = initial_rss
        active[process.pid]["peak"] = initial_rss or 0.0
        observe_concurrency()
        save(attempt_path, header)

    def finish(pid, cause=None):
        nonlocal failure
        item = active[pid]
        process = item["process"]
        if cause or process.poll() is None:
            kill_owned(item["token"])
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            kill_owned(item["token"])
            process.wait(timeout=5)
        # A normal parent exit must not leave its solver descendants running.
        kill_owned(item["token"])
        cleanup_until = time.monotonic() + 5
        while own_groups(item["token"]) and time.monotonic() < cleanup_until:
            time.sleep(0.02)
        cleanup_failed = bool(own_groups(item["token"]))
        for stream in (process.stdout, process.stderr):
            # select()+poll() has a real exit race: text written after the last
            # ready snapshot is still in the pipe even though poll() sees exit.
            # The session has ended now, so no future solver output is waited on.
            consume_pipe(item, stream, max_chunks=1024)
            try:
                selector.unregister(stream)
            except KeyError:
                pass
            stream.close()
        raw = read_worker(item["target"])
        if item["run"]["method"] == "ArithDiag-G":
            lease_path = ROOT / ".state/wls-leases.json"
            leases = read(lease_path)
            for lease in leases:
                if (
                    lease.get("attempt_id") == item["token"]
                    and raw.get("license_ready_total_s") is not None
                ):
                    lease["until_unix"] = (
                        lease["start_unix"] + raw["license_ready_total_s"] + 305
                    )
            if raw.get("license_session_started") is False:
                leases = [
                    lease
                    for lease in leases
                    if lease.get("attempt_id") != item["token"]
                ]
            save(lease_path, leases)
        if not cause and not item["target"].is_file() and item["allocator_failure"]:
            if raw:
                raw.update(outcome="memory_limit", termination="address_space_limit")
            else:
                cause = "address_space_limit"
        elapsed = time.perf_counter() - item["start"]
        try:
            row = normalize(
                raw,
                item["run"],
                settings,
                elapsed,
                item["peak"],
                cause,
                process.returncode,
                item["header"]["host_available_before_gib"],
            )
        except Exception as exc:
            row = normalize(
                {},
                item["run"],
                settings,
                elapsed,
                item["peak"],
                "worker_error",
                process.returncode,
                item["header"]["host_available_before_gib"],
            )
            row["record_validation_error"] = str(exc)
        row.update(
            attempt_id=item["token"],
            attempt_status="finished",
            started_utc=item["header"]["started_utc"],
            source_manifest_sha256=manifest_sha,
            environment_event_id=environment_event_id,
            allocator_failure_detected=item["allocator_failure"],
            rss_group_sample_count=item["rss_group_sample_count"],
            rss_group_resident_sample_count=item["rss_group_resident_sample_count"],
            rss_leader_initial_mib=item["rss_leader_initial_mib"],
            rss_peak_is_observed=item["peak"] > 0,
            exit_observed_after_deadline=time.perf_counter() >= item["deadline"],
            rss_peak_measurement_scope="periodic process-group RSS plus initial leader lower-bound sample",
        )
        if item["peak"] <= 0:
            row["peak_rss_mib"] = None
        if cleanup_failed:
            row.update(
                termination="worker_cleanup_failed",
                outcome="error",
                score_eligible=False,
            )
        save(item["attempt_path"], row)
        if row["score_eligible"]:
            save(out / "records" / (row["run_id"] + ".json"), row)
            completed[row["run_id"]] = row
        else:
            status["interrupted_attempts"] += 1
            failure = failure or row["termination"]
        if not cleanup_failed:
            cleanup_work(out, item["directory"])
        del active[pid]
        print(
            json.dumps(
                dict(
                    completed=len(completed),
                    total=len(manifest["plan"]),
                    method=row["method"],
                    instance_id=row["instance_id"],
                    seed=row["seed"],
                    U=row["best_cardinality"],
                    L=row["lower_bound"],
                    proof_s=row["proof_time_s"],
                    wall_s=row["process_wall_s"],
                    rss_mib=row["peak_rss_mib"],
                    termination=row["termination"],
                )
            ),
            flush=True,
        )

    try:
        for wave in wave_numbers:
            queue = deque(
                row
                for row in manifest["plan"]
                if row["wave"] == wave and row["run_id"] not in completed
            )
            status["wave"] = wave
            while queue or active:
                now = time.perf_counter()
                if wanted_stop[0]:
                    failure = wanted_stop[0]
                if now >= next_host:
                    try:
                        free = available_gib()
                        status["min_host_available_gib"] = min(
                            status["min_host_available_gib"] or free, free
                        )
                        if free < settings["host_stop_min_gib"]:
                            failure = "host_memory_low"
                    except Exception:
                        failure = "host_memory_check_failed"
                    next_host = now + settings["host_check_period_s"]
                if failure:
                    break
                # Bound launches per iteration so existing workers retain timely deadlines.
                if queue and len(active) < settings["concurrency"]:
                    eligible = next((r for r in queue if wls_can_start(r)), None)
                    if eligible is not None:
                        queue.remove(eligible)
                        start(eligible)
                for key, _ in selector.select(0):
                    if key.data not in active:
                        continue
                    if consume_pipe(active[key.data], key.fileobj):
                        selector.unregister(key.fileobj)
                now = time.perf_counter()
                if now - last_sample >= settings["rss_sampling_period_s"]:
                    gap = now - last_sample
                    tick = time.perf_counter()
                    totals, members = rss_groups(set(active))
                    status["rss_scan_max_s"] = max(
                        status["rss_scan_max_s"], time.perf_counter() - tick
                    )
                    status["rss_sampling_max_gap_s"] = max(
                        status["rss_sampling_max_gap_s"], gap
                    )
                    observe_concurrency()
                    for pid, item in active.items():
                        item["peak"] = max(item["peak"], totals[pid])
                        item["members"] = members[pid]
                        item["rss_group_sample_count"] += 1
                        item["rss_group_resident_sample_count"] += int(totals[pid] > 0)
                        if item["peak"] > settings["rss_limit_mib"]:
                            item["cause"] = "memory_limit"
                    last_sample = now
                for pid in list(active):
                    item = active[pid]
                    if item["cause"]:
                        finish(pid, item["cause"])
                    elif item["process"].poll() is not None:
                        finish(pid)
                    elif time.perf_counter() >= item["deadline"]:
                        finish(pid, "budget_exhausted")
                if time.perf_counter() >= next_status:
                    status.update(
                        completed_runs=len(completed),
                        active_runs=[
                            dict(
                                run_id=item["run"]["run_id"],
                                attempt_id=item["token"],
                                pid=pid,
                                affinity_cpu=item["run"]["affinity_cpu"],
                                peak_rss_mib=item["peak"],
                            )
                            for pid, item in active.items()
                        ],
                        updated_utc=utc(),
                    )
                    save(out / "status.json", status)
                    next_status = time.perf_counter() + 1
                if (
                    queue
                    and len(active) < settings["concurrency"]
                    and any(wls_can_start(r) for r in queue)
                ):
                    continue
                time.sleep(0.005)
            if failure:
                break
        status["state"] = "stopped" if failure else "completed"
        status["reason"] = failure
    except BaseException as exc:
        failure = "controller_guard_failed"
        status.update(
            state="stopped",
            reason=failure,
            controller_error_class=type(exc).__name__,
            controller_error=str(exc),
        )
        raise
    finally:
        # Stop every owned session before spending time recording/cleaning any one.
        for item in active.values():
            kill_owned(item["token"])
        for pid in list(active):
            finish(pid, failure or "interrupted")
        selector.close()
        status.update(completed_runs=len(completed), active_runs=[], updated_utc=utc())
        if failure:
            status.update(state="stopped", reason=failure)
        save(out / "status.json", status)
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    check(manifest)
    return status


def worker_command(manifest, run, target):
    settings = manifest["settings"]
    return [
        settings["python"],
        "-B",
        str(ROOT / "worker_bootstrap.py"),
        str(settings["address_space_limit_mib"]),
        run["method"],
        run["dataset"],
        run["instance_id"],
        str(settings["time_limit_s"]),
        str(run["seed"]),
        str(target),
    ]
