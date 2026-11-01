"""Capability registry: agents, skills and providers with honest integration status.

Statuses (blueprint §3): integrated · available_standalone · optional · planned · disabled.
`integrated` is reserved for capabilities the web API can actually invoke and that an
integration test covers. Paths are checked on disk so a missing component is reported
as such rather than advertised.
"""
from __future__ import annotations

import shutil
import subprocess

from .config import REPO_ROOT, settings

REFEREE_LEAN = REPO_ROOT / "vendor" / "20- Paper Review Agent" / "Referee-Lean-v2"

AGENTS = [
    {"id": "claude_code_research_agent", "name": "Claude Code research agent", "category": "Orchestration",
     "status": "integrated", "implementation_ref": "webapi/app/claude_runner.py",
     "description": "Runs your locally authenticated Claude Code CLI inside the project workspace. "
                    "Takes a prompt, writes files (LaTeX, Markdown, data, code) and streams its steps.",
     "inputs": ["Prompt", "Project workspace files"], "outputs": ["Workspace files", "Run events", "Artifact hashes"],
     "permissions": "Read/Write/Edit in the workspace; Bash limited to pdflatex, bibtex, biber, latexmk; web search/fetch."},
    {"id": "manuscript_export", "name": "Manuscript export", "category": "Manuscript Production",
     "status": "integrated", "implementation_ref": "webapi/app/workspace.py",
     "description": "Deterministic server-side conversion: LaTeX → PDF (pdflatex, shell escape off) and "
                    "Markdown → Word (.docx).",
     "inputs": [".tex or .md file"], "outputs": [".pdf or .docx"], "permissions": "No model calls."},
    {"id": "paper_factory_s1_s3", "name": "Paper Factory S1–S3 (idea, draft, review)", "category": "Research Production",
     "status": "integrated", "implementation_ref": "factory/pipeline/stages.py",
     "description": "Idea generation with a numeric falsifiability gate, LaTeX drafting with empty result slots, "
                    "and a first structured review. Launched from Discover / Manuscripts / Peer Review.",
     "inputs": ["_inputs/topic.md", "_inputs/context.json"], "outputs": ["1_idea/", "2_paper/", "3_review/"],
     "permissions": "Your Claude Code login; pdflatex."},
    {"id": "paper_factory_s4_s5", "name": "Paper Factory S4–S5 (experiments, revision)", "category": "Execution",
     "status": "optional", "implementation_ref": "factory/steps/code.py",
     "description": "Sandboxed experiments and evidence-bound revision. Launchable from Manuscripts; needs Docker running.",
     "inputs": ["S1–S3 artifacts", "data/"], "outputs": ["4_code/results.json", "5_refine/"],
     "permissions": "Network-restricted Docker container."},
    {"id": "evidence_ledger", "name": "ResearchLedger evidence ledger", "category": "Scientific Verification",
     "status": "integrated", "implementation_ref": "researchledger/",
     "description": "Claim C### / evidence E### / run R#### graph with digests. Ledger report, readiness audit "
                    "and integrity gates run from the Evidence section (no model calls).",
     "inputs": ["Runs", "Claim bindings"], "outputs": ["Ledger report"], "permissions": "Local files."},
    {"id": "validation_gates", "name": "Protocol & integrity gates", "category": "Scientific Verification",
     "status": "integrated", "implementation_ref": "factory/science/",
     "description": "Protocol lock (with human approval), science audit. Validation mode itself stays opt-in.",
     "inputs": ["Protocol in _inputs/"], "outputs": ["Gate receipts"], "permissions": "Local files."},
    {"id": "beihang_referee", "name": "Beihang Referee (bundled)", "category": "Scientific Review",
     "status": "integrated", "implementation_ref": "factory/integrations/referee_beihang.py",
     "description": "Evidence-grounded specialist review run with your Claude login (`researchctl referee cycle "
                    "--provider claude`). Launched from Peer Review.",
     "inputs": ["Manuscript (.pdf .docx .tex .md .txt)"], "outputs": ["beihang_referee/runs/<run>/artifacts/review.md"],
     "permissions": "Your Claude Code login."},
    {"id": "referee_lean_v2", "name": "Referee Lean v2", "category": "Scientific Review",
     "status": "available_standalone", "implementation_ref": str(REFEREE_LEAN.relative_to(REPO_ROOT)).replace("\\", "/"),
     "description": "Specialist review engine (24 roles, 56 skills). Needs an OpenAI-compatible API key, so it is "
                    "not offered in the web app yet; use the Beihang Referee instead.",
     "inputs": ["Manuscript"], "outputs": ["review_report.json"], "permissions": "OpenAI-compatible provider."},
    {"id": "claude_workflows", "name": "Claude Code research workflows", "category": "Research Discovery",
     "status": "integrated", "implementation_ref": "webapi/app/workflows.py",
     "description": "Literature review, proposal, research design, manuscript writing, thesis conversion, language "
                    "editing, quick review and citation verification — each a fixed task with named output files.",
     "inputs": ["Form fields", "Workspace files"], "outputs": ["Named files per workflow"],
     "permissions": "Same as the Claude Code research agent."},
    {"id": "research_director", "name": "Research Director", "category": "Orchestration", "status": "planned",
     "implementation_ref": None, "description": "Multi-agent planner with approval gates.",
     "inputs": [], "outputs": [], "permissions": ""},
]


