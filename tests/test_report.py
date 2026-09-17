import json

from researchledger.models import Claim, Evidence
from researchledger.report import render_json, render_text
from researchledger.validator import validate
from researchledger.workspace import init_workspace


def test_render_text_clean_workspace_shows_pass(tmp_path):
    ws = init_workspace(tmp_path)
    result = validate(ws)
    text = render_text(result)
    assert "Result: PASS" in text
    assert "0 warnings, 0 errors" in text


def test_render_text_reports_errors_and_warnings_with_codes(tmp_path):
    ws = init_workspace(tmp_path)
    cl = Claim(
        id="C001", path=ws.claims_dir / "C001.md", schema_version="2.0", name="C001",
        status="hypothesis", evidence=["E404"],
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")

    result = validate(ws)
    text = render_text(result)
    assert "ERROR" in text
    assert "RL101" in text
    assert "Result: FAIL" in text
    assert "1 error" in text and "1 errors" not in text  # singular grammar


def test_render_text_strict_promotes_warning_and_labels_it(tmp_path):
    ws = init_workspace(tmp_path)
    cl = Claim(
        id="C001", path=ws.claims_dir / "C001.md", schema_version="2.0", name="C001",
        status="supported", evidence=["E001"],
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")
    ev = Evidence(
        id="E001", path=ws.evidence_dir / "E001.md", schema_version="2.0", name="E001",
        status="superseded", source_kind="observation", supports=["C001"],
    )
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ev.path.write_text(ev.render(), encoding="utf-8")

    result = validate(ws)
    assert result.passed(strict=False) is True

    non_strict_text = render_text(result, strict=False)
    assert "Result: PASS" in non_strict_text

    strict_text = render_text(result, strict=True)
    assert "Result: FAIL" in strict_text
    assert "promoted by --strict" in strict_text


def test_render_json_shape(tmp_path):
    ws = init_workspace(tmp_path)
    cl = Claim(
        id="C001", path=ws.claims_dir / "C001.md", schema_version="2.0", name="C001",
        status="hypothesis", evidence=["E404"],
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")

    result = validate(ws)
    payload = json.loads(render_json(result, strict=True))
    assert payload["passed"] is False
    assert payload["strict"] is True
    assert payload["errors"][0]["code"] == "RL101"
    assert "counts" in payload and "metrics" in payload
