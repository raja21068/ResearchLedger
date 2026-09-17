"""`researchledger reproduce <run_id>`: re-execute a run's exact command,
isolated in a fresh git worktree checked out at its original commit when
possible, then compare the new metrics/artifacts against the original. This
is what makes "reproducible" a checked fact instead of a stored command
string — see reference/run-ledger.md.

Isolation requires the original run to have a recorded git commit and the
current workspace to actually be a git repository; otherwise this falls
back to re-running in place and says so plainly rather than silently
downgrading the guarantee.

`--repeat N` runs the reproduction N times (inside the same isolated
worktree, checked out once) and compares the original value against the
*distribution* of reproduced values — `mean ± max(tolerance, z * stddev)` —
instead of a single point. A fixed epsilon is the wrong tool for anything
with real run-to-run noise (non-deterministic GPU ops, sampling); `repeat=1`
degenerates to the old single-value tolerance check exactly (stddev is 0).
"""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .environment import git_info
from .runner import run_command
from .workspace import Workspace

DEFAULT_TOLERANCE = 1e-3
DEFAULT_Z_SCORE = 2.0


@dataclass
class MetricComparison:
    key: str
    original: object
    reproduced: object  # the mean of the reproduced samples (or the lone value when repeat=1)
    matches: bool
    samples: list[float] = field(default_factory=list)
    stddev: float | None = None


@dataclass
class ReproductionResult:
    original_run_id: str
    new_run_ids: list[str]
    isolated: bool
    isolation_note: str
    repeat: int = 1
    metric_comparisons: list[MetricComparison] = field(default_factory=list)
    artifact_total: int = 0
    artifact_matched: int = 0
    reproduced: bool = False


def _load_manifest(ws: Workspace, run_id: str) -> dict:
    path = ws.runs_dir / run_id / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No such run: {run_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_metrics(ws: Workspace, run_id: str, manifest: dict) -> dict | None:
    name = manifest.get("metrics")
    if not name:
        return None
    path = ws.runs_dir / run_id / name
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _compare_metrics(
    original: dict, reproduced_runs: list[dict], tolerance: float, z_score: float
) -> list[MetricComparison]:
    keys: set[str] = set(original)
    for r in reproduced_runs:
        keys |= set(r)

    comparisons = []
    for key in sorted(keys):
        original_value = original.get(key)
        original_number = _as_number(original_value)
        samples = [_as_number(r.get(key)) for r in reproduced_runs]
        numeric_samples = [s for s in samples if s is not None]

        if original_number is not None and numeric_samples and len(numeric_samples) == len(reproduced_runs):
            mean = statistics.fmean(numeric_samples)
            stddev = statistics.stdev(numeric_samples) if len(numeric_samples) > 1 else 0.0
            allowed = max(tolerance, z_score * stddev)
            matches = abs(original_number - mean) <= allowed
            comparisons.append(MetricComparison(key, original_value, mean, matches, numeric_samples, stddev))
        else:
            reproduced_value = reproduced_runs[-1].get(key) if reproduced_runs else None
            matches = all(r.get(key) == original_value for r in reproduced_runs)
            comparisons.append(MetricComparison(key, original_value, reproduced_value, matches))
    return comparisons


def _try_isolated_worktree(ws: Workspace, commit: str) -> tuple[Path | None, Path | None, str]:
    """Returns (worktree_dir, tempdir_to_clean, note). worktree_dir is None
    if isolation wasn't possible."""
    current_git = git_info(ws.root)
    if not current_git.get("commit"):
        return None, None, "workspace is not inside a git repository; re-ran in place"

    parent = Path(tempfile.mkdtemp(prefix="researchledger-reproduce-"))
    worktree_dir = parent / "worktree"
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_dir), commit],
            cwd=str(ws.root),
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        shutil.rmtree(parent, ignore_errors=True)
        return None, None, f"could not create an isolated worktree ({exc}); re-ran in place"
    return worktree_dir, parent, f"isolated git worktree at commit {commit[:12]}"


def _cleanup_worktree(ws: Workspace, worktree_dir: Path, tempdir: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=str(ws.root),
        capture_output=True,
        text=True,
    )
    shutil.rmtree(tempdir, ignore_errors=True)


