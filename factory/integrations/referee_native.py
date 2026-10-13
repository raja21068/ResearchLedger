"""Explicit subprocess bridge to the bundled Referee Lean v2 CLI.

This calls the *actual* Referee review engine. It deliberately does not
reinterpret model-produced Referee reviews as Factory scorecards, fabricate
independent scientific validation, or execute a vendor review implicitly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "vendor" / "20- Paper Review Agent" / "Referee-Lean-v2"
ALLOWED_SUFFIXES = {".md", ".txt", ".tex", ".pdf", ".docx", ".ipynb", ".csv", ".json", ".xlsx"}


def _vendor():
    if not (VENDOR / "referee" / "cli.py").is_file():
        raise ValueError(f"bundled Referee engine missing: {VENDOR}")
    return VENDOR


def _document(path):
    input_path = Path(path).expanduser()
    if input_path.is_symlink():
        raise ValueError("symlink input not allowed")
    file = input_path.resolve()
    if not file.is_file() or not file.suffix.lower() in ALLOWED_SUFFIXES:
        raise ValueError(f"missing or unsupported reviewer input: {path}")
    if file.is_symlink():
        raise ValueError("symlink input not allowed")
    return file


def _run(arguments, *, timeout=1200):
    vendor = _vendor()
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 14400:
        raise ValueError("timeout must be 1..14400 seconds")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(vendor) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        cp = subprocess.run([sys.executable, "-m", "referee.cli", *arguments],
                            cwd=vendor, env=env, text=True, capture_output=True,
                            errors="replace", timeout=timeout, shell=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"native Referee engine timed out after {timeout}s") from exc
    if cp.returncode:
        raise ValueError("native Referee execution failed: " + (cp.stderr or cp.stdout)[-3500:])
    return cp


def inspect(paths, *, output=None):
    files = [_document(path) for path in paths]
    if not files:
        raise ValueError("at least one manuscript/package file is required")
    args = ["inspect-package", *map(str, files)]
    if output:
        dest = Path(output).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        args.extend(["--json-out", str(dest)])
    cp = _run(args, timeout=120)
    return {"status": "EXECUTED", "engine": "referee-lean-v2", "mode": "inspect-package",
            "paths": list(map(str, files)), "stdout": cp.stdout[-8000:],
            "report": str(Path(output).resolve()) if output else None}


def review(project, manuscript, *, provider="openai-compatible", model=None, scripted_responses=None,
           mode="deep", pipeline="lean", profile=None, search_backend=None, timeout=1200,
           prior_manuscript=None):
    """Run native engine in a project-scoped audit directory; no host code execution."""
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError("project workspace not found")
    paper = _document(manuscript)
    if provider not in {"openai-compatible", "scripted"}:
        raise ValueError("provider must be openai-compatible or scripted")
    if mode not in {"standard", "deep", "exhaustive"} or pipeline not in {"lean", "legacy"}:
        raise ValueError("invalid Referee mode or pipeline")
    if provider == "scripted":
        if not scripted_responses:
            raise ValueError("scripted provider requires an explicit fixture (demo/test only)")
        fixture = _document(scripted_responses)
        if fixture.suffix != ".json":
            raise ValueError("scripted responses must be a JSON file")
        try:
            if not isinstance(json.loads(fixture.read_text(encoding="utf-8")), dict):
                raise ValueError("scripted fixture must contain an object")
        except json.JSONDecodeError as exc:
            raise ValueError("invalid scripted fixture JSON") from exc
    elif not (model or os.getenv("REFEREE_MODEL")):
        raise ValueError("model is required for live Referee; pass --model or set REFEREE_MODEL")
    if provider == "openai-compatible" and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required for live Referee; do not put credentials in project files")
    if profile and profile not in {"balanced", "fast", "full-audit", "clinical", "engineering", "theory", "computational", "reproducibility"}:
        # Delegate profile validation to the native engine so new supported profiles work.
        if not profile.replace("-", "").replace("_", "").isalnum():
            raise ValueError("invalid Referee profile")
    root = project / "referee_native" / "runs"
    root.mkdir(parents=True, exist_ok=True)
    args = ["review", str(paper), "--provider", provider, "--mode", mode,
            "--pipeline", pipeline, "--run-root", str(root)]
    if model:
        args.extend(["--model", model])
    if scripted_responses:
        args.extend(["--scripted-responses", str(Path(scripted_responses).resolve())])
    if search_backend:
        if search_backend not in {"none", "federated", "scripted"}:
            raise ValueError("invalid Referee search backend")
        args.extend(["--search-backend", search_backend])
    if profile:
        args.extend(["--profile", profile])
    if prior_manuscript:
        args.extend(["--review-mode", "revision", "--prior-manuscript", str(_document(prior_manuscript))])
    before = {p.name for p in root.iterdir() if p.is_dir()}
    cp = _run(args, timeout=timeout)
    candidate = Path(cp.stdout.strip().splitlines()[-1])
    # Referee prints the final report; never claim a success from only returncode.
    if not candidate.is_absolute():
        candidate = VENDOR / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root) or candidate.name != "review.md":
        raise ValueError("Referee returned a review outside the expected workspace")
    run_dir = candidate.parent.parent
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    final = bool(state.get("final_review_exportable"))
    return {"status": state.get("status", "UNKNOWN"), "engine": "referee-lean-v2",
            "provider": provider, "scripted_test_only": provider == "scripted",
            "run_directory": str(run_dir), "review_markdown": str(candidate) if candidate.is_file() else None,
            "review_exportable": final,
            "admitted_major_concerns": len(state.get("admitted_concerns") or []),
            "hard_invariant_failures": len(state.get("hard_invariant_failures") or []),
            "new_run": run_dir.name not in before}


def compare(old, new, *, output):
    old_file, new_file = _document(old), _document(new)
    out = Path(output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["compare-revision", str(old_file), str(new_file), "--json-out", str(out)], timeout=120)
    if not out.is_file():
        raise ValueError("native Referee did not write the requested revision diff")
    return {"status": "EXECUTED", "engine": "referee-lean-v2", "comparison_json": str(out)}


def iterate(project, manuscripts, *, scripted_responses=(), **kwargs):
    """Review a real sequence of supplied drafts and record revision comparisons.

    This is NOT an auto-editor. Drafts must be supplied independently (or created
    by the existing Factory revision stage). Native Referee reassesses each file.
    """
    drafts = [_document(x) for x in manuscripts]
    if len(drafts) < 2 or len(drafts) > 12:
        raise ValueError('iterate requires 2..12 manuscript versions')
    fixtures = list(scripted_responses or ())
    if kwargs.get('provider') == 'scripted' and len(fixtures) != len(drafts):
        raise ValueError('scripted iteration requires one fixture per manuscript version')
    project = Path(project).resolve()
    out = project / 'referee_native'
    out.mkdir(parents=True, exist_ok=True)
    rounds = []
    for index, document in enumerate(drafts):
        diff = None
        if index:
            diff = compare(drafts[index - 1], document,
                           output=out / f'comparison_{index:02d}_{index+1:02d}.json')
        assessed = review(project, document,
                          scripted_responses=fixtures[index] if fixtures else None, **kwargs)
        row = {'round': index + 1, 'input': str(document), 'assessment': assessed,
               'revision_difference': diff}
        rounds.append(row)
    report = {
        'schema_version': 1, 'engine': 'referee-lean-v2', 'workflow': 'native_iterative_review',
        'status': 'ROUNDS_EXECUTED', 'automatic_manuscript_revision': False,
        'scientific_acceptance_certified': False,
        'scripted_test_only': kwargs.get('provider') == 'scripted',
        'note': 'A reduction in major concern counts is not proof of scientific correctness. '
                'The provided drafts, provider outputs and absence of external human review must be considered.',
        'rounds': rounds,
    }
    summary = out / 'iteration_report.json'
    summary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'status': report['status'], 'rounds': len(rounds),
            'major_concerns_by_round': [row['assessment']['admitted_major_concerns'] for row in rounds],
            'scripted_test_only': report['scripted_test_only'], 'report_path': str(summary)}
