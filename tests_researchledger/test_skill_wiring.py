"""Guards the skill <-> CLI wiring itself: these are prose files an LLM
reads, not code, so there's no way to "run" them — but we can at least
assert the instruction to actually invoke `researchledger` is still there,
so a future edit to these files doesn't silently drop it back to "the tool
exists somewhere" instead of "the skill tells you to use it."
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


def _read(skill_name: str) -> str:
    return (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")


def test_research_entry_point_bootstraps_the_run_ledger():
    text = _read("research")
    assert "researchledger init" in text
    assert "researchledger run" in text
    assert "researchledger report" in text
    # The hook description must not have regressed back to describing a
    # fixed "stage" — that was the exact v1/v2 contradiction this was fixed for.
    assert "stage, evidence" not in text


def test_reproducible_implementation_spec_invokes_run_and_reproduce():
    text = _read("reproducible-implementation-spec")
    assert "researchledger run" in text
    assert "researchledger reproduce" in text
    assert "--seed" in text
    assert "--data" in text
    assert "run-ledger.md" in text


def test_evidence_assessment_invokes_trace_validate_and_evidence_create():
    text = _read("evidence-assessment")
    assert "researchledger trace" in text
    assert "researchledger validate" in text
    assert "researchledger evidence create" in text
    assert "run-ledger.md" in text


def test_experiment_design_points_execution_at_the_run_ledger():
    text = _read("experiment-design")
    assert "researchledger run" in text
    assert "run-ledger.md" in text


def test_wired_skills_do_not_still_say_convfusion_about_themselves():
    for skill_name in ("research", "reproducible-implementation-spec", "evidence-assessment", "experiment-design"):
        text = _read(skill_name)
        # The one legitimate historical mention is the attribution line
        # ("Ported from the ConvFusion research-skill library..."); nothing
        # else in these files should call the plugin itself "ConvFusion".
        self_references = [
            line
            for line in text.splitlines()
            if "ConvFusion" in line and "Ported from the ConvFusion research-skill library" not in line
            and "verbatim from ConvFusion" not in line
        ]
        assert self_references == [], f"{skill_name}: {self_references}"
