"""The stages, in one place.

    S1 Idea -> S2 Draft -> S3 Review -> S4 Code -> S5 Refine

S2 writes the paper BEFORE any experiment, with empty result tables and empty figure
slots. S4 treats those empty slots as its requirements and fills them by running code
in the sandbox. S5 is the loop: the slots are filled by code (never by a model), then
write-update <-> review repeats until the thresholds are met.

Each stage names the function that runs it, the input file it reads from
`<project>/_inputs/` (if it requires one), the artifact that proves it ran, and the
state it advances to. A stage is done only when its artifact passes `artifact_valid`.
"""
import json
import pathlib
import shutil

from factory import results
from factory.steps import code, idea, review, write


def _idea(project, source, context):
    result = idea.run(project, context)
    from factory.integrations.ledger import enabled, record_idea
    if enabled(context):
        record_idea(project)
    return result


def _write(project, source, context):
    if context.get('science_mode') == 'validation':
        from factory.science.protocol import check
        ok, issues = check(project, context)
        if not ok:
            raise ValueError('validation protocol gate before draft: ' + '; '.join(issues))
    return write.run(project, context)


def _review(project, source, context):
    """First pass only: score the empty-results draft. Nothing is revised before there are results."""
    return review.run(project, context, out_name="3_review", revise=False)


def _code(project, source, context):
    if context.get('science_mode') == 'validation':
        from factory.science.protocol import check
        ok, issues = check(project, context)
        if not ok:
            raise ValueError('protocol changed or not locked before experiment: ' + '; '.join(issues))
    result = code.run(project, context)
    from factory.integrations.ledger import enabled, import_docker_run
    if enabled(context):
        import_docker_run(project, context, force_new=True)
    return result


def _prepare_filled_paper(project):
    """5_refine/source: the draft with its slots filled from results.json, and compiled."""
    project = pathlib.Path(project)
    spec = results.load_spec(project / "2_paper" / "results_spec.json")
    payload = results.read_results(project / "4_code" / "results.json")
    src = project / "5_refine" / "source"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(project / "2_paper" / "build", src / "build")
    shutil.copyfile(project / "2_paper" / "paper.tex", src / "paper.tex")
    shutil.copyfile(project / "2_paper" / "paper.tex", src / "build" / "paper.tex")
    filled = results.fill(src / "build", spec, payload)
    pdf = review.compile_pdf(src / "build", "paper.tex")
    shutil.copyfile(pdf, src / "paper.pdf")
    return src, filled


def _refine(project, source, context):
    """Fill the slots with the measured results, then loop write-update <-> review.

    The first revision uses everything learned so far: the first review's weaknesses and
    what PaperCompiler could not resolve. Numbers are never typed by a model.
    """
    project = pathlib.Path(project)
    from factory.integrations.ledger import enabled, verify_run_receipt
    if enabled(context):
        valid, detail = verify_run_receipt(project)
        if not valid:
            raise ValueError(f"ResearchLedger gate blocked S5: {detail}")
    if context.get('science_mode') == 'validation':
        from factory.science.gates import audit
        gate = audit(project, context)
        if gate['status'] != 'PASS_AUTOMATED_INTEGRITY_ONLY':
            reasons = [key + ': ' + '; '.join(value['issues'])
                       for key, value in gate['checks'].items() if value['status'] != 'PASS']
            raise ValueError('evidence-first validation blocks refinement: ' + ' | '.join(reasons))
    src, _filled = _prepare_filled_paper(project)
    log_path = project / "_inputs" / "experimental_log.md"
    notes = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    shown = notes + (project / "4_code" / "experimental_log.generated.md").read_text(encoding="utf-8")
    seed = []
    first = project / "3_review" / "round_01" / "review.json"
    if first.is_file():
        seed += json.loads(first.read_text(encoding="utf-8")).get("weaknesses", [])
    unresolved = project / "4_code" / "unresolved.json"
    if unresolved.is_file():
        seed += json.loads(unresolved.read_text(encoding="utf-8"))
    return review.run(project, context, out_name="5_refine", revise=True, seed_weaknesses=seed,
                      log_text=shown, guard_text=notes, source_dir=src)


def _load(path):
    try:
        payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("schema_version") == 1 else None


def _score_line(report):
    scores = report["final_scores"]
    shown = ", ".join(f"{k} {v}" for k, v in scores.items())
    return f"{shown} after {len(report['rounds'])} round(s), {report['status']}"


def artifact_valid(project, stage_id):
    """(valid, detail) for a stage's artifact, checked from disk."""
    project = pathlib.Path(project)
    path = project / BY_ID[stage_id]["artifact"]
    if not path.is_file() or path.stat().st_size == 0:
        return False, "missing"
    if stage_id == "S1":
        report = _load(project / "1_idea" / "tournament.json")
        ok = bool(report and report.get("winner") and report.get("ideas"))
        return ok, "idea selected" if ok else "tournament report invalid"
    if stage_id == "S2":
        try:
            spec = results.load_spec(project / "2_paper" / "results_spec.json")
        except ValueError as exc:
            return False, str(exc)
        problems = results.coverage_problems(path.read_text(encoding="utf-8"), spec)
        return (not problems), (f"draft with {len(spec['slots'])} empty result slots"
                                if not problems else "; ".join(problems))
    if stage_id == "S4":
        return code.artifact_ok(project)
    report = _load(path)
    ok = bool(report and isinstance(report.get("final_scores"), dict)
              and report.get("status") and report.get("rounds"))
    if not ok:
        return False, "review report invalid"
    if stage_id == "S5" and report["status"] != "TARGET_REACHED":
        return False, "refinement did not reach its declared thresholds: " + _score_line(report)
    return True, _score_line(report)


STAGES = [
    dict(id="S1", title="Idea", artifact="1_idea/idea.md", states=("IDEA_READY",),
         driver=_idea, source=None),
    dict(id="S2", title="Draft", artifact="2_paper/paper.tex", states=("PAPER_READY",),
         driver=_write, source=None),
    dict(id="S3", title="Review", artifact="3_review/report.json", states=("REVIEWED",),
         driver=_review, source=None),
    dict(id="S4", title="Code", artifact="4_code/results.json", states=("CODE_RUN",),
         driver=_code, source=None),
    dict(id="S5", title="Refine", artifact="5_refine/report.json", states=("REFINED",),
         driver=_refine, source=None),
]

BY_ID = {stage["id"]: stage for stage in STAGES}


def ordered(start=None, stop=None):
    """Stages from `start` through `stop` inclusive, in pipeline order."""
    ids = [stage["id"] for stage in STAGES]
    for name in (start, stop):
        if name and name not in ids:
            raise ValueError(f"unknown stage {name!r}; stages are {', '.join(ids)}")
    lo = ids.index(start) if start else 0
    hi = ids.index(stop) + 1 if stop else len(ids)
    if lo >= hi:
        raise ValueError(f"stage range is inverted: {start} .. {stop}")
    return STAGES[lo:hi]
