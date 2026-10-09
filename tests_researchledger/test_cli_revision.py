from researchledger.cli import main
from researchledger.models import Claim, Evidence
from researchledger.workspace import init_workspace


def _seed(ws):
    ev=Evidence(id='E001',path=ws.evidence_dir/'E001.md',schema_version='2.0',name='E001',status='verified',source_kind='observation',supports=['C001'],body='# E001\n')
    ev.path.write_text(ev.render(),encoding='utf-8')
    cl=Claim(id='C001',path=ws.claims_dir/'C001.md',schema_version='2.0',name='C001',status='supported',evidence=['E001'],body='## Statement\nclaim\n')
    cl.path.write_text(cl.render(),encoding='utf-8')


def test_revision_plan_cli(tmp_path, monkeypatch, capsys):
    ws=init_workspace(tmp_path); _seed(ws); monkeypatch.chdir(tmp_path)
    rc=main(['revision','plan','--update','E001=superseded','--json'])
    out=capsys.readouterr().out
    assert rc==0 and '"C001"' in out and '"hypothesis"' in out


def test_revision_apply_cli(tmp_path, monkeypatch, capsys):
    ws=init_workspace(tmp_path); _seed(ws); monkeypatch.chdir(tmp_path)
    rc=main(['revision','apply','--update','E001=superseded','--reason','correction','--json'])
    out=capsys.readouterr().out
    assert rc==0 and '"status": "committed"' in out
