"""The execution wrapper: `researchledger run -- <command>`.

This is the one place that selectively reuses AutoResearch's engineering
ideas — execution capture, environment recording, resource controls
(timeout), and a bounded retry loop — without importing its multi-agent
orchestrator. Every run gets an immutable, numbered directory under
research/runs/. The manifest is written by this code, never by an LLM — see
reference/run-ledger.md#do-not-let-an-llm-write-the-manifest.

Concurrency: id allocation and command *execution* are two different
things, and only the first needs to be serialized. `_allocate_run_dir`
grabs the next id under `ledger_lock` and releases it immediately, so
multiple `researchledger run` processes execute their commands fully in
parallel. What can't happen in parallel is *sealing* — computing
`previous_run_hash` and writing manifest.json — because the chain's
correctness depends on seals happening in a well-defined order, one at a
time, each seeing the complete result of every seal before it. `_seal_run`
reacquires `ledger_lock` right before the (fast) write and, while holding
it, *recomputes* the chain tail from every existing manifest on disk rather
than trusting a cached "last tip" value — a cached tip file has its own
crash window (write manifest, die, never update the tip; the next seal
then branches off stale state) and a full scan under the lock is cheap
enough at realistic ledger sizes to just always be right. See
reference/run-ledger.md#tamper-evident-run-chain.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .atomic import atomic_write_json, atomic_write_text
from .environment import capture_env_vars, capture_environment, capture_hardware, environment_digest, git_info
from .hashing import sha256_file, sha256_path
from .workspace import Workspace, ledger_lock, next_id

SCHEMA_VERSION = "2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pump(pipe, file_handle, echo_stream) -> None:
    for line in iter(pipe.readline, ""):
        file_handle.write(line)
        try:
            echo_stream.write(line)
        except (ValueError, OSError):
            pass
    pipe.close()


def _execute_once(
    command: list[str],
    *,
    cwd: Path,
    env: dict,
    stdout_path: Path,
    stderr_path: Path,
    timeout: int | None,
) -> tuple[int, bool]:
    """Run `command` once, teeing stdout/stderr to both the console and log
    files. Returns (exit_code, timed_out)."""
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with open(stdout_path, "w", encoding="utf-8") as out_f, open(
        stderr_path, "w", encoding="utf-8"
    ) as err_f:
        t_out = threading.Thread(target=_pump, args=(process.stdout, out_f, sys.stdout))
        t_err = threading.Thread(target=_pump, args=(process.stderr, err_f, sys.stderr))
        t_out.start()
        t_err.start()
        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait()
            timed_out = True
        t_out.join()
        t_err.join()
    return exit_code, timed_out


def _allocate_run_dir(ws: Workspace) -> tuple[str, Path]:
    ws.runs_dir.mkdir(parents=True, exist_ok=True)
    with ledger_lock(ws):
        run_id = next_id(ws.runs_dir, "R", 4)
        run_dir = ws.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _reconstruct_chain_tail(ws: Workspace) -> str | None:
    """Recomputes which existing run is the current end of the chain, by
    reading every manifest on disk — no cached "tip" file, so there's
    nothing that can go stale relative to the manifests themselves. Must be
    called with `ledger_lock` already held (so nothing else can seal a run
    while this scan is in progress).

    A chain-aware run's hash is "the tail" if no other chain-aware run
    claims it as their `previous_run_hash`. If there are no chain-aware
    runs yet, falls back to the most recently allocated legacy run (or
    `None`, for a brand-new workspace).
    """
    if not ws.runs_dir.exists():
        return None

    chained_hashes: dict[str, str] = {}
    claimed: set[str] = set()
    legacy_run_ids: list[str] = []
    for run_dir in sorted(ws.runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue  # a corrupt, unrelated run must not block sealing a new one
        if "previous_run_hash" in manifest:
            chained_hashes[run_dir.name] = "sha256:" + sha256_file(manifest_path)
            previous = manifest.get("previous_run_hash")
            if previous is not None:
                claimed.add(previous)
        else:
            legacy_run_ids.append(run_dir.name)

    if chained_hashes:
        tails = sorted(h for h in chained_hashes.values() if h not in claimed)
        if tails:
            # Normally exactly one. If more than one (e.g. a prior crash
            # left an unresolved branch on disk), pick deterministically —
            # `researchledger validate` reports the pre-existing branch
            # separately; sealing must still be able to proceed.
            return tails[-1]
    if legacy_run_ids:
        latest_legacy = sorted(legacy_run_ids)[-1]
        return "sha256:" + sha256_file(ws.runs_dir / latest_legacy / "manifest.json")
    return None


def _seal_run(ws: Workspace, run_dir: Path, manifest: dict) -> dict:
    """Commits a run to history: assigns `previous_run_hash` and writes
    manifest.json, both under `ledger_lock` so seals are strictly
    serialized even when the runs producing them executed concurrently."""
    with ledger_lock(ws):
        manifest["previous_run_hash"] = _reconstruct_chain_tail(ws)
        atomic_write_json(run_dir / "manifest.json", manifest)
    return manifest


def run_command(
    ws: Workspace,
    command: list[str],
    *,
    seed: int | None = None,
    claims: list[str] | None = None,
    plan: str | None = None,
    metrics_path: Path | None = None,
    timeout: int | None = None,
    retries: int = 0,
    cwd: Path | None = None,
    env_allowlist: list[str] | None = None,
    data: list[str] | None = None,
) -> dict:
    if not command:
        raise ValueError("run_command requires a non-empty command")

    working_dir = (cwd or Path.cwd()).resolve()

    # Validate --data paths up front, before allocating a run id, so a typo
    # doesn't burn a run number on a doomed invocation.
    resolved_inputs: list[tuple[str, Path]] = []
    for data_path_str in data or []:
        data_path = Path(data_path_str)
        resolved = data_path if data_path.is_absolute() else (working_dir / data_path)
        if not resolved.exists():
            raise ValueError(f"--data path does not exist: {data_path_str}")
        resolved_inputs.append((data_path_str, resolved))

    run_id, run_dir = _allocate_run_dir(ws)
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    child_env = dict(os.environ)
    child_env["RESEARCHLEDGER_RUN_ID"] = run_id
    child_env["RESEARCHLEDGER_RUN_DIR"] = str(run_dir)
    child_env["RESEARCHLEDGER_ARTIFACTS_DIR"] = str(artifacts_dir)

    atomic_write_text(run_dir / "command.txt", shlex.join(command) + "\n")

    started_at = _now()
    attempts = []
    exit_code = -1
    timed_out = False
    max_attempts = max(1, retries + 1)
    for attempt in range(1, max_attempts + 1):
        exit_code, timed_out = _execute_once(
            command,
            cwd=working_dir,
            env=child_env,
            stdout_path=run_dir / "stdout.log",
            stderr_path=run_dir / "stderr.log",
            timeout=timeout,
        )
        attempts.append({"attempt": attempt, "exit_code": exit_code, "timed_out": timed_out})
        if exit_code == 0:
            break
    finished_at = _now()

    if timed_out:
        status = "timeout"
    elif exit_code == 0:
        status = "completed"
    else:
        status = "failed"

    environment = capture_environment()
    atomic_write_json(run_dir / "environment.json", environment)
    digest = environment_digest(environment)
    hardware = capture_hardware()
    env_vars = capture_env_vars(env_allowlist or [])

    metrics_name = None
    if metrics_path is not None and Path(metrics_path).exists():
        atomic_write_text(run_dir / "metrics.json", Path(metrics_path).read_text(encoding="utf-8"))
        metrics_name = "metrics.json"
    elif (run_dir / "metrics.json").exists():
        # The command wrote directly into $RESEARCHLEDGER_RUN_DIR/metrics.json.
        metrics_name = "metrics.json"
    metrics_sha256 = sha256_file(run_dir / metrics_name) if metrics_name else None

    artifacts = []
    if artifacts_dir.exists():
        for artifact_path in sorted(artifacts_dir.rglob("*")):
            if artifact_path.is_file():
                rel = artifact_path.relative_to(run_dir).as_posix()
                artifacts.append({"path": rel, "sha256": sha256_file(artifact_path)})

    inputs = [{"path": path_str, "sha256": sha256_path(resolved)} for path_str, resolved in resolved_inputs]

    try:
        working_dir_repr = str(working_dir.relative_to(ws.root))
    except ValueError:
        working_dir_repr = str(working_dir)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "command": shlex.join(command),
        "command_argv": command,
        "working_directory": working_dir_repr,
        "git": git_info(working_dir),
        "randomness": {"seed": seed},
        "targets": {"claims": claims or [], "plan": plan},
        "environment": "environment.json",
        "environment_digest": digest,
        "hardware": hardware,
        "env_vars": env_vars,
        "metrics": metrics_name,
        "metrics_sha256": metrics_sha256,
        "inputs": inputs,
        "artifacts": artifacts,
        "timeout": timeout,
        "attempts": attempts,
        "exit_code": exit_code,
    }
    return _seal_run(ws, run_dir, manifest)
