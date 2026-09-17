"""Covers the CLI's error paths and less-common branches that
test_cli.py's happy-path walkthrough doesn't exercise."""

import json
import sys

import pytest

from researchledger.cli import main


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    return tmp_path


def test_init_with_explicit_path_prints_cd_hint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    new_dir = "my-study"
    assert main(["init", new_dir]) == 0
    output = capsys.readouterr().out
    assert f"cd {new_dir}" in output
    assert (tmp_path / new_dir / ".researchledger").is_dir()


def test_run_with_bad_data_path_is_a_usage_error(workspace, capsys):
    exit_code = main(["run", "--data", str(workspace / "nope.csv"), "--", sys.executable, "-c", "pass"])
    assert exit_code == 2
    assert "error:" in capsys.readouterr().err


def test_report_json(workspace, capsys):
    exit_code = main(["report", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "counts" in payload and "metrics" in payload


def test_validate_json(workspace, capsys):
    exit_code = main(["validate", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True


def test_trace_unrecognized_id_via_cli(workspace, capsys):
    exit_code = main(["trace", "X999"])
    assert exit_code == 2
    assert "error:" in capsys.readouterr().err


def test_inspect_missing_run(workspace, capsys):
    exit_code = main(["inspect", "R9999"])
    assert exit_code == 1
    assert "no such run" in capsys.readouterr().err


def test_reproduce_missing_run(workspace, capsys):
    exit_code = main(["reproduce", "R9999"])
    assert exit_code == 1
    assert "no such run" in capsys.readouterr().err


def test_index_command(workspace, capsys):
    exit_code = main(["index"])
    assert exit_code == 0
    assert "Wrote" in capsys.readouterr().out
    assert (workspace / ".researchledger" / "index.json").exists()


def test_migrate_with_malformed_file_exits_nonzero(workspace, capsys):
    evidence_dir = workspace / "research" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "E001.md").write_bytes(b"\xff\xfe broken")
    exit_code = main(["migrate", "--from", "v1"])
    assert exit_code == 1
    assert "require manual review" in capsys.readouterr().out


def test_evidence_create_error_via_cli(workspace, capsys):
    exit_code = main(["evidence", "create", "--supports", "C999"])
    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_validate_paper_missing_file(workspace, capsys):
    exit_code = main(["validate-paper", str(workspace / "nope.md")])
    assert exit_code == 1
    assert "no such file" in capsys.readouterr().err


def test_validate_paper_json_output(workspace, capsys):
    paper_path = workspace / "paper.md"
    paper_path.write_text("# Title\n\nAccuracy reached 91.4%.\n", encoding="utf-8")
    exit_code = main(["validate-paper", str(paper_path), "--json"])
    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["unsupported"] == 1


def test_refresh_index_failure_is_non_fatal(workspace, monkeypatch, capsys):
    import researchledger.cli as cli_module

    def _boom(_ws):
        raise RuntimeError("disk full")

    monkeypatch.setattr(cli_module, "write_index", _boom)
    exit_code = main(["run", "--", sys.executable, "-c", "pass"])
    assert exit_code == 0  # the run itself still succeeded
    assert "could not refresh" in capsys.readouterr().err
