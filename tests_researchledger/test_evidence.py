import sys

from researchledger.evidence import create_evidence
from researchledger.models import Claim, load_claims
from researchledger.runner import run_command
from researchledger.workspace import init_workspace


def _write_claim(ws, cid, status="hypothesis", evidence=None):
    cl = Claim(
        id=cid,
        path=ws.claims_dir / f"{cid}.md",
        schema_version="2.0",
        name=cid,
        status=status,
        evidence=evidence or [],
        body=f"# Claim: {cid}\n\n## Statement\nSomething testable.\n",
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")
    return cl


def test_create_evidence_from_run_links_claim_bidirectionally(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C001")
    script = (
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'f1': 0.9}))\n"
    )
    manifest = run_command(ws, [sys.executable, "-c", script])

    ev = create_evidence(ws, from_run=manifest["run_id"], supports=["C001"])

    assert ev.id == "E001"
    assert ev.status == "checked"
    assert ev.runs == [manifest["run_id"]]
    assert "researchledger reproduce" in ev.body

    claims = load_claims(ws)
    assert "E001" in claims["C001"].evidence
    assert claims["C001"].status == "provisional"  # 'checked' evidence, not 'verified'


def test_create_evidence_rejects_verified_status_from_a_run(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"])
    try:
        create_evidence(ws, from_run=manifest["run_id"], status="verified")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_create_evidence_rejects_unknown_claim(tmp_path):
    ws = init_workspace(tmp_path)
    try:
        create_evidence(ws, supports=["C999"])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_create_evidence_ids_increment(tmp_path):
    ws = init_workspace(tmp_path)
    first = create_evidence(ws, source_kind="observation")
    second = create_evidence(ws, source_kind="observation")
    assert first.id == "E001"
    assert second.id == "E002"


def test_create_evidence_without_run_never_writes_runs_field(tmp_path):
    ws = init_workspace(tmp_path)
    ev = create_evidence(ws, source_kind="literature", status="observed")
    assert ev.runs == []


def test_concurrent_evidence_creates_never_collide_on_id(tmp_path):
    """Regression test for a confirmed bug: create_evidence() called
    next_id() with no lock at all. 8 concurrent calls produced duplicate
    ids (two callers both got E002), and the second write silently
    clobbered the first — only 6 of 8 evidence files survived."""
    import concurrent.futures

    ws = init_workspace(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda _: create_evidence(ws, source_kind="observation"), range(8)))

    ids = [ev.id for ev in created]
    assert len(ids) == len(set(ids)) == 8
    assert len(list(ws.evidence_dir.glob("E*.md"))) == 8


def test_create_evidence_rejects_checked_status_from_a_failed_run(tmp_path):
    """Regression test for a confirmed bug: 'evidence create' advertised
    being 'graph-consistent by construction' but never checked that the
    source run actually succeeded — a failed run could produce evidence
    recorded as 'checked' (implying the result looks right), only caught
    later by `validate`'s RL211, after the inconsistent record already
    existed."""
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "import sys; sys.exit(1)"])
    assert manifest["status"] == "failed"

    try:
        create_evidence(ws, from_run=manifest["run_id"])  # default status is 'checked'
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "did not complete successfully" in str(exc)

    assert list(ws.evidence_dir.glob("E*.md")) == []  # nothing was written


def test_create_evidence_allows_observed_status_from_a_failed_run(tmp_path):
    """Observing that a run failed is still legitimate evidence — only the
    implicitly-successful 'checked' status is blocked."""
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "import sys; sys.exit(1)"])

    ev = create_evidence(ws, from_run=manifest["run_id"], status="observed")
    assert ev.status == "observed"
