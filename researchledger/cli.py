"""The `researchledger` command line entry point.

Commands: init, run, validate, report, trace, inspect, reproduce, index,
migrate, evidence create, validate-paper. See reference/run-ledger.md for
the full contract. `run`, `validate`, and `migrate` refresh the cached
`.researchledger/index.json` on the way out (best-effort — a failure to
refresh the cache never fails the command that triggered it).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .evidence import create_evidence
from .indexer import write_index
from .migrate import migrate_v1_to_v2
from .migrate import render as render_migration
from .report import render_json, render_text
from .reproduce import DEFAULT_TOLERANCE, DEFAULT_Z_SCORE
from .reproduce import render as render_reproduction
from .reproduce import reproduce as run_reproduce
from .runner import run_command
from .trace import trace
from .validate_paper import audit_paper
from .validate_paper import render as render_paper_audit
from .validator import validate
from .workspace import WorkspaceError, find_workspace, init_workspace


def _refresh_index(ws) -> None:
    try:
        write_index(ws)
    except Exception as exc:  # noqa: BLE001 - a cache refresh must never fail the real command
        print(f"warning: could not refresh .researchledger/index.json: {exc}", file=sys.stderr)


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve() if args.path else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    ws = init_workspace(target)
    print(f"Initialized ResearchLedger run ledger at {ws.root}")
    if args.path:
        print(f"cd {args.path}")
    _refresh_index(ws)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    command = args.command
    if not command:
        print("error: no command given. Usage: researchledger run [options] -- <command>", file=sys.stderr)
        return 2
    ws = find_workspace()
    try:
        manifest = run_command(
            ws,
            command,
            seed=args.seed,
            claims=args.claim or [],
            plan=args.plan,
            metrics_path=Path(args.metrics) if args.metrics else None,
            timeout=args.timeout,
            retries=args.retries,
            env_allowlist=args.env or [],
            data=args.data or [],
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"\n{manifest['run_id']}: {manifest['status']} (exit code {manifest['exit_code']})")
    _refresh_index(ws)
    return 0 if manifest["status"] == "completed" else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    ws = find_workspace()
    result = validate(ws)
    print(render_json(result, strict=args.strict) if args.json else render_text(result, strict=args.strict))
    _refresh_index(ws)
    return 1 if not result.passed(args.strict) else 0


def _cmd_report(args: argparse.Namespace) -> int:
    ws = find_workspace()
    result = validate(ws)
    print(render_json(result) if args.json else render_text(result))
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    ws = find_workspace()
    try:
        print(trace(ws, args.id))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    ws = find_workspace()
    manifest_path = ws.runs_dir / args.run_id / "manifest.json"
    if not manifest_path.exists():
        print(f"error: no such run: {args.run_id}", file=sys.stderr)
        return 1
    print(manifest_path.read_text(encoding="utf-8").rstrip())
    return 0


def _cmd_reproduce(args: argparse.Namespace) -> int:
    ws = find_workspace()
    manifest_path = ws.runs_dir / args.run_id / "manifest.json"
    if not manifest_path.exists():
        print(f"error: no such run: {args.run_id}", file=sys.stderr)
        return 1

    result = run_reproduce(
        ws,
        args.run_id,
        tolerance=args.tolerance,
        isolate=not args.no_isolate,
        keep_worktree=args.keep_worktree,
        repeat=args.repeat,
        z_score=args.z_score,
    )
    print(render_reproduction(result, args.tolerance))
    _refresh_index(ws)
    return 0 if result.reproduced else 1


def _cmd_index(args: argparse.Namespace) -> int:
    ws = find_workspace()
    path = write_index(ws)
    print(f"Wrote {path}")
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    ws = find_workspace()
    report = migrate_v1_to_v2(ws, dry_run=args.dry_run)
    print(render_migration(report))
    if not args.dry_run:
        _refresh_index(ws)
    return 1 if report.malformed else 0


def _cmd_evidence_create(args: argparse.Namespace) -> int:
    ws = find_workspace()
    try:
        evidence = create_evidence(
            ws,
            from_run=args.from_run,
            supports=args.supports or [],
            contradicts=args.contradicts or [],
            source_kind=args.source_kind,
            status=args.status,
            name=args.name,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {evidence.id} ({evidence.status}, source_kind={evidence.source_kind})")
    _refresh_index(ws)
    return 0


def _cmd_validate_paper(args: argparse.Namespace) -> int:
    ws = find_workspace()
    paper_path = Path(args.path)
    if not paper_path.exists():
        print(f"error: no such file: {paper_path}", file=sys.stderr)
        return 1
    result = audit_paper(ws, paper_path)
    if args.json:
        print(
            json.dumps(
                {
                    "quantitative_assertions": result.quantitative_assertions,
                    "linked_to_claims": result.linked_to_claims,
                    "backed_by_verified_evidence": result.backed_by_verified_evidence,
                    "backed_by_reproducible_runs": result.backed_by_reproducible_runs,
                    "unsupported": result.unsupported,
                    "stale_evidence_usage": result.stale_evidence_usage,
                    "unsupported_sentences": result.unsupported_sentences,
                },
                indent=2,
            )
        )
    else:
        print(render_paper_audit(result))
    return 1 if result.unsupported else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="researchledger",
        description="Immutable run ledger, deterministic validator and claim-to-artifact "
        "tracing for ResearchLedger research workspaces.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_init = sub.add_parser("init", help="Bootstrap the run ledger, here or at a new path")
    p_init.add_argument("path", nargs="?", default=None)
    p_init.set_defaults(func=_cmd_init, command=[])

    p_run = sub.add_parser(
        "run",
        help="Execute a command as a tracked, immutable run",
        description="Usage: researchledger run [options] -- <command to execute>",
    )
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--claim", action="append", help="Claim id this run targets (repeatable)")
    p_run.add_argument("--plan", default=None)
    p_run.add_argument("--metrics", default=None, help="Path to a metrics JSON file the command produced")
    p_run.add_argument("--timeout", type=int, default=None, help="Seconds before the run is killed")
    p_run.add_argument("--retries", type=int, default=0, help="Extra attempts after a non-zero exit")
    p_run.add_argument(
        "--data", action="append",
        help="Path to an input dataset (file or directory) to hash and record (repeatable)",
    )
    p_run.add_argument(
        "--env", action="append", metavar="NAME",
        help="Allowlist this environment variable's value into the manifest (repeatable). "
        "Never captures anything not explicitly named.",
    )
    p_run.set_defaults(func=_cmd_run, command=[])

    p_validate = sub.add_parser("validate", help="Run the deterministic integrity validator")
    p_validate.add_argument(
        "--strict", action="store_true",
        help="Promote strict-escalating warnings to errors; exit non-zero on any error",
    )
    p_validate.add_argument("--json", action="store_true")
    p_validate.set_defaults(func=_cmd_validate, command=[])

    p_trace = sub.add_parser(
        "trace", help="Trace the provenance chain for a claim/evidence id, or reverse-trace from a run id"
    )
    p_trace.add_argument("id")
    p_trace.set_defaults(func=_cmd_trace, command=[])

    p_inspect = sub.add_parser("inspect", help="Print a run's manifest")
    p_inspect.add_argument("run_id")
    p_inspect.set_defaults(func=_cmd_inspect, command=[])

    p_reproduce = sub.add_parser("reproduce", help="Re-execute a run's exact command, isolated, and compare results")
    p_reproduce.add_argument("run_id")
    p_reproduce.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    p_reproduce.add_argument(
        "--no-isolate", action="store_true", help="Re-run in place instead of an isolated git worktree"
    )
    p_reproduce.add_argument(
        "--keep-worktree", action="store_true", help="Don't delete the isolated worktree afterward"
    )
    p_reproduce.add_argument(
        "--repeat", type=int, default=1,
        help="Reproduce N times and compare the original against the resulting distribution, not one point",
    )
    p_reproduce.add_argument(
        "--z-score", type=float, default=DEFAULT_Z_SCORE,
        help="How many standard deviations of the reproduced distribution count as a match (with --repeat > 1)",
    )
    p_reproduce.set_defaults(func=_cmd_reproduce, command=[])

    p_report = sub.add_parser("report", help="Print the integrity report (non-gating)")
    p_report.add_argument("--json", action="store_true")
    p_report.set_defaults(func=_cmd_report, command=[])

    p_index = sub.add_parser("index", help="Rebuild .researchledger/index.json")
    p_index.set_defaults(func=_cmd_index, command=[])

    p_migrate = sub.add_parser("migrate", help="Migrate evidence/claims/decisions from schema v1 to v2")
    p_migrate.add_argument("--from", dest="from_version", choices=["v1"], required=True)
    p_migrate.add_argument("--dry-run", action="store_true")
    p_migrate.set_defaults(func=_cmd_migrate, command=[])

    p_paper = sub.add_parser(
        "validate-paper",
        help="Audit a manuscript's quantitative assertions against the claim/evidence graph",
    )
    p_paper.add_argument("path")
    p_paper.add_argument("--json", action="store_true")
    p_paper.set_defaults(func=_cmd_validate_paper, command=[])

    p_evidence = sub.add_parser("evidence", help="Evidence record operations")
    evidence_sub = p_evidence.add_subparsers(dest="evidence_command", required=True)
    p_evidence_create = evidence_sub.add_parser("create", help="Create a new, graph-consistent evidence record")
    p_evidence_create.add_argument("--from-run", dest="from_run", default=None)
    p_evidence_create.add_argument("--supports", action="append", help="Claim id this evidence supports (repeatable)")
    p_evidence_create.add_argument(
        "--contradicts", action="append", help="Claim id this evidence contradicts (repeatable)"
    )
    p_evidence_create.add_argument("--source-kind", dest="source_kind", default=None)
    p_evidence_create.add_argument("--status", default="checked")
    p_evidence_create.add_argument("--name", default=None)
    p_evidence_create.set_defaults(func=_cmd_evidence_create, command=[])

    return parser


def _use_utf8_output() -> None:
    # Report text uses U+2500/2193/2713/2717 (box-drawing, arrow, check, cross).
    # Some Windows consoles default to a non-UTF-8 codepage (e.g. GBK/cp1252)
    # that can't encode those and would otherwise crash print() outright.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _use_utf8_output()
    argv = list(argv if argv is not None else sys.argv[1:])

    # `researchledger run [options] -- <command>` — split off everything after
    # the first literal `--` before argparse ever sees it, so the wrapped
    # command's own flags are never mistaken for researchledger's.
    passthrough: list[str] = []
    if "run" in argv and "--" in argv:
        idx = argv.index("--")
        passthrough = argv[idx + 1 :]
        argv = argv[:idx]

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "run":
        args.command = passthrough

    try:
        return args.func(args)
    except WorkspaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
