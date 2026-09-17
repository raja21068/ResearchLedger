"""Guards the shipped examples/quickstart workspace: it exists specifically
so a new user (or CI) can point `researchledger` at something real and see
it pass clean. If a future change to the validator or the example itself
breaks that, this is what catches it.
"""

from pathlib import Path

from researchledger.validate_paper import audit_paper
from researchledger.validator import validate
from researchledger.workspace import Workspace

EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "quickstart"


def test_example_workspace_exists():
    assert EXAMPLE_ROOT.is_dir()
    assert (EXAMPLE_ROOT / "project.md").exists()


def test_example_workspace_validates_strict_clean():
    ws = Workspace(EXAMPLE_ROOT)
    result = validate(ws)
    assert result.errors == []
    assert result.warnings == []
    assert result.passed(strict=True) is True
    for metric_value in result.metrics.values():
        assert metric_value == 100.0


def test_example_paper_is_fully_backed():
    ws = Workspace(EXAMPLE_ROOT)
    result = audit_paper(ws, EXAMPLE_ROOT / "papers" / "main" / "paper.md")
    assert result.unsupported == 0
    assert result.stale_evidence_usage == 0
    assert result.backed_by_verified_evidence == result.linked_to_claims
    assert result.backed_by_reproducible_runs == result.linked_to_claims
