"""End-to-end CLI tests: drives `researchledger.cli.main()` the same way a
shell would, through the exact walkthrough from the v2 spec — init, run,
evidence create, trace, validate, report, migrate — so the wiring between
subcommands is exercised, not just each module in isolation.
"""

import json
import subprocess
import sys

import pytest

from researchledger.cli import main


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    return tmp_path


def test_full_walkthrough(workspace, capsys):
    script = workspace / "experiment.py"
    script.write_text(
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': 0.9137}))\n",
        encoding="utf-8",
    )

    exit_code = main(["run", "--seed", "42", "--", sys.executable, "experiment.py"])
    assert exit_code == 0
    run_id = "R0001"
    assert (workspace / "research" / "runs" / run_id / "manifest.json").exists()

    (workspace / "research" / "claims").mkdir(parents=True, exist_ok=True)
    claim_path = workspace / "research" / "claims" / "C001.md"
    claim_path.write_text(
        "---\nschema_version: '2.0'\nname: C001\ntype: research-claim\nstatus: hypothesis\n"
        "evidence: []\ncontradicts: []\n---\n\n# Claim: C001\n\n## Statement\n"
        "The method reaches over 90% accuracy.\n",
        encoding="utf-8",
    )

    assert main(["evidence", "create", "--from-run", run_id, "--supports", "C001"]) == 0
    capsys.readouterr()

    assert main(["trace", "C001"]) == 0
    trace_output = capsys.readouterr().out
    assert "E001" in trace_output
    assert run_id in trace_output

    # `evidence create` already recomputed and wrote C001's status (to
    # 'provisional' — a run completing only earns 'checked' evidence, not
    # 'verified', so the claim can't be 'supported' either) — the graph is
    # consistent by construction, so a strict validate should pass clean.
    claim_status = claim_path.read_text(encoding="utf-8")
    assert "status: provisional" in claim_status

    validate_code = main(["validate", "--strict"])
    validate_output = capsys.readouterr().out
    assert "ResearchLedger Integrity Check" in validate_output
    assert validate_code == 0
    assert "Result: PASS" in validate_output

    report_code = main(["report"])
    assert report_code == 0
    report_output = capsys.readouterr().out
    assert "Claims" in report_output

    assert main(["inspect", run_id]) == 0
    inspect_output = capsys.readouterr().out
    assert json.loads(inspect_output)["run_id"] == run_id

    index_path = workspace / ".researchledger" / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["counts"]["evidence"] == 1


def test_run_without_double_dash_reports_usage_error(workspace, capsys):
    exit_code = main(["run"])
    assert exit_code == 2
    assert "Usage" in capsys.readouterr().err


def test_validate_outside_a_workspace_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["validate"])
    assert exit_code == 1
    assert "No ResearchLedger workspace found" in capsys.readouterr().err


def test_migrate_dry_run_via_cli(workspace, capsys):
    v1_evidence_dir = workspace / "research" / "evidence"
    v1_evidence_dir.mkdir(parents=True, exist_ok=True)
    (v1_evidence_dir / "E001.md").write_text(
        "---\nname: E001\ntype: experiment-evidence\nstatus: supported\n"
        "source_kind: experiment\nsupports: C001\n---\n\n# Evidence: E001\n",
        encoding="utf-8",
    )
    exit_code = main(["migrate", "--from", "v1", "--dry-run"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "1 evidence record(s) migrated" in output
    assert not (workspace / "backup").exists()


def test_reproduce_via_cli_in_a_git_repo(workspace, capsys):
    _git(["init"], workspace)
    _git(["config", "user.email", "test@example.com"], workspace)
    _git(["config", "user.name", "Test"], workspace)
    script = workspace / "exp.py"
    script.write_text(
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': 0.9}))\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], workspace)
    _git(["commit", "-m", "init"], workspace)

    assert main(["run", "--", sys.executable, "exp.py"]) == 0
    capsys.readouterr()

    exit_code = main(["reproduce", "R0001", "--tolerance", "0.001"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "REPRODUCED" in output


def test_validate_paper_via_cli(workspace, capsys):
    paper_path = workspace / "paper.md"
    paper_path.write_text("# Title\n\nAccuracy reached 91.4%.\n", encoding="utf-8")
    exit_code = main(["validate-paper", str(paper_path)])
    output = capsys.readouterr().out
    assert exit_code == 1  # one unsupported quantitative assertion
    assert "Unsupported:" in output
