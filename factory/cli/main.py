"""researchctl: idea -> draft -> review -> code -> refine. Everything runs under your Claude Code login."""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from factory import sandbox
from factory.integrations.ledger import ledger_report, enabled
from factory.config import validate_context
from factory.quality import audit as quality_audit
from factory.agents.loop import AgentLoop
from factory.pipeline import Orchestrator
from factory.state import ProjectState
from factory.steps import code, review, write

ROOT = pathlib.Path(__file__).resolve().parents[2]
# Never create a user's research data inside site-packages on a normal pip install.
# Existing source-checkout workspaces continue to work; users may override via env.
_legacy = ROOT / "workspaces"
WORKSPACES = (pathlib.Path(os.environ["PAPERFACTORY_WORKSPACES"]).expanduser()
              if os.environ.get("PAPERFACTORY_WORKSPACES")
              else (_legacy if _legacy.is_dir() else
                    pathlib.Path.home() / ".local" / "share" / "paperfactory" / "workspaces"))


INPUTS = ("topic.md OR ideas.json (S1)", "experimental_log.md, optional setup notes (S2)",
          "data/, optional datasets for the sandbox (S4)", "context.json, optional run options")


def doctor():
    checks = {"python": {"status": "PASS", "detail": sys.version.split()[0]}}
    path = shutil.which("pdflatex")
    checks["pdflatex"] = {"status": "PASS" if path else "BLOCK", "detail": path or "not found"}
    for provider in ("claude", "codex"):
        health = AgentLoop(provider).healthcheck()
        checks[f"{provider}_cli"] = {
            "status": health["status"],
            "detail": health.get("detail", health.get("authentication", "unavailable")),
            "remedy": health.get("remedy", "")}
    from factory.integrations.paper_orchestra import (resolve_skills_dir,
                                                       bundled_vendor_present)
    try:
        resolved_skills = resolve_skills_dir()
        ready = bundled_vendor_present() if resolved_skills == write.SKILLS_DIR.resolve() else True
        checks["paperorchestra_skills"] = {
            "status": "PASS" if ready else "BLOCK",
            "detail": str(resolved_skills),
            "remedy": "" if ready else "restore vendored PaperOrchestra source prompts"}
    except ValueError as exc:
        checks["paperorchestra_skills"] = {
            "status": "BLOCK", "detail": str(exc),
            "remedy": "restore the bundled skills/paper-orchestra directory"}
    lean = (review.REFEREE_DIR / "core" / "LEAN_CORE_REVIEWER_PROMPT.md").is_file()
    checks["referee_agent"] = {
        "status": "PASS" if lean else "WARN",
        "detail": str(review.REFEREE_DIR) if lean
        else "Referee-Lean-v2 not unpacked; review falls back to the light reviewer"}
    checks["papercompiler"] = {
        "status": "PASS" if (code.PAPERCOMPILER / "codes" / "5_engineering.py").is_file() else "BLOCK",
        "detail": str(code.PAPERCOMPILER)}
    checks["docker"] = sandbox.healthcheck()
    try:
        from researchledger.schema_validation import validate_instance
        checks["researchledger"] = {"status": "PASS" if not validate_instance("run", {
            "schema_version": "2.0", "run_id": "R0001", "status": "completed",
            "started_at": "2026-01-01T00:00:00Z", "command": "true",
            "command_argv": ["true"], "exit_code": 0}) else "BLOCK",
            "detail": "ResearchLedger validator and schemas available"}
    except (ImportError, OSError, ValueError) as exc:
        checks["researchledger"] = {"status": "BLOCK", "detail": str(exc)}
    try:
        import matplotlib  # noqa: F401
        checks["matplotlib"] = {"status": "PASS", "detail": "figures will be drawn from results"}
    except ImportError:
        checks["matplotlib"] = {"status": "WARN", "detail": "missing; figures stay as placeholders",
                                "remedy": "pip install matplotlib"}
    has_writer_cli = any(checks[f"{p}_cli"]["status"] == "PASS"
                         for p in ("claude", "codex"))
    steps = {
        "S1-S3 (idea, draft, review)": has_writer_cli and all(
            checks[k]["status"] == "PASS" for k in ("pdflatex", "paperorchestra_skills")),
        "S4-S5 (code, refine)": has_writer_cli and all(
            checks[k]["status"] == "PASS" for k in ("papercompiler", "docker", "pdflatex")),
    }
    return {"factory_status": "READY" if all(steps.values()) else "BLOCKED",
            "steps_ready": steps, "checks": checks}


