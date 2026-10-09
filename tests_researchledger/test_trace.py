import sys

from researchledger.models import Claim, Evidence
from researchledger.runner import run_command
from researchledger.trace import trace
from researchledger.workspace import init_workspace


def _build_chain(tmp_path):
    ws = init_workspace(tmp_path)
    script = (
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'f1': 0.84}))\n"
        "art = pathlib.Path(os.environ['RESEARCHLEDGER_ARTIFACTS_DIR']) / 'results.csv'\n"
        "art.write_text('f1,0.84')\n"
    )
    manifest = run_command(ws, [sys.executable, "-c", script])
    run_id = manifest["run_id"]

    ev = Evidence(
        id="E001",
        path=ws.evidence_dir / "E001.md",
        schema_version="2.0",
        name="E001",
        status="verified",
        source_kind="experiment",
        supports=["C001"],
        runs=[run_id],
        body=f"# Evidence: E001\n\n## Reproducibility\nresearchledger reproduce {run_id}\n",
    )
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ev.path.write_text(ev.render(), encoding="utf-8")

    cl = Claim(
        id="C001",
        path=ws.claims_dir / "C001.md",
        schema_version="2.0",
        name="C001",
        status="supported",
        evidence=["E001"],
        body="# Claim: C001\n\n## Statement\nThe method improves F1 by 4.8 points.\n",
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")

    return ws, run_id


def test_trace_from_claim_reaches_verified_artifact(tmp_path):
    ws, run_id = _build_chain(tmp_path)
    text = trace(ws, "C001")

    assert "C001" in text
    assert "E001" in text
    assert run_id in text
    assert "metrics.json" in text
    assert "artifact hashes" in text
    assert "✓" in text  # verified: metrics present, artifact hash matches


def test_reverse_trace_from_run_shows_dependents(tmp_path):
    ws, run_id = _build_chain(tmp_path)
    text = trace(ws, run_id)

    assert "Depended on by" in text
    assert "E001" in text
    assert "C001" in text


def test_reverse_trace_from_unused_run_says_so(tmp_path):
    ws = init_workspace(tmp_path)
    import sys as _sys

    manifest = run_command(ws, [_sys.executable, "-c", "pass"])
    text = trace(ws, manifest["run_id"])
    assert "nothing yet" in text


def test_trace_missing_claim_is_flagged(tmp_path):
    ws = init_workspace(tmp_path)
    text = trace(ws, "C999")
    assert "MISSING" in text


def test_trace_rejects_unrecognized_id(tmp_path):
    ws = init_workspace(tmp_path)
    try:
        trace(ws, "X001")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_trace_missing_evidence_is_flagged(tmp_path):
    ws = init_workspace(tmp_path)
    text = trace(ws, "E999")
    assert "MISSING" in text


def test_trace_evidence_with_no_runs_says_so(tmp_path):
    ws = init_workspace(tmp_path)
    ev = Evidence(
        id="E001", path=ws.evidence_dir / "E001.md", schema_version="2.0", name="E001",
        status="observed", source_kind="literature",
    )
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ev.path.write_text(ev.render(), encoding="utf-8")

    text = trace(ws, "E001")
    assert "no runs" in text
    assert "literature" in text


def test_trace_claim_shows_manuscript_usage_by_section(tmp_path):
    ws, run_id = _build_chain(tmp_path)
    paper_dir = ws.papers_dir / "main"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.md").write_text(
        "# Title\n\n## Results\n\nC001 is supported by our experiments.\n",
        encoding="utf-8",
    )

    text = trace(ws, "C001")
    assert "Manuscript usage" in text
    assert "main/paper.md" in text
    assert "Results" in text
