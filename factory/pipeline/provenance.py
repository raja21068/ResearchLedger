"""Input signatures and artifact chains for deterministic checkpoint invalidation.

A stage signature covers the inputs and upstream products it consumed.  Computing
it *before* execution means a later resume detects changes to ideas, options,
datasets, results specs, or an upstream review.  Large data files are hashed in
chunks rather than loaded into RAM.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

STAGE_DEPENDENCIES = {
    "S1": (),
    "S2": ("1_idea/idea.md", "1_idea/tournament.json", "control/protocol_lock.json"),
    "S3": ("2_paper/paper.tex", "2_paper/paper.pdf", "2_paper/results_spec.json"),
    "S4": ("2_paper/paper.tex", "2_paper/results_spec.json", "3_review/report.json",
           "control/protocol_lock.json"),
    "S5": ("2_paper/paper.tex", "2_paper/results_spec.json", "3_review/report.json",
           "4_code/results.json", "control/ledger_s4_receipt.json",
           "control/metric_claim_bindings.json", "control/independent_repeat.json",
           "control/independent_repeat_output/run/results.json", "control/doi_verifications",
           "4_code/experimental_log.generated.md",
           "4_code/unresolved.json"),
}


STAGE_OUTPUTS = {
    "S1": ("1_idea/tournament.json", "control/ledger_idea.json"),
    "S2": ("2_paper/results_spec.json", "2_paper/paper.pdf"),
    "S3": ("3_review/final/paper.tex", "3_review/final/paper.pdf"),
    "S4": ("4_code/repo", "4_code/unresolved.json", "4_code/experimental_log.generated.md", "control/ledger_s4_receipt.json"),
    "S5": ("5_refine/final/paper.tex", "5_refine/final/paper.pdf"),
}


def output_signature(project, stage_id):
    """Bind supporting artifacts, not just the primary checkpoint file."""
    root = Path(project).resolve()
    entries = []
    for rel in STAGE_OUTPUTS[stage_id]:
        path = root / rel
        if path.is_symlink():
            raise ValueError(f"output symlink prohibited: {rel}")
        if path.is_file():
            entries.append([rel, hash_file(path)])
        elif path.is_dir():
            for member in sorted(path.rglob("*")):
                if member.is_symlink():
                    raise ValueError(f"output symlink prohibited: {member}")
                if member.is_file() and "__pycache__" not in member.parts:
                    entries.append([member.relative_to(root).as_posix(), hash_file(member)])
        else:
            entries.append([rel, "MISSING"])
    return hashlib.sha256(json.dumps(entries, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()

def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_signature(project, stage_id, context):
    root = Path(project).resolve()
    if stage_id not in STAGE_DEPENDENCIES:
        raise ValueError(f"unknown stage {stage_id}")
    # Validation mode collects operator-authored evidence BETWEEN stages. Watching
    # every _inputs file at S1 would invalidate an already selected idea when the
    # scientist later writes a preregistration or metric bindings. Scope only the
    # inputs a stage actually consumes; keep legacy broad signatures in exploration.
    if context.get('science_mode') == 'validation':
        by_stage = {
            'S1': ('topic.md', 'ideas.json', 'context.json'),
            'S2': ('context.json', 'experimental_log.md', 'research_protocol.json'),
            'S3': ('context.json', 'research_protocol.json'),
            'S4': ('context.json', 'research_protocol.json', 'data'),
            'S5': ('context.json', 'research_protocol.json', 'data',
                   'metric_claims.json', 'literature.json', 'prior_art.json'),
        }
        watched = [root / '_inputs' / name for name in by_stage[stage_id]]
        # Even a non-consumed symlink in the operator directory is unsafe.
        inputs = root / '_inputs'
        if inputs.is_dir() and any(item.is_symlink() for item in inputs.rglob('*')):
            raise ValueError('symlink prohibited within _inputs')
    else:
        watched = [root / '_inputs']
    watched += [root / rel for rel in STAGE_DEPENDENCIES[stage_id]]
    # Upgrading source code or altering a reviewer prompt changes the workflow.
    # Watch source files, but not bytecode, tests, generated workspaces or vendor corpora.
    factory_sources = sorted((Path(__file__).resolve().parents[1]).rglob("*.py"))
    watched += factory_sources
    repository = Path(__file__).resolve().parents[2]
    if context.get("ledger_enabled", False):
        # Bound checkpoints to the integrity engine and actual methodology prompts.
        # Persistent run/evidence records are NOT hashed here (they evolve over time).
        watched += sorted((repository / "researchledger").rglob("*.py"))
        watched += sorted((repository / "schemas").glob("*.schema.json"))
        from factory.integrations.methodology import STAGE_SKILLS
        group = "idea" if stage_id == "S1" else "experiment" if stage_id == "S4" else "review"
        watched += [repository / "skills" / name / "SKILL.md" for name in STAGE_SKILLS[group]]
    if stage_id in {"S3", "S5"}:
        watched.append(repository / "vendor" / "20- Paper Review Agent" / "Prompt.txt")
        watched.append(repository / "vendor" / "20- Paper Review Agent" /
                       "Referee-Lean-v2" / "config" / "score_dimensions.json")
    if stage_id == "S4":
        watched.append(repository / "vendor" / "PaperCompiler-main" / "codes")
    if stage_id == "S2":
        from factory.steps.write import DEFAULT_TEMPLATE
        selected = context.get("template_dir", str(DEFAULT_TEMPLATE))
        template_dir = Path(selected)
        if not template_dir.is_absolute():
            template_dir = repository / template_dir
        if template_dir.is_dir():
            watched += sorted(p for p in template_dir.rglob("*") if p.is_file()
                              and p.suffix.lower() in {".tex", ".sty", ".cls", ".bib", ".bst"})
    records = []
    for item in watched:
        if item.is_symlink():
            raise ValueError(f"symlink is not an allowed stage input: {item}")
        if item.is_file():
            paths = [item]
        elif item.is_dir():
            paths = sorted(p for p in item.rglob("*") if p.is_file() or p.is_symlink())
        else:
            records.append([item.relative_to(root).as_posix(), "MISSING"])
            continue
        for path in paths:
            if path.is_symlink():
                raise ValueError(f"symlink is not an allowed stage input: {path}")
            try:
                label = path.relative_to(root).as_posix()
            except ValueError:
                label = "toolchain:" + path.resolve().as_posix()
            records.append([label, hash_file(path)])
    canonical = json.dumps({"schema": 2, "stage": stage_id, "context": context,
                            "inputs": records}, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
