from researchledger.models import Claim, Evidence
from researchledger.validator import validate
from researchledger.workspace import init_workspace


def _write(obj):
    obj.path.write_text(obj.render(), encoding="utf-8")


def test_ids_wider_than_three_digits_validate(tmp_path):
    # Workspaces larger than 999 records per type need ids such as E1000.
    ws = init_workspace(tmp_path)
    _write(Evidence(id="E1000", path=ws.evidence_dir / "E1000.md", schema_version="2.0", name="E1000",
                    status="verified", source_kind="observation", supports=["C001234"], body="# E1000\n"))
    _write(Claim(id="C001234", path=ws.claims_dir / "C001234.md", schema_version="2.0", name="C001234",
                 status="supported", evidence=["E1000"], body="## Statement\nC001234\n"))
    result = validate(ws)
    assert not result.errors, [i.message for i in result.errors]


def test_ids_shorter_than_three_digits_still_rejected(tmp_path):
    ws = init_workspace(tmp_path)
    _write(Evidence(id="E12", path=ws.evidence_dir / "E12.md", schema_version="2.0", name="E12",
                    status="verified", source_kind="observation", body="# E12\n"))
    assert validate(ws).errors
