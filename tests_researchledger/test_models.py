from researchledger.models import Claim, Evidence, recompute_claim_status


def _evidence(eid, status, source_kind="experiment"):
    return Evidence(id=eid, path=None, schema_version="2.0", name=eid, status=status, source_kind=source_kind)


def _claim(cid, status, evidence=None, contradicts=None):
    return Claim(
        id=cid, path=None, schema_version="2.0", name=cid, status=status,
        evidence=evidence or [], contradicts=contradicts or [],
    )


def test_no_evidence_is_hypothesis():
    claim = _claim("C001", "supported", evidence=[])
    assert recompute_claim_status(claim, {}) == "hypothesis"


def test_verified_supporting_evidence_is_supported():
    claim = _claim("C001", "hypothesis", evidence=["E001"])
    evidence_map = {"E001": _evidence("E001", "verified")}
    assert recompute_claim_status(claim, evidence_map) == "supported"


def test_checked_but_not_verified_evidence_is_only_provisional():
    """The whole point of the v2 vocabulary: one experiment completing
    (status='checked') does not earn 'supported' on its own."""
    claim = _claim("C001", "supported", evidence=["E001"])
    evidence_map = {"E001": _evidence("E001", "checked")}
    assert recompute_claim_status(claim, evidence_map) == "provisional"


def test_verified_support_plus_checked_contradiction_is_mixed():
    claim = _claim("C001", "supported", evidence=["E001"], contradicts=["E002"])
    evidence_map = {
        "E001": _evidence("E001", "verified"),
        "E002": _evidence("E002", "checked"),
    }
    assert recompute_claim_status(claim, evidence_map) == "mixed"


def test_contradiction_with_no_support_is_contradicted():
    claim = _claim("C001", "hypothesis", evidence=[], contradicts=["E002"])
    evidence_map = {"E002": _evidence("E002", "verified")}
    assert recompute_claim_status(claim, evidence_map) == "contradicted"


def test_superseded_evidence_is_ignored():
    claim = _claim("C001", "supported", evidence=["E001"])
    evidence_map = {"E001": _evidence("E001", "superseded")}
    assert recompute_claim_status(claim, evidence_map) == "hypothesis"


def test_withdrawn_claim_is_never_reinstated():
    claim = _claim("C001", "withdrawn", evidence=["E001"])
    evidence_map = {"E001": _evidence("E001", "verified")}
    assert recompute_claim_status(claim, evidence_map) == "withdrawn"


def test_support_set_requires_all_members_for_supported_status():
    claim = Claim(
        id="C010", path=None, schema_version="2.0", name="C010", status="hypothesis",
        evidence=["E001", "E002"], support_sets=[["E001", "E002"]],
    )
    evidence_map = {
        "E001": _evidence("E001", "verified"),
        "E002": _evidence("E002", "superseded"),
    }
    assert recompute_claim_status(claim, evidence_map) == "hypothesis"


def test_alternative_support_set_survives_loss_of_other_path():
    claim = Claim(
        id="C011", path=None, schema_version="2.0", name="C011", status="supported",
        evidence=["E001", "E002", "E003"],
        support_sets=[["E001", "E002"], ["E003"]],
    )
    evidence_map = {
        "E001": _evidence("E001", "superseded"),
        "E002": _evidence("E002", "verified"),
        "E003": _evidence("E003", "verified"),
    }
    assert recompute_claim_status(claim, evidence_map) == "supported"


def test_required_evidence_is_conjoined_with_every_support_path():
    claim = Claim(
        id="C012", path=None, schema_version="2.0", name="C012", status="supported",
        evidence=["E001"], support_sets=[["E001"]], required_evidence="E009",
    )
    evidence_map = {
        "E001": _evidence("E001", "verified"),
        "E009": _evidence("E009", "checked"),
    }
    assert recompute_claim_status(claim, evidence_map) == "provisional"
    evidence_map["E009"].status = "verified"
    assert recompute_claim_status(claim, evidence_map) == "supported"


def test_support_sets_round_trip_yaml(tmp_path):
    path = tmp_path / "C013.md"
    claim = Claim(
        id="C013", path=path, schema_version="2.0", name="C013", status="supported",
        evidence=["E001", "E002", "E003"], support_sets=[["E001", "E002"], ["E003"]],
        body="## Statement\nA claim.\n",
    )
    path.write_text(claim.render(), encoding="utf-8")
    loaded = Claim.load(path)
    assert loaded.support_sets == [["E001", "E002"], ["E003"]]