def project_slug(name):
    """Keep workspace names readable and impossible to use as a filesystem path."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("project name cannot be empty")
    if any(c in name for c in ("/", "\\", ":")) or name.strip() in {".", ".."}:
        raise ValueError("project name must not contain paths or directory separators")
    slug = "-".join(name.strip().lower().split())
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?", slug):
        raise ValueError("project name must use letters, numbers, hyphens or underscores (max 64)")
    return slug


def init_project(name):
    project_id = project_slug(name)
    workspace = WORKSPACES / project_id
    if workspace.exists():
        raise ValueError(f"workspace already exists: {workspace}")
    (workspace / "_inputs").mkdir(parents=True)
    from factory.io import atomic_json
    from researchledger.workspace import init_workspace
    init_workspace(workspace)
    atomic_json(workspace / "_inputs" / "context.json", {
        "science_mode": "exploration", "ledger_enabled": True, "allow_network_install": False,
        "code_mode": "agent", "review_agent": "auto"})
    from factory.science.protocol import scaffold as protocol_scaffold
    from factory.science.literature import scaffold_prior_art
    protocol_scaffold(workspace)
    scaffold_prior_art(workspace)
    ProjectState(project_id).save(workspace / "state.json")
    return {"project_id": project_id, "workspace": str(workspace), "state": "INITIALIZED",
            "next": "put in _inputs/: " + "; ".join(INPUTS)}


def workspace_for(project_id):
    workspace = WORKSPACES / project_slug(project_id)
    if workspace.is_symlink() or not workspace.resolve().is_relative_to(WORKSPACES.resolve()):
        raise ValueError("workspace must be a real directory inside workspaces/")
    if not workspace.is_dir():
        raise ValueError(f"unknown project: {project_id}")
    return workspace


def load_context(workspace):
    """Run options (models, template, thresholds, code mode) live in `_inputs/context.json`."""
    path = workspace / "_inputs" / "context.json"
    return validate_context(json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {})


def run_command(project_id, start=None, stop=None, resume=False, retry_budget=1):
    workspace = workspace_for(project_id)
    return Orchestrator(workspace, load_context(workspace),
                        retry_budget=retry_budget).run(start, stop, resume=resume)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="researchctl")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    init = commands.add_parser("init", help="create a project workspace")
    init.add_argument("name")
    status = commands.add_parser("status")
    status.add_argument("project_id")
    audit_parser = commands.add_parser("audit", help="write honest evidence/readiness audit")
    audit_parser.add_argument("project_id")
    ledger_parser = commands.add_parser("ledger", help="validate claim → evidence → Docker run provenance")
    ledger_parser.add_argument("project_id")
    protocol_cmd = commands.add_parser('protocol', help='scaffold, lock, or inspect a research protocol')
    protocol_cmd.add_argument('operation', choices=['scaffold', 'lock', 'check'])
    protocol_cmd.add_argument('project_id')
    claims_cmd = commands.add_parser('claims', help='scaffold, bind, or check quantitative claim links')
    claims_cmd.add_argument('operation', choices=['scaffold', 'bind', 'check'])
    claims_cmd.add_argument('project_id')
    literature_cmd = commands.add_parser('literature', help='DOI metadata and prior-art controls')
    literature_cmd.add_argument('operation', choices=['verify', 'scaffold', 'audit'])
    literature_cmd.add_argument('project_id')
    literature_cmd.add_argument('--doi')
    reproduce_cmd = commands.add_parser('reproduce-isolated', help='repeat the experiment in restricted Docker')
    reproduce_cmd.add_argument('project_id')
    reproduce_cmd.add_argument('--abs-tol', type=float, default=1e-7)
    reproduce_cmd.add_argument('--rel-tol', type=float, default=1e-5)
    science_cmd = commands.add_parser('science-audit', help='inspect automated scientific integrity gates')
    science_cmd.add_argument('project_id')
    idea_cmd = commands.add_parser('idea-discovery', help='inspect or safely prepare the bundled V5 research agent')
    idea_cmd.add_argument('operation', choices=['inspect', 'prepare', 'run', 'adopt', 'phase-audit'])
    idea_cmd.add_argument('project_id', nargs='?', help='project ID required for prepare/run')
    idea_cmd.add_argument('--topic', help='research question for the native V5 run')
    idea_cmd.add_argument('--paper', action='append', default=[], help='source article PDF/TXT/MD; repeat flag')
    idea_cmd.add_argument('--no-quality', action='store_true', help='disable optional vendor quality prompts')
    idea_cmd.add_argument('--with-embeddings', action='store_true', help='enable heavier embedding model dependencies')
    idea_cmd.add_argument('--provider', choices=['api','claude','codex'], default='api', help='API or existing Claude Code/Codex CLI login')
    idea_cmd.add_argument('--dry-run', action='store_true', help='validate setup and report command without model calls')
    idea_cmd.add_argument('--timeout', type=int, default=3600)
    idea_cmd.add_argument('--idea-id', help='V5 survivor ID for explicit S1 adoption')
    idea_cmd.add_argument('--metric', help='observable used for falsification in Factory')
    idea_cmd.add_argument('--threshold', type=float, help='numeric rejection threshold from your protocol')
    idea_cmd.add_argument('--falsifier-statement', help='concrete result that rejects the hypothesis')
    idea_cmd.add_argument('--strict-phases', action='store_true', help='require recorded valid Phase 10-16 artifacts for adoption')
    idea_cmd.add_argument('--acknowledge-manual', action='store_true', help='operator checked the V5 proposal, its science and numeric falsifier')
    referee_cmd = commands.add_parser('referee', help='run the actual bundled Referee engine (separate from Factory reviewer)')
    referee_sub = referee_cmd.add_subparsers(dest='referee_operation', required=True)
    referee_inspect = referee_sub.add_parser('inspect', help='offline native manuscript/package inspection')
    referee_inspect.add_argument('paths', nargs='+')
    referee_inspect.add_argument('--output')
    referee_review = referee_sub.add_parser('review', help='run full native Referee review')
    referee_review.add_argument('project_id')
    referee_review.add_argument('manuscript')
    referee_review.add_argument('--provider', choices=['openai-compatible', 'scripted'], default='openai-compatible')
    referee_review.add_argument('--model')
    referee_review.add_argument('--scripted-responses')
    referee_review.add_argument('--mode', choices=['standard', 'deep', 'exhaustive'], default='deep')
    referee_review.add_argument('--pipeline', choices=['lean', 'legacy'], default='lean')
    referee_review.add_argument('--profile')
    referee_review.add_argument('--search-backend', choices=['none','federated','scripted'])
    referee_review.add_argument('--prior-manuscript')
    referee_review.add_argument('--timeout', type=int, default=1200)
    referee_iterate = referee_sub.add_parser('iterate', help='re-review a sequence of human/Factory-edited drafts')
    referee_iterate.add_argument('project_id')
    referee_iterate.add_argument('manuscripts', nargs='+')
    referee_iterate.add_argument('--provider', choices=['openai-compatible', 'scripted'], default='openai-compatible')
    referee_iterate.add_argument('--model')
    referee_iterate.add_argument('--fixture', action='append', default=[], help='one scripted JSON fixture per round; DEMO ONLY')
    referee_iterate.add_argument('--mode', choices=['standard', 'deep', 'exhaustive'], default='deep')
    referee_iterate.add_argument('--pipeline', choices=['lean', 'legacy'], default='lean')
    referee_iterate.add_argument('--search-backend', choices=['none','federated','scripted'])
    referee_iterate.add_argument('--timeout', type=int, default=1200)
    referee_cycle = referee_sub.add_parser('cycle', help='review successive drafts with the NEW Beihang Referee core/full engine and your rubric')
    referee_cycle.add_argument('project_id')
    referee_cycle.add_argument('manuscripts', nargs='+', help='one or more distinct manuscript versions')
    referee_cycle.add_argument('--provider', choices=['openai-compatible','scripted','claude','codex'], default='openai-compatible')
    referee_cycle.add_argument('--model')
    referee_cycle.add_argument('--pipeline', choices=['core','full'], default='core')
    referee_cycle.add_argument('--mode', choices=['standard','deep','exhaustive'], default='deep')
    referee_cycle.add_argument('--rubric', help='supplemental trusted reviewer prompt file; defaults to bundled Prompt(3).txt rubric')
    referee_cycle.add_argument('--scorecard', action='store_true')
    referee_cycle.add_argument('--search-backend', choices=['none','federated','scripted'])
    referee_cycle.add_argument('--fixture', action='append', default=[], help='scripted responses JSON: one per draft, offline tests only')
    referee_cycle.add_argument('--max-rounds', type=int, default=6)
    referee_cycle.add_argument('--timeout', type=int, default=1800)
    referee_compare = referee_sub.add_parser('compare', help='native manuscript revision difference')
    referee_compare.add_argument('old')
    referee_compare.add_argument('new')
    referee_compare.add_argument('--output', required=True)
    method_parser = commands.add_parser("methodology", help="show stage-specific research method")
    method_parser.add_argument("stage", choices=["idea", "experiment", "review"])
    run = commands.add_parser(
        "run", help="run S1 idea -> S2 draft -> S3 review -> S4 code -> S5 refine")
    run.add_argument("--project", required=True)
    run.add_argument("--from", dest="start", help="first stage: S1 .. S5")
    run.add_argument("--to", dest="stop", help="last stage, inclusive")
    run.add_argument("--retry-budget", type=int, default=1)
    resume = commands.add_parser("resume", help="continue a run, re-validating checkpoints")
    resume.add_argument("project_id")
    test = commands.add_parser("test")
    test.add_argument("suite", nargs="?", default="unit", choices=["unit"])
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "init":
            result = init_project(args.name)
        elif args.command == "status":
            workspace = workspace_for(args.project_id)
            controller = Orchestrator(workspace, load_context(workspace))
            result = controller.state().to_dict()
            result["effective_state"] = controller.effective_state()
            result["verified_stages"] = list(controller.completed())
        elif args.command == "ledger":
            result = ledger_report(workspace_for(args.project_id))
        elif args.command == 'protocol':
            from factory.science import protocol
            workspace = workspace_for(args.project_id)
            if args.operation == 'scaffold':
                result = protocol.scaffold(workspace)
            elif args.operation == 'lock':
                result = protocol.lock(workspace)
            else:
                ok, issues = protocol.check(workspace, {'science_mode': 'validation'})
                result = {'status': 'PASS' if ok else 'BLOCKED', 'issues': issues}
        elif args.command == 'claims':
            from factory.science import claims
            workspace = workspace_for(args.project_id)
            if args.operation == 'scaffold':
                result = claims.scaffold(workspace)
            elif args.operation == 'bind':
                result = claims.evaluate(workspace, write=True)
            else:
                ok, issues = claims.check(workspace)
                result = {'status': 'PASS' if ok else 'BLOCKED', 'issues': issues}
        elif args.command == 'literature':
            from factory.science import literature
            workspace = workspace_for(args.project_id)
            if args.operation == 'verify':
                if not args.doi:
                    raise ValueError('literature verify requires --doi')
                result = literature.verify_doi(workspace, args.doi)
            elif args.operation == 'scaffold':
                result = literature.scaffold_prior_art(workspace)
            else:
                result = literature.audit(workspace)
        elif args.command == 'reproduce-isolated':
            from factory.science.reproduction import repeat
            workspace = workspace_for(args.project_id)
            result = repeat(workspace, load_context(workspace), abs_tol=args.abs_tol, rel_tol=args.rel_tol)
        elif args.command == 'science-audit':
            from factory.science.gates import audit
            workspace = workspace_for(args.project_id)
            result = audit(workspace, load_context(workspace))
        elif args.command == 'idea-discovery':
            from factory.integrations.idea_discovery import inspect, prepare, run as run_v5
            if args.operation == 'inspect':
                result = inspect()
            else:
                if not args.project_id:
                    raise ValueError('idea-discovery prepare/run requires a project ID')
                workspace = workspace_for(args.project_id)
                if args.operation == 'prepare':
                    result = prepare(workspace)
                elif args.operation == 'phase-audit':
                    from factory.integrations.idea_discovery import phase_audit
                    if not args.idea_id:
                        raise ValueError('phase-audit requires --idea-id')
                    result = phase_audit(workspace, idea_id=args.idea_id)
                elif args.operation == 'adopt':
                    from factory.integrations.idea_discovery import adopt
                    result = adopt(workspace, idea_id=args.idea_id, metric=args.metric,
                        threshold=args.threshold, falsifier_statement=args.falsifier_statement,
                        operator_acknowledgement=args.acknowledge_manual, strict_phases=args.strict_phases)
                else:
                    result = run_v5(workspace, topic=args.topic, papers=args.paper,
                        skip_embeddings=not args.with_embeddings, no_quality=args.no_quality,
                        dry_run=args.dry_run, timeout=args.timeout, provider=args.provider)
        elif args.command == 'referee':
            from factory.integrations import referee_native as native
            if args.referee_operation == 'inspect':
                result = native.inspect(args.paths, output=args.output)
            elif args.referee_operation == 'compare':
                result = native.compare(args.old, args.new, output=args.output)
            elif args.referee_operation == 'cycle':
                from factory.integrations.referee_beihang import review_cycle
                result = review_cycle(workspace_for(args.project_id), args.manuscripts,
                    provider=args.provider, model=args.model, pipeline=args.pipeline,
                    mode=args.mode, rubric=args.rubric, scorecard=args.scorecard,
                    search_backend=args.search_backend, fixtures=args.fixture,
                    max_rounds=args.max_rounds, timeout=args.timeout)
            elif args.referee_operation == 'iterate':
                result = native.iterate(workspace_for(args.project_id), args.manuscripts,
                    provider=args.provider, model=args.model, scripted_responses=args.fixture,
                    mode=args.mode, pipeline=args.pipeline, search_backend=args.search_backend,
                    timeout=args.timeout)
            else:
                result = native.review(workspace_for(args.project_id), args.manuscript,
                    provider=args.provider, model=args.model,
                    scripted_responses=args.scripted_responses, mode=args.mode,
                    pipeline=args.pipeline, profile=args.profile,
                    search_backend=args.search_backend, timeout=args.timeout,
                    prior_manuscript=args.prior_manuscript)
        elif args.command == "methodology":
            from factory.integrations.methodology import brief
            result = {"stage": args.stage, "methodology": brief(args.stage)}
        elif args.command == "audit":
            workspace = workspace_for(args.project_id)
            result = quality_audit(workspace, load_context(workspace))
        elif args.command == "run":
            result = run_command(args.project, args.start, args.stop, False, args.retry_budget)
        elif args.command == "resume":
            result = run_command(args.project_id, resume=True)
        else:
            return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                                   "-p", "test_*.py", "-v"], cwd=ROOT, shell=False).returncode
        print(json.dumps(result, indent=2))
        return 1 if (result.get("factory_status") == "BLOCKED"
                     or result.get("status") == "BLOCKED") else 0
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