def agents() -> list[dict]:
    out = []
    for a in AGENTS:
        a = dict(a)
        ref = a.get("implementation_ref")
        local = ref and not ref.startswith("github.com") and "," not in ref
        a["implementation_present"] = bool(local and (REPO_ROOT / ref).exists()) if local else None
        out.append(a)
    return out


def skills() -> list[dict]:
    rows = []
    for d in sorted((REPO_ROOT / "skills").glob("*/")):
        rows.append({"id": d.name, "source": "skills/", "status": "available_standalone"})
    for d in sorted((REFEREE_LEAN / "skills").glob("*/")):
        rows.append({"id": d.name, "source": "Referee-Lean-v2/skills/", "status": "available_standalone"})
    return rows


def provider_health() -> list[dict]:
    claude = {"id": "claude_code_cli", "name": "Claude Code CLI", "status": "unavailable",
              "detail": "Not found on PATH. Install Claude Code and run `claude` once to log in."}
    if settings.claude_cmd:
        try:
            done = subprocess.run([*settings.claude_cmd, "--version"], capture_output=True, text=True,
                                  timeout=20, shell=False)
            if done.returncode == 0:
                claude.update(status="installed", detail=done.stdout.strip() +
                              " · login is checked on the first run (a failed login shows as a failed run).")
            else:
                claude["detail"] = (done.stderr or done.stdout)[-300:]
        except Exception as exc:
            claude["detail"] = str(exc)[:300]
    latex = {"id": "pdflatex", "name": "LaTeX (pdflatex)",
             "status": "installed" if shutil.which("pdflatex") else "unavailable",
             "detail": shutil.which("pdflatex") or "Install MiKTeX or TeX Live for PDF export."}
    try:
        import mammoth  # noqa: F401
        docx_preview = {"id": "mammoth", "name": "Word preview (mammoth)", "status": "installed", "detail": ""}
    except ImportError:
        docx_preview = {"id": "mammoth", "name": "Word preview (mammoth)", "status": "unavailable",
                        "detail": "pip install mammoth"}
    try:
        import docx  # noqa: F401
        docx_export = {"id": "python_docx", "name": "Word export (python-docx)", "status": "installed", "detail": ""}
    except ImportError:
        docx_export = {"id": "python_docx", "name": "Word export (python-docx)", "status": "unavailable",
                       "detail": "pip install python-docx"}
    codex = {"id": "codex_cli", "name": "Codex CLI", "status": "planned",
             "detail": "Used by factory/agents/session.py; not yet selectable in the web app."}
    return [claude, latex, docx_preview, docx_export, codex]
