from pathlib import Path

from researchledger.models import Claim, Evidence, recompute_claim_status, support_fields_from_relations
from validation_study.analysis import tms_crosscheck as xc


def _status(claim_fields, statuses):
    claim = Claim(id="C1", path=Path("C1.md"), **claim_fields)
    ev = {e: Evidence(id=e, path=Path(f"{e}.md"), status=s) for e, s in statuses.items()}
    return recompute_claim_status(claim, ev)


# E1 is both a singleton sufficient path and a member of {E1, E2}.
COLLISION = [("E1", "C1", "member", "g1"), ("E2", "C1", "member", "g1"), ("E1", "C1", "supports", None)]


def test_explicit_registration_keeps_singleton_alternative():
    fields = support_fields_from_relations(COLLISION)
    assert fields["support_sets"] == [["E1"], ["E1", "E2"]]
    assert _status(fields, {"E1": "verified", "E2": "invalidated"}) == "supported"


def test_naive_registration_reproduces_pair_collision():
    fields = xc._naive_fields(COLLISION, "C1")
    assert _status(fields, {"E1": "verified", "E2": "invalidated"}) == "hypothesis"


def test_required_evidence_is_conjoined_with_every_path():
    rels = [("E1", "C1", "supports", None), ("E2", "C1", "supports", None), ("E3", "C1", "requires", None)]
    fields = support_fields_from_relations(rels)
    assert fields["support_sets"] == [] and fields["required_evidence"] == "E3"
    assert _status(fields, {"E1": "verified", "E2": "verified", "E3": "superseded"}) == "hypothesis"
    assert _status(fields, {"E1": "invalidated", "E2": "verified", "E3": "verified"}) == "supported"


def test_crosscheck_small_run_matches_oracle_and_controls_diverge():
    result = xc.run(n=20, seed=7)
    for graph, r in result["graphs"].items():
        t = r["tallies"]
        assert t["jtms"] == t["atms"] == t["rl_explicit"] == t["events"], graph
    gold = result["graphs"]["gold"]["tallies"]
    assert gold["reach"] < gold["events"] and gold["flat"] < gold["events"]


def test_planner_on_disk_matches_oracle_with_explicit_registration():
    pc = xc.planner_check(n=3, seed=7, graph="spurious30", mode="explicit")
    assert pc["matches"] == pc["events"] == 9
