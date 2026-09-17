#!/usr/bin/env python3
"""ResearchLedger UserPromptSubmit hook -- "harness style" per-turn context.

Claude Code runs a plain local script on 'UserPromptSubmit' once per turn,
before Claude sees the prompt, and whatever it prints to stdout becomes
context Claude can see. This script is that hook: it never calls a model,
never needs an API key, and never fails loudly -- if anything goes wrong, or
this isn't a research workspace, it just prints nothing and exits 0. That
fail-open contract is deliberate and specific to *this* hook: the CLI tools
in researchledger/ (validate, run, migrate, reproduce) do the opposite --
they fail closed and report errors explicitly. See
reference/run-ledger.md#fail-open-vs-fail-closed.

v2 change: this reports research *state* -- counts and open issues -- and
does not prescribe a "current stage." A fixed stage table conflicts with
this project's own "no fixed pipeline" design; deciding what to do next is
the skills' and the human's job, not this hook's. State is read from the
cached `.researchledger/index.json` (built by `researchledger validate`/
`run`/`index`) when present, which keeps this hook a single small read
regardless of workspace size; it falls back to a light, dependency-free
scan (flat `key: value` frontmatter fields only -- no PyYAML here on
purpose, since this must run on whatever bare python3 the user has) when no
index exists yet.

Wired up via ../.claude-plugin/plugin.json + hooks/hooks.json.
"""
import glob
import json
import os
import re
import sys

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(path):
    """Flat `key: value` scalar fields only. Multi-line YAML list values
    (the v2 canonical form for e.g. `supports:`) are silently skipped, not
    misparsed -- every field this fallback actually reads (status,
    source_kind, topic) stays a single-line scalar in both v1 and v2."""
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
        if ":" in line and not line.startswith((" ", "-")):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def is_research_workspace(root):
    return (
        os.path.isfile(os.path.join(root, "project.md"))
        or os.path.isfile(os.path.join(root, "research-state.md"))
        or os.path.isdir(os.path.join(root, "research"))
        or os.path.isdir(os.path.join(root, ".researchledger"))
    )


def status_of(path):
    return parse_frontmatter(path).get("status", "")


def load_index(root):
    index_path = os.path.join(root, ".researchledger", "index.json")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def method_specified(root):
    state_path = os.path.join(root, "research-state.md")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return False
    return bool(re.search(r"^##\s*Method\s*$", text, re.MULTILINE))


def render_from_index(root, index, topic):
    claim_counts = index.get("claim_status_counts", {})
    evidence_counts = index.get("evidence_status_counts", {})
    file_counts = index.get("file_counts", {})

    supported = claim_counts.get("supported", 0)
    unresolved = sum(v for k, v in claim_counts.items() if k != "supported")
    verified_ev = evidence_counts.get("verified", 0)
    provisional_ev = evidence_counts.get("observed", 0) + evidence_counts.get("checked", 0)
    literature_ev = index.get("literature_evidence", 0)

    lines = [f'ResearchLedger -- "{topic}"' if topic else "ResearchLedger"]
    lines.append("")
    lines.append("Research state")
    lines.append(f"  Literature       {literature_ev} evidence record(s)")
    lines.append(f"  Hypotheses       {claim_counts.get('hypothesis', 0)} active")
    lines.append(f"  Method           {'specified' if method_specified(root) else 'not yet specified'}")
    lines.append(f"  Runs             {file_counts.get('runs', 0)} total")
    lines.append(f"  Evidence         {verified_ev} verified / {provisional_ev} provisional")
    lines.append(f"  Claims           {supported} supported / {unresolved} unresolved")
    lines.append(f"  Manuscript       {file_counts.get('papers', 0)} paper(s)")
    lines.append(f"  Integrity        {index.get('errors', 0)} error(s) / {index.get('warnings', 0)} warning(s)")

    top_issues = index.get("top_issues") or []
    if top_issues:
        lines.append("")
        lines.append("Recommended unresolved issue:")
        lines.append(f"  {top_issues[0]['message']}")

    lines.append("")
    lines.append("(Cached index from `researchledger validate` -- run /research or `researchledger report` for the full picture.)")
    return "\n".join(lines)


def render_from_scan(root, topic):
    """Dependency-free fallback when no .researchledger/index.json exists
    yet (e.g. before the first `researchledger run`/`validate`)."""
    evidence_files = glob.glob(os.path.join(root, "research", "evidence", "E*.md"))
    claim_files = glob.glob(os.path.join(root, "research", "claims", "C*.md"))
    decision_files = glob.glob(os.path.join(root, "research", "decisions", "D*.md"))
    run_dirs = glob.glob(os.path.join(root, "research", "runs", "R*"))

    verified_ev = sum(1 for p in evidence_files if status_of(p) == "verified")
    supported_claims = sum(1 for p in claim_files if status_of(p) == "supported")

    lines = [f'ResearchLedger -- "{topic}"' if topic else "ResearchLedger"]
    lines.append(
        f"Evidence: {len(evidence_files)} ({verified_ev} verified) | "
        f"Claims: {len(claim_files)} ({supported_claims} supported) | "
        f"Decisions: {len(decision_files)} | Runs: {len(run_dirs)}"
    )
    lines.append(
        "(No cached index yet -- run `researchledger validate` for a full, "
        "checked report; run /research to act.)"
    )
    return "\n".join(lines)


def build_context(root):
    project_fm = parse_frontmatter(os.path.join(root, "project.md"))
    topic = project_fm.get("topic", "")

    index = load_index(root)
    if index is not None:
        return render_from_index(root, index, topic)
    return render_from_scan(root, topic)


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    root = payload.get("cwd") or os.getcwd()

    try:
        if not is_research_workspace(root):
            return  # not a ResearchLedger workspace -- stay completely silent
        print(build_context(root))
    except Exception:
        # A hook that crashes noisily on every turn is worse than one that
        # says nothing this turn -- never let this become a visible failure.
        # (This fail-open behavior is specific to this hook -- see the
        # module docstring. researchledger's CLI tools fail closed.)
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
