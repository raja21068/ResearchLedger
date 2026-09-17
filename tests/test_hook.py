import json
import subprocess
import sys
import time
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "inject_research_context.py"


def _run_hook(payload_text: str):
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_hook_is_silent_outside_a_workspace(tmp_path):
    result = _run_hook(json.dumps({"cwd": str(tmp_path)}))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_hook_never_crashes_on_garbage_stdin():
    result = _run_hook("not json at all {{{")
    assert result.returncode == 0


def test_hook_never_crashes_on_empty_stdin():
    result = _run_hook("")
    assert result.returncode == 0


def test_hook_falls_back_to_scan_without_an_index(tmp_path):
    (tmp_path / "project.md").write_text("---\ntopic: Test project\n---\n", encoding="utf-8")
    result = _run_hook(json.dumps({"cwd": str(tmp_path)}))
    assert result.returncode == 0
    assert "ResearchLedger" in result.stdout
    assert "No cached index yet" in result.stdout
    assert "ConvFusion" not in result.stdout


def test_hook_reads_cached_index_when_present(tmp_path):
    (tmp_path / "project.md").write_text("---\ntopic: Test project\n---\n", encoding="utf-8")
    index_dir = tmp_path / ".researchledger"
    index_dir.mkdir()
    index = {
        "schema_version": "2.0",
        "file_counts": {"evidence": 2, "claims": 1, "decisions": 0, "runs": 1, "papers": 0},
        "counts": {"claims": 1, "evidence": 2, "runs": 1, "decisions": 0},
        "evidence_status_counts": {"verified": 1, "checked": 1},
        "claim_status_counts": {"supported": 1},
        "literature_evidence": 0,
        "metrics": {},
        "errors": 0,
        "warnings": 1,
        "top_issues": [{"level": "warning", "code": "RL303", "message": "E002 has no reproduction command"}],
    }
    (index_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    result = _run_hook(json.dumps({"cwd": str(tmp_path)}))
    assert result.returncode == 0
    assert "1 supported / 0 unresolved" in result.stdout
    assert "E002 has no reproduction command" in result.stdout
    assert "Stage:" not in result.stdout  # v1's fixed-stage prescription must be gone


def test_hook_reads_index_quickly_even_with_many_records(tmp_path):
    (tmp_path / "project.md").write_text("---\ntopic: Test project\n---\n", encoding="utf-8")
    index_dir = tmp_path / ".researchledger"
    index_dir.mkdir()
    index = {
        "schema_version": "2.0",
        "file_counts": {"evidence": 5000, "claims": 5000, "decisions": 0, "runs": 5000, "papers": 0},
        "counts": {"claims": 5000, "evidence": 5000, "runs": 5000, "decisions": 0},
        "evidence_status_counts": {"verified": 5000},
        "claim_status_counts": {"supported": 5000},
        "literature_evidence": 0,
        "metrics": {},
        "errors": 0,
        "warnings": 0,
        "top_issues": [],
    }
    (index_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    started = time.monotonic()
    result = _run_hook(json.dumps({"cwd": str(tmp_path)}))
    elapsed = time.monotonic() - started
    assert result.returncode == 0
    # The hook only reads one small JSON file regardless of record count —
    # this bounds process-launch overhead too, so it's generous.
    assert elapsed < 2.0
