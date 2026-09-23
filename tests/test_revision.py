import json

from researchledger.models import Claim, Evidence, Claim as ClaimModel, Evidence as EvidenceModel
from researchledger.revision import apply_evidence_revision, plan_evidence_revision, recover_incomplete_revisions
from researchledger.workspace import init_workspace


def _ev(ws, eid, status="verified", supports=None):
    obj = Evidence(id=eid, path=ws.evidence_dir/f"{eid}.md", schema_version="2.0", name=eid,
                   status=status, source_kind="observation", supports=supports or [], body=f"# {eid}\n")
    obj.path.write_text(obj.render(), encoding="utf-8")
    return obj


def _cl(ws, cid, *, evidence, support_sets=None, status="supported"):
    obj = Claim(id=cid, path=ws.claims_dir/f"{cid}.md", schema_version="2.0", name=cid,
                status=status, evidence=evidence, support_sets=support_sets or [], body=f"## Statement\n{cid}\n")
    obj.path.write_text(obj.render(), encoding="utf-8")
    return obj


def test_plan_revision_respects_alternative_support_sets(tmp_path):
    ws=init_workspace(tmp_path)
    _ev(ws,"E001",supports=["C001","C002"]); _ev(ws,"E002",supports=["C002"])
    _cl(ws,"C001",evidence=["E001"])
    _cl(ws,"C002",evidence=["E001","E002"],support_sets=[["E001"],["E002"]])
    plan=plan_evidence_revision(ws,{"E001":"superseded"})
    assert [(x.entity_id,x.before,x.after) for x in plan.claim_changes] == [("C001","supported","hypothesis")]


def test_apply_revision_commits_and_recomputes_claim(tmp_path):
    ws=init_workspace(tmp_path)
    _ev(ws,"E001",supports=["C001"]); _cl(ws,"C001",evidence=["E001"])
    result=apply_evidence_revision(ws,{"E001":"superseded"},reason="historical correction")
    assert result["status"] == "committed"
    assert EvidenceModel.load(ws.evidence_dir/"E001.md").status == "superseded"
    assert ClaimModel.load(ws.claims_dir/"C001.md").status == "hypothesis"
    mp=ws.root/".researchledger"/"revisions"/result["txid"]/"manifest.json"
    manifest=json.loads(mp.read_text())
    assert manifest["phase"] == "committed"
    assert sorted(manifest["files"]) == ["research/claims/C001.md","research/evidence/E001.md"]


def test_invalid_revision_status_does_not_mutate_workspace(tmp_path):
    ws=init_workspace(tmp_path)
    _ev(ws,"E001",supports=["C001"]); _cl(ws,"C001",evidence=["E001"])
    before=(ws.evidence_dir/"E001.md").read_text()
    try:
        apply_evidence_revision(ws,{"E001":"not-a-state"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert (ws.evidence_dir/"E001.md").read_text() == before


def test_recover_incomplete_revision_restores_preimage(tmp_path):
    ws=init_workspace(tmp_path)
    _ev(ws,"E001",supports=[])
    target=ws.evidence_dir/"E001.md"
    before=target.read_text()
    tx=ws.root/".researchledger"/"revisions"/"REV-test"
    backup=tx/"before"/"research"/"evidence"/"E001.md"
    backup.parent.mkdir(parents=True)
    backup.write_text(before)
    target.write_text(before.replace("status: verified","status: superseded"))
    (tx/"manifest.json").write_text(json.dumps({"phase":"applying","files":["research/evidence/E001.md"]}))
    recovered=recover_incomplete_revisions(ws)
    assert recovered == ["REV-test"]
    assert target.read_text() == before
    assert json.loads((tx/"manifest.json").read_text())["phase"] == "rolled_back"
