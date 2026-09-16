#!/usr/bin/env python3
"""ConvFusion UserPromptSubmit hook -- "harness style" per-turn context injection.

The original DeepSeek-Harness ConvFusion plugin re-evaluated a Research Context
system-prompt section on every single model turn (ctx.systemPrompt.context()).
Claude Code has no such hook point on its own, but it DOES run a plain local
script on 'UserPromptSubmit' -- once per turn, before Claude sees the prompt --
and whatever that script prints to stdout is added as context Claude can see.
This script is that hook: it never calls a model, never needs an API key, and
never fails loudly -- if anything goes wrong, or this isn't a research
workspace, it just prints nothing and exits 0.

Wired up via ../.claude-plugin/plugin.json + hooks/hooks.json.
"""
import json
import os
import re
import sys
import glob

# ---- fixed default stage table (mirrors the `research-process` skill's -------
# ---- defaults; edit this list directly to customize, same as any skill) -----
STAGES = [
    ("problem", "Problem Framing", "falsifiable research questions + scope (project.md)"),
    ("literature", "Literature", "literature evidence records (research/evidence/)"),
    ("innovation", "Innovation", "testable claims/hypotheses (research/claims/)"),
    ("method", "Method Design", "a method design (a plan naming method/design/approach)"),
    ("experiment", "Experimentation", "experiment artifacts (experiments/<name>/results/)"),
    ("analysis", "Analysis", "confirmed evidence (status supported/verified)"),
    ("decision", "Decision", "recorded decisions (research/decisions/)"),
    ("writing", "Writing", "paper body (papers/<id>/paper.md)"),
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(path):
    """Flat `key: value` frontmatter only -- matches this plugin's file convention.
    No PyYAML dependency on purpose: this must run on whatever Python the user has."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def is_research_workspace(root):
    return os.path.isfile(os.path.join(root, "project.md")) or os.path.isfile(
        os.path.join(root, "research-state.md")
    )


def count_glob(pattern):
    return len(glob.glob(pattern))


def status_of(path):
    return parse_frontmatter(path).get("status", "")


def build_context(root):
    lines = []

    project_fm = parse_frontmatter(os.path.join(root, "project.md"))
    topic = project_fm.get("topic", "(untitled)")

    evidence_files = glob.glob(os.path.join(root, "research", "evidence", "E*.md"))
    claim_files = glob.glob(os.path.join(root, "research", "claims", "C*.md"))
    decision_files = glob.glob(os.path.join(root, "research", "decisions", "D*.md"))
    plan_files = glob.glob(os.path.join(root, "plans", "*.md"))

    evidence_settled = sum(1 for p in evidence_files if status_of(p) in ("supported", "verified"))
    claims_supported = sum(1 for p in claim_files if status_of(p) in ("supported", "verified"))
    plans_ready = sum(1 for p in plan_files if status_of(p) in ("ready", "refined", "executing"))

    has_literature_evidence = any(
        parse_frontmatter(p).get("source_kind") == "literature" for p in evidence_files
    )
    has_method_plan = any(
        re.search(r"method|design|approach", os.path.basename(p), re.I) for p in plan_files
    )
    experiment_results = glob.glob(os.path.join(root, "experiments", "*", "results", "*"))
    paper_files = glob.glob(os.path.join(root, "papers", "*", "paper.md"))

    signals = {
        "problem": bool(project_fm) and "topic" in project_fm,
        "literature": has_literature_evidence,
        "innovation": len(claim_files) > 0,
        "method": has_method_plan,
        "experiment": len(experiment_results) > 0,
        "analysis": evidence_settled > 0,
        "decision": len(decision_files) > 0,
        "writing": len(paper_files) > 0,
    }

    current_stage = None
    for stage_id, label, produces in STAGES:
        if not signals.get(stage_id):
            current_stage = (label, produces)
            break

    lines.append(f"[ConvFusion] Research workspace: \"{topic}\"")
    if current_stage:
        lines.append(f"Stage: {current_stage[0]} -- next: {current_stage[1]}")
    else:
        lines.append("Stage: every default stage has landed artifacts -- open-ended continued research.")

    lines.append(
        f"Evidence: {len(evidence_files)} ({evidence_settled} settled) | "
        f"Claims: {len(claim_files)} ({claims_supported} supported) | "
        f"Decisions: {len(decision_files)} | Plans: {len(plan_files)} ({plans_ready} ready/executing)"
    )

    if paper_files:
        first_paper_dir = os.path.dirname(paper_files[0])
        meta = parse_frontmatter(os.path.join(first_paper_dir, "metadata.md"))
        pid = meta.get("id", os.path.basename(first_paper_dir))
        pver = meta.get("version", "?")
        pstatus = meta.get("status", "?")
        lines.append(f"Paper: {pid} v{pver} [{pstatus}]")

    lines.append("(Auto-context from the ConvFusion plugin -- run /research for the full picture or to act.)")
    return "\n".join(lines)


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    root = payload.get("cwd") or os.getcwd()

    try:
        if not is_research_workspace(root):
            return  # not a ConvFusion workspace -- stay completely silent
        print(build_context(root))
    except Exception:
        # A hook that crashes noisily on every turn is worse than one that
        # says nothing this turn -- never let this become visible failure.
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
