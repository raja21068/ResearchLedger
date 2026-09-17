import json
import subprocess
import sys

import pytest

from researchledger.reproduce import _as_number, _compare_metrics, _read_metrics, render, reproduce
from researchledger.runner import run_command
from researchledger.workspace import init_workspace


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(root):
    _git(["init"], root)
    _git(["config", "user.email", "test@example.com"], root)
    _git(["config", "user.name", "Test"], root)


def test_reproduce_isolated_worktree_matches_within_tolerance(tmp_path):
    ws = init_workspace(tmp_path)
    _init_git_repo(tmp_path)

    (tmp_path / "experiment.py").write_text(
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': 0.9137}))\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "add experiment"], tmp_path)

    # A relative command path, run with cwd=tmp_path, so that re-running with
    # cwd=<worktree> actually executes the worktree's own checked-out copy —
    # that's what isolation is actually testing.
    manifest = run_command(ws, [sys.executable, "experiment.py"], cwd=tmp_path)
    assert manifest["git"]["commit"] is not None

    result = reproduce(ws, manifest["run_id"], tolerance=1e-3)

    assert result.isolated is True
    assert result.reproduced is True
    assert result.metric_comparisons
    assert all(c.matches for c in result.metric_comparisons)


def test_reproduce_without_git_falls_back_to_in_place(tmp_path):
    ws = init_workspace(tmp_path)  # deliberately not a git repo
    manifest = run_command(ws, [sys.executable, "-c", "pass"])

    result = reproduce(ws, manifest["run_id"])

    assert result.isolated is False
    assert "git" in result.isolation_note


def test_reproduce_no_isolate_flag_skips_worktree_even_in_a_repo(tmp_path):
    ws = init_workspace(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)

    manifest = run_command(ws, [sys.executable, "-c", "pass"], cwd=tmp_path)
    result = reproduce(ws, manifest["run_id"], isolate=False)
    assert result.isolated is False
    assert result.isolation_note == "re-ran in place (no isolation)"


def test_reproduce_repeat_tolerates_noisy_metrics_within_the_observed_spread(tmp_path):
    ws = init_workspace(tmp_path)
    _init_git_repo(tmp_path)

    # A "noisy" script whose result varies slightly by a small random jitter
    # each run — a fixed tight tolerance would flag this as not reproduced,
    # but --repeat should recognize the original falls within the spread.
    (tmp_path / "noisy.py").write_text(
        "import os, json, pathlib, random\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "value = 0.9 + random.uniform(-0.01, 0.01)\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': value}))\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "add noisy"], tmp_path)

    manifest = run_command(ws, [sys.executable, "noisy.py"], cwd=tmp_path)
    result = reproduce(ws, manifest["run_id"], tolerance=1e-6, repeat=8, z_score=3.0)

    assert len(result.new_run_ids) == 8
    assert result.metric_comparisons
    accuracy = next(c for c in result.metric_comparisons if c.key == "accuracy")
    assert accuracy.stddev is not None
    assert len(accuracy.samples) == 8


def test_reproduce_missing_run_raises(tmp_path):
    ws = init_workspace(tmp_path)
    with pytest.raises(FileNotFoundError):
        reproduce(ws, "R9999")


def test_read_metrics_missing_file_returns_none(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    assert _read_metrics(ws, "R0001", {"metrics": "metrics.json"}) is None


def test_read_metrics_corrupt_json_returns_none(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text("{not valid", encoding="utf-8")
    assert _read_metrics(ws, "R0001", {"metrics": "metrics.json"}) is None


def test_as_number_rejects_bools_and_strings():
    assert _as_number(True) is None
    assert _as_number(False) is None
    assert _as_number("0.5") is None
    assert _as_number(0.5) == 0.5
    assert _as_number(3) == 3.0


def test_compare_metrics_falls_back_to_exact_equality_for_non_numeric_values():
    comparisons = _compare_metrics({"label": "ok"}, [{"label": "ok"}, {"label": "different"}], 1e-3, 2.0)
    comparison = comparisons[0]
    assert comparison.matches is False  # not every reproduced sample matched exactly
    assert comparison.stddev is None


def test_render_with_repeat_and_artifacts_shows_stddev_and_artifact_line():
    from researchledger.reproduce import MetricComparison, ReproductionResult

    result = ReproductionResult(
        original_run_id="R0001",
        new_run_ids=["R0002", "R0003"],
        isolated=True,
        isolation_note="isolated git worktree at commit abc123",
        repeat=2,
        metric_comparisons=[MetricComparison("accuracy", 0.9, 0.901, True, [0.900, 0.902], 0.001)],
        artifact_total=3,
        artifact_matched=3,
        reproduced=True,
    )
    text = render(result, tolerance=1e-3)
    assert "Repeated: 2x" in text
    assert "stddev" in text
    assert "z·stddev" in text
    assert "Artifacts: 3/3 verified" in text


def test_reproduce_current_workspace_not_a_git_repo_falls_back(tmp_path):
    """The original run recorded a commit, but by the time we reproduce it
    the workspace itself isn't a git repo anymore (e.g. .git was removed) —
    a distinct case from the original run never having had a commit."""
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "2.0", "run_id": "R0001", "status": "completed",
        "started_at": "t", "finished_at": "t",
        "command": f"{sys.executable} -c pass", "command_argv": [sys.executable, "-c", "pass"],
        "working_directory": ".", "git": {"commit": "deadbeef", "dirty": False},
        "randomness": {"seed": None}, "targets": {"claims": [], "plan": None},
        "environment": "environment.json", "artifacts": [], "inputs": [],
        "timeout": None, "attempts": [], "exit_code": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = reproduce(ws, "R0001")
    assert result.isolated is False
    assert "not inside a git repository" in result.isolation_note


def test_reproduce_worktree_add_failure_falls_back_to_in_place(tmp_path, monkeypatch):
    ws = init_workspace(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)

    manifest = run_command(ws, [sys.executable, "-c", "pass"], cwd=tmp_path)

    real_run = subprocess.run

    def _fail_worktree_add(cmd, **kwargs):
        if cmd[:3] == ["git", "worktree", "add"]:
            raise subprocess.CalledProcessError(1, cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fail_worktree_add)
    result = reproduce(ws, manifest["run_id"])
    assert result.isolated is False
    assert "could not create an isolated worktree" in result.isolation_note


def test_reproduce_rejects_repeat_below_one(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"])
    try:
        reproduce(ws, manifest["run_id"], repeat=0)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_reproduce_detects_a_real_metric_drift(tmp_path):
    ws = init_workspace(tmp_path)
    _init_git_repo(tmp_path)

    # A "run" whose result depends on wall-clock time, so the reproduction's
    # metric will differ from the original by more than a tight tolerance —
    # this is what a genuinely non-reproducible run should look like.
    (tmp_path / "flaky.py").write_text(
        "import os, json, pathlib, time\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'value': time.time()}))\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "add flaky"], tmp_path)

    manifest = run_command(ws, [sys.executable, "flaky.py"], cwd=tmp_path)
    result = reproduce(ws, manifest["run_id"], tolerance=1e-6)

    assert result.reproduced is False
    assert any(not c.matches for c in result.metric_comparisons)