def reproduce(
    ws: Workspace,
    run_id: str,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    isolate: bool = True,
    keep_worktree: bool = False,
    repeat: int = 1,
    z_score: float = DEFAULT_Z_SCORE,
) -> ReproductionResult:
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    manifest = _load_manifest(ws, run_id)
    command = manifest["command_argv"]
    seed = (manifest.get("randomness") or {}).get("seed")
    targets = manifest.get("targets") or {}
    commit = (manifest.get("git") or {}).get("commit")

    worktree_dir: Path | None = None
    tempdir: Path | None = None
    isolated = False
    isolation_note = "re-ran in place (no isolation)"

    if isolate and commit:
        worktree_dir, tempdir, isolation_note = _try_isolated_worktree(ws, commit)
        isolated = worktree_dir is not None
    elif isolate and not commit:
        isolation_note = "original run had no recorded git commit; re-ran in place"

    try:
        new_manifests = [
            run_command(
                ws,
                command,
                seed=seed,
                claims=targets.get("claims") or [],
                plan=targets.get("plan"),
                cwd=worktree_dir,
            )
            for _ in range(repeat)
        ]
    finally:
        if worktree_dir is not None and tempdir is not None and not keep_worktree:
            _cleanup_worktree(ws, worktree_dir, tempdir)

    result = ReproductionResult(
        original_run_id=run_id,
        new_run_ids=[m["run_id"] for m in new_manifests],
        isolated=isolated,
        isolation_note=isolation_note,
        repeat=repeat,
    )

    original_metrics = _read_metrics(ws, run_id, manifest)
    reproduced_metrics = [
        metrics
        for m in new_manifests
        if (metrics := _read_metrics(ws, m["run_id"], m)) is not None
    ]
    if original_metrics is not None and len(reproduced_metrics) == len(new_manifests):
        result.metric_comparisons = _compare_metrics(original_metrics, reproduced_metrics, tolerance, z_score)

    # Artifact hashes are compared against the last reproduction — unlike
    # metrics, file outputs are expected to be exactly deterministic, not
    # statistically close, so there's no distribution to average over.
    last_manifest = new_manifests[-1]
    original_artifacts = {a["path"]: a["sha256"] for a in manifest.get("artifacts", [])}
    new_artifacts = {a["path"]: a["sha256"] for a in last_manifest.get("artifacts", [])}
    result.artifact_total = len(original_artifacts)
    result.artifact_matched = sum(1 for path, sha in original_artifacts.items() if new_artifacts.get(path) == sha)

    metrics_ok = all(c.matches for c in result.metric_comparisons) if result.metric_comparisons else True
    artifacts_ok = result.artifact_matched == result.artifact_total
    all_exited_clean = all(m["exit_code"] == 0 for m in new_manifests)
    result.reproduced = all_exited_clean and metrics_ok and artifacts_ok
    return result


def render(result: ReproductionResult, tolerance: float) -> str:
    new_ids = " -> ".join(result.new_run_ids)
    lines = [f"Reproduction {result.original_run_id} -> {new_ids}", ""]
    lines.append(f"Isolation: {result.isolation_note}")
    if result.repeat > 1:
        lines.append(f"Repeated: {result.repeat}x")

    if result.metric_comparisons:
        lines.append("")
        lines.append("Original metric:")
        for c in result.metric_comparisons:
            lines.append(f"  {c.key} = {c.original}")
        lines.append("")
        lines.append("Reproduced:" if result.repeat == 1 else f"Reproduced (mean of {result.repeat}):")
        for c in result.metric_comparisons:
            mark = "✓" if c.matches else "✗"
            if c.stddev is not None and result.repeat > 1:
                lines.append(f"  {c.key} = {c.reproduced:.6g} (stddev {c.stddev:.6g}) {mark}")
            else:
                lines.append(f"  {c.key} = {c.reproduced} {mark}")
        lines.append("")
        if result.repeat > 1:
            lines.append(f"Tolerance: ±max({tolerance}, z·stddev)")
        else:
            lines.append(f"Tolerance: ±{tolerance}")

    lines.append("")
    lines.append(f"Result: {'REPRODUCED ✓' if result.reproduced else 'NOT REPRODUCED ✗'}")

    if result.artifact_total:
        lines.append("")
        lines.append(f"Artifacts: {result.artifact_matched}/{result.artifact_total} verified")

    return "\n".join(lines)
