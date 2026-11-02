"""FastAPI application: /api/v1 routes for the ResearchLedger web workspace."""
from __future__ import annotations

import asyncio
import json
import re
import os
import mimetypes
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import (agent_receipts, review_packet, manuscript_trace, mission, ledger_bridge, lab, memory_store, backup, versions, autopilot, inbox, steps, loops, prefs, quality, bridge, claude_runner, director, document_tools, experiments, memory, paper_studio, recipes, refcheck, registry, skills_catalog,
               workflows, workspace)
from .config import settings
from .db import Store, TERMINAL_STATES, new_id, now

app = FastAPI(title="ResearchLedger Web API", version="0.1.0")
store = Store(settings.db_path, keep_agent_runs=bridge.executor() == "bridge")

# Local single-user deployment: only loopback hosts (blocks DNS rebinding) and the
# configured frontend origins.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

CLIENT_HEADER = "x-rl-client"


@app.middleware("http")
async def require_client_header(request: Request, call_next):
    # A custom header forces a CORS preflight, so other sites in the user's browser
    # cannot fire state-changing "simple" requests (form posts) at this local API.
    if request.method in {"POST", "PATCH", "PUT", "DELETE"} and not request.headers.get(CLIENT_HEADER):
        return JSONResponse({"detail": f"missing {CLIENT_HEADER} header"}, status_code=403)
    return await call_next(request)


# ---------------------------------------------------------------- schemas
class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    domain: str = Field(default="", max_length=200)
    kind: str = Field(default="paper", pattern="^(paper|quick)$")


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    domain: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    kind: str | None = Field(default=None, pattern="^(paper|quick)$")


class ConversationIn(BaseModel):
    title: str = Field(default="New chat", max_length=200)


class RunIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._\-\[\]]{1,80}$")


class ExportIn(BaseModel):
    path: str
    to: str = Field(pattern="^(pdf|docx)$")


# ---------------------------------------------------------------- helpers
def _project(project_id: str) -> dict:
    p = store.one("SELECT * FROM projects WHERE id=?", (project_id,))
    if not p:
        raise HTTPException(404, "project not found")
    return p


def _path(project_id: str, rel: str):
    try:
        return workspace.resolve(project_id, rel)
    except workspace.PathError as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- health / registry
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "time": now(), "data_dir": str(settings.data_dir)}


@app.get("/api/v1/providers/health")
def providers_health():
    return registry.provider_health()


@app.get("/api/v1/agents")
def list_agents():
    return registry.agents()


@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: str):
    for a in registry.agents():
        if a["id"] == agent_id:
            return a
    raise HTTPException(404, "agent not found")


@app.get("/api/v1/skills")
def list_skills(refresh: bool = False):
    return skills_catalog.catalog(refresh)


class TaskIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._\-\[\]]{1,80}$")
    skill_id: str | None = Field(default=None, max_length=100)
    files: list[str] = Field(default_factory=list, max_length=20)


@app.post("/api/v1/projects/{project_id}/tasks", status_code=201)
def start_task(project_id: str, body: TaskIn):
    """The home-page composer: one prompt, optionally run through a skill, in a new chat."""
    _project(project_id)
    files = []
    for f in body.files:
        p = _path(project_id, f)
        if not p.is_file():
            raise HTTPException(400, f"attached file not found: {f}")
        files.append(p.relative_to(workspace.project_root(project_id)).as_posix())
    prompt, title = body.prompt, " ".join(body.prompt.split())[:60]
    if body.skill_id:
        skill = skills_catalog.get(body.skill_id)
        if not skill:
            raise HTTPException(404, "skill not found")
        skill_md = skills_catalog.stage(skill, workspace.project_root(project_id))
        prompt = skills_catalog.prompt(skill, skill_md, body.prompt, files)
        title = f"{skill['name']}: {title}"[:80]
    elif files:
        prompt += "\n\nAttached files in the workspace:\n" + "\n".join(f"- `{f}`" for f in files)
    ts = now()
    cid, rid = new_id("cnv"), new_id("run")
    store.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
               (cid, project_id, title, ts, ts))
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,model,created_at) "
               "VALUES (?,?,?,?,?,?,?,?,?)", (rid, project_id, cid, f"skill:{body.skill_id}" if body.skill_id
                                                else "claude_code", prompt, "queued", "claude_code_cli", body.model, ts))
    store.exec("UPDATE projects SET updated_at=? WHERE id=?", (ts, project_id))
    store.log_activity(project_id, "task_started", rid)
    claude_runner.start_run(store, rid)
    return {"run_id": rid, "conversation_id": cid, "project_id": project_id}


# ---------------------------------------------------------------- workflows
class WorkflowIn(BaseModel):
    values: dict = Field(default_factory=dict)


@app.get("/api/v1/workflows")
def list_workflows(section: str | None = None):
    return [workflows.public(w) for w in workflows.WORKFLOWS if not section or w["section"] == section]


@app.get("/api/v1/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    w = workflows.BY_ID.get(workflow_id)
    if not w:
        raise HTTPException(404, "workflow not found")
    return workflows.public(w)


@app.post("/api/v1/projects/{project_id}/workflows/{workflow_id}", status_code=201)
def launch_workflow(project_id: str, workflow_id: str, body: WorkflowIn):
    _project(project_id)
    try:
        return workflows.launch(store, project_id, workflow_id, body.values)
    except (workflows.WorkflowError, workspace.PathError) as exc:
        raise HTTPException(400, str(exc))


class MemoryIn(BaseModel):
    text: str = Field(max_length=1_000_000)


@app.get("/api/v1/projects/{project_id}/memory")
def get_memory(project_id: str):
    _project(project_id)
    return {"path": memory.MEMORY_PATH, "text": memory.read(project_id), "exists": memory.path(project_id).is_file()}


@app.put("/api/v1/projects/{project_id}/memory")
def put_memory(project_id: str, body: MemoryIn):
    _project(project_id)
    memory.write(project_id, body.text)
    store.log_activity(project_id, "memory_edited", memory.MEMORY_PATH)
    return get_memory(project_id)


RESULT_DIRS = ("results/", "4_code/", "analysis/", "5_refine/", "code/outputs/")


@app.get("/api/v1/projects/{project_id}/results")
def get_results(project_id: str):
    """Result files the project holds, and the measured S4 results.json when it exists."""
    _project(project_id)
    files = [f for f in workspace.list_files(project_id) if f["path"].startswith(RESULT_DIRS)]
    measured = None
    p = workspace.project_root(project_id) / "4_code" / "results.json"
    if p.is_file():
        try:
            measured = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            measured = {"error": "4_code/results.json is not valid JSON"}
    return {"files": files, "measured": measured}


@app.get("/api/v1/projects/{project_id}/progress")
def project_progress(project_id: str):
    _project(project_id)
    return workflows.progress(store, project_id)


@app.get("/api/v1/factory/doctor")
def factory_doctor():
    """`researchctl doctor`: the Factory's own readiness check (CLI logins, LaTeX, Docker, vendors)."""
    import subprocess as sp
    try:
        done = sp.run(workflows._researchctl("doctor"), cwd=workflows.REPO_ROOT, capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=180, env=workflows.claude_runner.child_env())
    except sp.TimeoutExpired:
        raise HTTPException(504, "researchctl doctor timed out")
    result = workflows._final_json(done.stdout)
    if result is None:
        raise HTTPException(502, (done.stderr or done.stdout)[-1500:] or "doctor produced no output")
    return result


# ---------------------------------------------------------------- One-click autopilot + approvals inbox
class AutopilotIn(BaseModel):
    goal: str = Field(default="", max_length=20_000)
    files: list[str] = Field(default_factory=list, max_length=30)
    model: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._\-\[\]]{1,80}$")
    repeat: str | None = Field(default=None, pattern="^(review|idea)$")


class ClassifyIn(BaseModel):
    goal: str = Field(default="", max_length=20_000)
    filenames: list[str] = Field(default_factory=list, max_length=30)
    repeat: str | None = Field(default=None, pattern="^(review|idea)$")


@app.post("/api/v1/autopilot/classify")
def autopilot_classify(body: ClassifyIn):
    """Preview for the home box: which tool would run, and why. Starts nothing."""
    try:
        d = autopilot.classify_with_repeat(body.goal, body.filenames, body.repeat)
    except ValueError as exc:
        return {"mode": "invalid", "tool": None, "why": str(exc)}
    return {**d, "tool": autopilot.tool_label(d)}


class AutopilotToggleIn(BaseModel):
    on: bool


@app.post("/api/v1/autopilot/classify")
def autopilot_classify(body: AutopilotIn):
    return autopilot.classify(body.goal, [Path(f).name for f in body.files])


@app.post("/api/v1/projects/{project_id}/autopilot/start", status_code=201)
def autopilot_start(project_id: str, body: AutopilotIn):
    _project(project_id)
    if not body.goal.strip() and not body.files:
        raise HTTPException(400, "say what you want or upload a file")
    try:
        out = autopilot.start(store, project_id, body.goal, body.files, body.model, body.repeat)
    except (ValueError, workspace.PathError) as exc:
        raise HTTPException(400, str(exc))
    if out.get("mode") == "paper":  # writing a whole paper turns a quick job into a paper project
        store.exec("UPDATE projects SET kind='paper' WHERE id=?", (project_id,))
    return out


@app.put("/api/v1/projects/{project_id}/paper/autopilot")
def paper_autopilot(project_id: str, body: AutopilotToggleIn):
    _project(project_id)
    try:
        return paper_studio.set_autopilot(store, project_id, body.on)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/inbox")
def get_inbox():
    return inbox.build(store)


class DismissIn(BaseModel):
    key: str = Field(min_length=1, max_length=600)


@app.post("/api/v1/inbox/dismiss")
def dismiss_inbox_item(body: DismissIn):
    """Hide one decision (it returns if its state changes). Changes nothing else."""
    inbox.dismiss(body.key)
    return inbox.build(store)


# ---------------------------------------------------------------- Research loops + standing preferences
class LoopIn(BaseModel):
    type: str
    goal: str = Field("", max_length=4000)
    idea_text: str | None = Field(None, max_length=60_000)
    manuscript: str | None = None
    external_review: str | None = Field(None, max_length=200_000)
    params: dict = Field(default_factory=dict)
    mode: str = "auto"
    example_pdf: str | None = None
    experiments_text: str | None = Field(None, max_length=60_000)
    from_loop: str | None = None


class SteerIn(BaseModel):
    text: str = Field(..., max_length=2000)


class PrefsIn(BaseModel):
    enabled: bool = True
    rules: list[str] = Field(default_factory=list)


def _loop_call(fn, *args):
    try:
        return fn(*args)
    except (loops.LoopError, workspace.PathError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/steps")
def pipeline_steps():
    """The seven numbered research steps shown in both the console (/rl) and the GUI home."""
    return {"pipeline": steps.PIPELINE, "steps": steps.STEPS, "extras": steps.EXTRAS, "menu": steps.menu_text(),
            "recipe_step": steps.RECIPE_STEP, "loop_step": steps.LOOP_STEP}


class StepIn(BaseModel):
    text: str = Field(default="", max_length=200_000)
    files: list[str] = Field(default_factory=list, max_length=50)
    options: dict = Field(default_factory=dict)


@app.post("/api/v1/projects/{project_id}/steps/{step_id}/start", status_code=201)
def start_step(project_id: str, step_id: str, body: StepIn):
    """Start one of the seven steps from files and/or pasted text; errors are plain sentences."""
    _project(project_id)
    try:
        return steps.start(store, project_id, step_id, body.text, body.files, body.options)
    except (steps.StepError, recipes.RecipeError, loops.LoopError, workspace.PathError, ValueError) as exc:
        raise HTTPException(400, str(exc).rstrip(".") + ".")


@app.get("/api/v1/loop-types")
def loop_types():
    return [{"id": k, "label": t["label"], "pitch": t["pitch"], "icon": t["icon"], "params": t["params"],
             "moves": [{"id": m, "label": loops.MOVE_LABELS[m]} for m in t["moves"]]} for k, t in loops.TYPES.items()]


@app.get("/api/v1/projects/{project_id}/loops")
def list_loops(project_id: str):
    _project(project_id)
    return loops.list_view(store, project_id)


@app.post("/api/v1/projects/{project_id}/loops", status_code=201)
def create_loop(project_id: str, body: LoopIn):
    _project(project_id)
    return _loop_call(loops.create, store, project_id, body.type, body.goal, body.idea_text, body.manuscript,
                      body.external_review, body.params, body.mode, body.example_pdf, body.experiments_text,
                      body.from_loop)


@app.get("/api/v1/projects/{project_id}/loops/{loop_id}")
def get_loop(project_id: str, loop_id: str):
    _project(project_id)
    _loop_call(loops.reconcile, store, project_id, loop_id)
    return _loop_call(loops.view, store, project_id, loop_id)


@app.post("/api/v1/projects/{project_id}/loops/{loop_id}/{action}")
def loop_action(project_id: str, loop_id: str, action: str, body: SteerIn | None = None):
    _project(project_id)
    if action == "steer":
        return _loop_call(loops.steer, store, project_id, loop_id, body.text if body else "")
    fn = {"continue": loops.resume, "stop": loops.stop, "retry": loops.retry, "accept": loops.accept}.get(action)
    if not fn:
        raise HTTPException(404, "unknown loop action")
    return _loop_call(fn, store, project_id, loop_id)


class QualityIn(BaseModel):
    tex: str
    target_pages: int | None = Field(None, ge=1, le=200)
    target_refs: int | None = Field(40, ge=0, le=1000)
    example_pdf: str | None = None
    online: bool = False


@app.post("/api/v1/projects/{project_id}/quality")
def run_quality(project_id: str, body: QualityIn):
    """Submission gate on a .tex (docs/QUALITY_PLAYBOOK.md). online=true also looks every reference up."""
    _project(project_id)
    tex = _path(project_id, body.tex)
    if not tex.is_file() or tex.suffix.lower() != ".tex":
        raise HTTPException(400, "choose a .tex file in the workspace")
    if body.example_pdf and not _path(project_id, body.example_pdf).is_file():
        raise HTTPException(400, f"{body.example_pdf} does not exist")
    root = workspace.project_root(project_id)
    report = quality.gate(root, tex.relative_to(root).as_posix(), body.target_pages, body.target_refs or None,
                          body.example_pdf, body.online)
    store.log_activity(project_id, "quality_gate", f"{body.tex} ready={report['ready']}")
    return report


@app.get("/api/v1/projects/{project_id}/quality")
def get_quality(project_id: str, tex: str):
    _project(project_id)
    rep = quality.load(workspace.project_root(project_id), tex)
    if not rep:
        raise HTTPException(404, "no quality report for this file yet")
    return rep


@app.get("/api/v1/preferences")
def get_prefs():
    return {**prefs.load(), "defaults": prefs.DEFAULT_RULES}


@app.put("/api/v1/preferences")
def put_prefs(body: PrefsIn):
    return {**prefs.save(body.enabled, body.rules), "defaults": prefs.DEFAULT_RULES}


@app.post("/api/v1/preferences/reset")
def reset_prefs():
    return {**prefs.reset(), "defaults": prefs.DEFAULT_RULES}


if os.environ.get("RL_LOOP_TICKER", "1") != "0":
    loops.start_ticker(store)


# ---------------------------------------------------------------- Smart recipes
class SuggestIn(BaseModel):
    filenames: list[str] = Field(default_factory=list, max_length=50)
    text: str = Field(default="", max_length=4000)


class RecipeRunIn(BaseModel):
    files: dict[str, list[str]] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


@app.get("/api/v1/recipes")
def list_recipes():
    return [recipes.public(r) for r in recipes.R]


@app.get("/api/v1/recipes/{recipe_id}")
def get_recipe(recipe_id: str):
    if recipe_id not in recipes.R:
        raise HTTPException(404, "recipe not found")
    return recipes.public(recipe_id)


@app.post("/api/v1/recipes/suggest")
def suggest_recipe(body: SuggestIn):
    return recipes.suggest(body.filenames, body.text)


@app.get("/api/v1/engines")
def list_engines():
    return recipes.engine_status()


@app.post("/api/v1/projects/{project_id}/recipes/{recipe_id}/run", status_code=201)
def run_recipe(project_id: str, recipe_id: str, body: RecipeRunIn):
    _project(project_id)
    try:
        return recipes.run(store, project_id, recipe_id, body.files, body.options)
    except (recipes.RecipeError, workspace.PathError) as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- Paper Studio
class PaperIn(BaseModel):
    type: str = Field(pattern="^(research_article|review_paper|thesis_to_paper|revision_rebuttal)$")
    venue: str = Field(default="journal", max_length=40)
    topic: str = Field(default="", max_length=4000)


class StageRunIn(BaseModel):
    notes: str = Field(default="", max_length=20_000)
    feedback: str | None = Field(default=None, max_length=20_000)


@app.get("/api/v1/paper-types")
def paper_types():
    return {"types": {k: {"label": v["label"], "stages": [s["title"] for s in v["stages"]]}
                      for k, v in paper_studio.PAPER_TYPES.items()},
            "venues": {k: v["label"] for k, v in paper_studio.VENUES.items()}}


@app.get("/api/v1/papers")
def list_papers():
    out = []
    for p in store.all("SELECT * FROM projects WHERE status='active' ORDER BY updated_at DESC"):
        v = paper_studio.view(store, p["id"])
        if v:
            nxt = next((s for s in v["stages"] if s["status"] != "approved"), None)
            out.append({"project_id": p["id"], "title": p["title"], "type_label": v["type_label"],
                        "venue_label": v["venue_label"], "topic": v["topic"],
                        "approved": sum(s["status"] == "approved" for s in v["stages"]), "total": len(v["stages"]),
                        "next_stage": nxt["title"] if nxt else None, "next_status": nxt["status"] if nxt else "done"})
    return out


@app.get("/api/v1/projects/{project_id}/paper")
def get_paper(project_id: str):
    _project(project_id)
    return paper_studio.view(store, project_id)


@app.post("/api/v1/projects/{project_id}/paper", status_code=201)
def create_paper(project_id: str, body: PaperIn):
    _project(project_id)
    try:
        out = paper_studio.create(store, project_id, body.type, body.venue, body.topic)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    store.exec("UPDATE projects SET kind='paper' WHERE id=?", (project_id,))
    return out


@app.post("/api/v1/projects/{project_id}/paper/stages/{stage_id}/run", status_code=201)
def run_paper_stage(project_id: str, stage_id: str, body: StageRunIn):
    _project(project_id)
    try:
        return paper_studio.run_stage(store, project_id, stage_id, body.notes, body.feedback)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/projects/{project_id}/paper/stages/{stage_id}/approve")
def approve_paper_stage(project_id: str, stage_id: str):
    _project(project_id)
    try:
        return paper_studio.approve(store, project_id, stage_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/projects/{project_id}/paper/collect-results")
def collect_paper_results(project_id: str):
    """Fill paper/experimental_log.md from results/*.json (also done when 'Run experiments' is approved)."""
    _project(project_id)
    state = paper_studio.load(project_id)
    if not state:
        raise HTTPException(400, "this project has no paper yet")
    stage = "experiments" if "experiments" in state["stages"] else "extract"
    return paper_studio.collect_results(store, project_id, stage, state["stages"].get(stage, {}).get("run_id"))


@app.post("/api/v1/projects/{project_id}/paper/review-rounds", status_code=201)
def start_review_round(project_id: str):
    """Run the next review <-> revise round (2 or 3) after Revise is approved."""
    _project(project_id)
    try:
        return paper_studio.start_review_round(store, project_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class EditIn(BaseModel):
    file: str = Field(min_length=1, max_length=300)
    selection: str = Field(min_length=1, max_length=20000)
    instruction: str = Field(default="", max_length=4000)


def _doc_call(fn, *args):
    try:
        return fn(*args)
    except (ValueError, workspace.PathError) as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/projects/{project_id}/paper/compare")
def compare_paper_files(project_id: str, a: str, b: str):
    _project(project_id)
    return _doc_call(document_tools.compare, project_id, a, b)


@app.get("/api/v1/projects/{project_id}/paper/edits")
def list_paper_edits(project_id: str):
    _project(project_id)
    return document_tools.list_edits(store, project_id)


@app.post("/api/v1/projects/{project_id}/paper/edits", status_code=201)
def request_paper_edit(project_id: str, body: EditIn):
    _project(project_id)
    state = paper_studio.load(project_id)
    if not state:
        raise HTTPException(400, "this project has no paper yet")
    return _doc_call(document_tools.request_edit, store, project_id, state["conversation_id"], body.file,
                     body.selection, body.instruction)


@app.post("/api/v1/projects/{project_id}/paper/edits/{edit_id}/apply")
def apply_paper_edit(project_id: str, edit_id: str):
    _project(project_id)
    return _doc_call(document_tools.apply_edit, store, project_id, edit_id)


@app.post("/api/v1/projects/{project_id}/paper/package", status_code=201)
def build_paper_package(project_id: str):
    _project(project_id)
    return _doc_call(document_tools.build_package, project_id)


@app.get("/api/v1/projects/{project_id}/paper/references")
def paper_reference_report(project_id: str):
    _project(project_id)
    return refcheck.load_report(workspace.project_root(project_id))


@app.post("/api/v1/projects/{project_id}/paper/check-references")
def check_paper_references(project_id: str):
    """Check paper/refs.bib against Crossref and arXiv; fill missing author/year/venue fields."""
    _project(project_id)
    try:
        return refcheck.check_file(workspace.project_root(project_id), refcheck.fetcher())
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/projects/{project_id}/paper/choose-idea/{idea_id}")
def choose_paper_idea(project_id: str, idea_id: str):
    _project(project_id)
    try:
        return paper_studio.choose_idea(store, project_id, idea_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- Claude app bridge
class ExecutorIn(BaseModel):
    executor: str = Field(pattern="^(bridge|cli)$")


class BridgeEventIn(BaseModel):
    kind: str = Field(pattern="^(say|step|todos|ping)$")
    text: str = Field(default="ping", min_length=1, max_length=20_000)
    claim: str | None = Field(default=None, max_length=64)


class BridgeDoneIn(BaseModel):
    summary: str = Field(default="", max_length=50_000)
    failed: bool = False
    claim: str | None = Field(default=None, max_length=64)


@app.get("/api/v1/bridge/status")
def bridge_status():
    return bridge.status(store)


@app.put("/api/v1/bridge/executor")
def set_bridge_executor(body: ExecutorIn):
    bridge.set_executor(body.executor)
    return bridge.status(store)


@app.post("/api/v1/bridge/next")
def bridge_next():
    """Called by the Claude app worker: claim the next queued agent task (or 204)."""
    task = bridge.claim(store)
    if not task:
        return Response(status_code=204)
    return task


@app.post("/api/v1/bridge/runs/{run_id}/event")
def bridge_event(run_id: str, body: BridgeEventIn):
    try:
        bridge.add_event(store, run_id, body.kind, body.text, body.claim)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


@app.post("/api/v1/bridge/runs/{run_id}/done")
def bridge_done(run_id: str, body: BridgeDoneIn):
    try:
        return bridge.complete(store, run_id, body.summary, body.failed, body.claim)
    except bridge.ClaimError as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# ---------------------------------------------------------------- dashboard
@app.get("/api/v1/dashboard")
def dashboard():
    return {
        "counts": {
            "projects": store.one("SELECT COUNT(*) n FROM projects WHERE status='active'")["n"],
            "runs": store.one("SELECT COUNT(*) n FROM runs")["n"],
            "running": store.one("SELECT COUNT(*) n FROM runs WHERE status IN ('queued','running')")["n"],
            "artifacts": store.one("SELECT COUNT(*) n FROM artifacts")["n"],
            "reviews": store.one("SELECT COUNT(*) n FROM runs WHERE kind IN "
                                 "('workflow:beihang_review','workflow:quick_review','workflow:factory_review_s3')")["n"],
        },
        "recent_projects": store.all("SELECT * FROM projects WHERE status='active' ORDER BY updated_at DESC LIMIT 6"),
        "recent_runs": store.all(
            "SELECT r.id, r.project_id, r.conversation_id, r.status, r.prompt, r.created_at, r.finished_at, "
            "r.error, p.title project_title FROM runs r JOIN projects p ON p.id=r.project_id "
            "ORDER BY r.created_at DESC LIMIT 8"),
        "recent_artifacts": store.all(
            "SELECT a.path, a.change, a.created_at, a.project_id, a.run_id, p.title project_title "
            "FROM artifacts a JOIN projects p ON p.id=a.project_id ORDER BY a.id DESC LIMIT 8"),
    }


# ---------------------------------------------------------------- projects
@app.get("/api/v1/projects")
def list_projects(status: str = "active", kind: str | None = None):
    if kind:
        return store.all("SELECT * FROM projects WHERE status=? AND kind=? ORDER BY updated_at DESC", (status, kind))
    return store.all("SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,))


@app.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectIn):
    pid, ts = new_id("prj"), now()
    store.exec("INSERT INTO projects(id,title,description,domain,kind,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
               (pid, body.title.strip(), body.description, body.domain, body.kind, ts, ts))
    workspace.project_root(pid)
    store.log_activity(pid, "project_created", body.title)
    return _project(pid)


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str):
    p = _project(project_id)
    p["conversations"] = store.all("SELECT * FROM conversations WHERE project_id=? ORDER BY updated_at DESC",
                                   (project_id,))
    return p


@app.patch("/api/v1/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch):
    _project(project_id)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        store.exec(f"UPDATE projects SET {cols} WHERE id=?", (*fields.values(), project_id))
    return _project(project_id)


@app.get("/api/v1/projects/{project_id}/activity")
def project_activity(project_id: str):
    _project(project_id)
    return store.all("SELECT * FROM activity WHERE project_id=? ORDER BY id DESC LIMIT 100", (project_id,))


# ---------------------------------------------------------------- conversations & runs
@app.post("/api/v1/projects/{project_id}/conversations", status_code=201)
def create_conversation(project_id: str, body: ConversationIn):
    _project(project_id)
    cid, ts = new_id("cnv"), now()
    store.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
               (cid, project_id, body.title or "New chat", ts, ts))
    return store.one("SELECT * FROM conversations WHERE id=?", (cid,))


@app.get("/api/v1/conversations")
def recent_conversations(limit: int = 20):
    """Recent chats across all projects (sidebar 'Recents')."""
    return store.all(
        "SELECT c.id, c.project_id, c.title, c.updated_at, p.title project_title, p.kind project_kind, "
        "(SELECT status FROM runs r WHERE r.conversation_id=c.id ORDER BY r.created_at DESC LIMIT 1) last_status "
        "FROM conversations c JOIN projects p ON p.id=c.project_id WHERE p.status='active' "
        "AND EXISTS (SELECT 1 FROM runs r WHERE r.conversation_id=c.id) "
        "ORDER BY c.updated_at DESC LIMIT ?", (min(limit, 100),))


@app.get("/api/v1/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    conv = store.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not conv:
        raise HTTPException(404, "conversation not found")
    runs = store.all("SELECT * FROM runs WHERE conversation_id=? ORDER BY created_at", (conversation_id,))
    for r in runs:
        r["events"] = store.events_after(r["id"], 0, 5000)
    conv["runs"] = runs
    return conv


@app.post("/api/v1/conversations/{conversation_id}/runs", status_code=201)
def create_run(conversation_id: str, body: RunIn):
    conv = store.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not conv:
        raise HTTPException(404, "conversation not found")
    active = store.one("SELECT id FROM runs WHERE conversation_id=? AND status IN ('queued','running')",
                       (conversation_id,))
    if active:
        raise HTTPException(409, f"run {active['id']} is still active in this conversation")
    rid, ts = new_id("run"), now()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,prompt,status,provider,model,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)",
               (rid, conv["project_id"], conversation_id, body.prompt, "queued", "claude_code_cli",
                body.model, ts))
    if conv["title"] == "New chat":
        title = " ".join(body.prompt.split())[:60]
        store.exec("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
    store.exec("UPDATE conversations SET updated_at=? WHERE id=?", (ts, conversation_id))
    store.exec("UPDATE projects SET updated_at=? WHERE id=?", (ts, conv["project_id"]))
    store.log_activity(conv["project_id"], "run_started", rid)
    claude_runner.start_run(store, rid)
    return store.one("SELECT * FROM runs WHERE id=?", (rid,))


@app.get("/api/v1/runs")
def list_runs(project_id: str | None = None, status: str | None = None, limit: int = 100):
    sql = ("SELECT r.*, p.title project_title FROM runs r JOIN projects p ON p.id=r.project_id WHERE 1=1")
    args: list = []
    if project_id:
        sql += " AND r.project_id=?"; args.append(project_id)
    if status:
        sql += " AND r.status=?"; args.append(status)
    sql += " ORDER BY r.created_at DESC LIMIT ?"
    args.append(min(limit, 500))
    return store.all(sql, args)


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str):
    r = store.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not r:
        raise HTTPException(404, "run not found")
    r["artifacts"] = store.all("SELECT path, sha256, size, change, created_at FROM artifacts WHERE run_id=?",
                               (run_id,))
    return r


@app.post("/api/v1/conversations/{conversation_id}/director", status_code=201)
def director_turn(conversation_id: str, body: RunIn):
    """A Research Director turn: answers directly, or writes a plan for approval."""
    if not store.one("SELECT id FROM conversations WHERE id=?", (conversation_id,)):
        raise HTTPException(404, "conversation not found")
    active = store.one("SELECT id FROM runs WHERE conversation_id=? AND status IN ('queued','running')",
                       (conversation_id,))
    if active:
        raise HTTPException(409, f"run {active['id']} is still active in this conversation")
    return director.start_turn(store, conversation_id, body.prompt, body.model)


@app.get("/api/v1/conversations/{conversation_id}/plan")
def get_plan(conversation_id: str):
    conv = store.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not conv:
        raise HTTPException(404, "conversation not found")
    plan_run = store.one("SELECT id, status FROM runs WHERE conversation_id=? AND kind='plan' "
                         "ORDER BY created_at DESC LIMIT 1", (conversation_id,))
    return {"path": director.plan_path(conversation_id),
            "plan": director.load_plan(conv["project_id"], conversation_id), "plan_run": plan_run}


@app.post("/api/v1/conversations/{conversation_id}/plan/approve", status_code=201)
def approve_plan(conversation_id: str):
    conv = store.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    if not conv:
        raise HTTPException(404, "conversation not found")
    try:
        return director.approve(store, conv["project_id"], conversation_id)
    except workflows.WorkflowError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/runs/{run_id}/cancel")
def cancel(run_id: str):
    r = get_run(run_id)
    if r["status"] in TERMINAL_STATES:
        raise HTTPException(409, f"run already {r['status']}")
    if r["kind"] == "plan":
        director.stop(store, run_id)
        return get_run(run_id)
    if not claude_runner.cancel_run(store, run_id):
        raise HTTPException(409, "run is not executing in this server process")
    return get_run(run_id)


@app.get("/api/v1/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0):
    """Server-Sent Events. Resumable with ?after=<event id> or Last-Event-ID."""
    get_run(run_id)
    last = int(request.headers.get("last-event-id") or after or 0)

    async def stream():
        nonlocal last
        idle = 0
        while True:
            if await request.is_disconnected():
                return
            events = store.events_after(run_id, last)
            for e in events:
                last = e["id"]
                yield f"id: {e['id']}\nevent: {e['kind']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
            status = store.one("SELECT status FROM runs WHERE id=?", (run_id,))["status"]
            if status in TERMINAL_STATES and not events:
                yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                return
            idle = 0 if events else idle + 1
            if idle and idle % 30 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- files
@app.get("/api/v1/projects/{project_id}/files")
def list_files(project_id: str, include_build: bool = False):
    _project(project_id)
    files = workspace.list_files(project_id, include_build)
    latest = {a["path"]: a for a in store.all(
        "SELECT path, run_id, change, created_at FROM artifacts WHERE project_id=? ORDER BY id", (project_id,))}
    for f in files:
        a = latest.get(f["path"])
        f["last_run_id"] = a["run_id"] if a else None
    return files


@app.get("/api/v1/projects/{project_id}/files/raw")
def raw_file(project_id: str, path: str, download: bool = False):
    _project(project_id)
    p = _path(project_id, path)
    if not p.is_file():
        raise HTTPException(404, "file not found")
    media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if media in {"text/html", "image/svg+xml"} and not download:
        media = "text/plain"  # never render workspace HTML/SVG as active content
    headers = {"X-Content-Type-Options": "nosniff"}
    if media != "application/pdf":
        # Browsers refuse to run their PDF viewer in a sandboxed document, so only
        # non-PDF files get the CSP sandbox.
        headers["Content-Security-Policy"] = "sandbox"
    return FileResponse(p, media_type=media, filename=p.name,
                        content_disposition_type="attachment" if download else "inline", headers=headers)


@app.get("/api/v1/projects/{project_id}/files/preview")
def preview_file(project_id: str, path: str):
    _project(project_id)
    p = _path(project_id, path)
    if not p.is_file():
        raise HTTPException(404, "file not found")
    kind = workspace.file_kind(p)
    info = {"path": path, "kind": kind, "size": p.stat().st_size, "sha256": workspace.sha256(p)}
    if kind == "docx":
        try:
            info.update(workspace.docx_to_html(p))
        except ImportError:
            raise HTTPException(501, "Word preview needs the 'mammoth' package on the server")
    elif kind in {"text", "markdown"}:
        if p.stat().st_size > 2_000_000:
            info["text"] = None
            info["warnings"] = ["File is larger than 2 MB; download it instead."]
        else:
            info["text"] = p.read_text(encoding="utf-8", errors="replace")
    return info


@app.get("/api/v1/projects/{project_id}/files/history")
def file_history(project_id: str, path: str):
    """Every saved version of a file, newest first (who wrote it, when, which run)."""
    _project(project_id)
    rel = _path(project_id, path).relative_to(workspace.project_root(project_id)).as_posix()
    versions.safe_sync(store, project_id, "external")  # edits made on disk since the last run show up too
    return versions.history(store, project_id, rel)


@app.get("/api/v1/projects/{project_id}/files/version")
def file_version(project_id: str, path: str, version: int, download: bool = False):
    """The content of one saved version (read-only), served like /files/raw."""
    _project(project_id)
    rel = _path(project_id, path).relative_to(workspace.project_root(project_id)).as_posix()
    try:
        obj = versions.version_object(store, project_id, rel, version)
    except versions.VersionError as exc:
        raise HTTPException(404, str(exc))
    name = Path(rel).name
    media = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if media in {"text/html", "image/svg+xml"} and not download:
        media = "text/plain"
    headers = {"X-Content-Type-Options": "nosniff"}
    if media != "application/pdf":
        headers["Content-Security-Policy"] = "sandbox"
    return FileResponse(obj, media_type=media, filename=f"v{version}_{name}",
                        content_disposition_type="attachment" if download else "inline", headers=headers)


class RestoreIn(BaseModel):
    path: str
    version: int


@app.post("/api/v1/projects/{project_id}/files/restore")
def file_restore(project_id: str, body: RestoreIn):
    """Make an earlier version current again. It is added as a new version; later versions are kept."""
    _project(project_id)
    rel = _path(project_id, body.path).relative_to(workspace.project_root(project_id)).as_posix()
    _agent_busy(project_id)
    try:
        new = versions.restore(store, project_id, rel, body.version)
    except versions.VersionError as exc:
        raise HTTPException(404, str(exc))
    store.log_activity(project_id, "file_restored", f"{rel} v{body.version}")
    return {"path": rel, "restored": body.version, "current_version": new}


def _agent_busy(project_id: str) -> None:
    if store.one("SELECT id FROM runs WHERE project_id=? AND status='running' AND provider='claude_code_cli'",
                 (project_id,)):
        raise HTTPException(409, "An agent is working in this project right now. Try again when it has finished.")


@app.get("/api/v1/projects/{project_id}/files/trash")
def file_trash(project_id: str):
    """Deleted files whose content is kept; bring one back with files/restore (its last version)."""
    _project(project_id)
    versions.safe_sync(store, project_id, "external")
    return versions.trash(store, project_id)


@app.get("/api/v1/projects/{project_id}/files/compare")
def file_compare(project_id: str, path: str, old: int, new: int | None = None):
    """Line-by-line changes from version `old` to version `new` (omit `new` for the file as it is now)."""
    _project(project_id)
    rel = _path(project_id, path).relative_to(workspace.project_root(project_id)).as_posix()
    try:
        return versions.compare(store, project_id, rel, old, new)
    except versions.VersionError as exc:
        raise HTTPException(400, str(exc))


class RenameIn(BaseModel):
    path: str
    new_path: str


@app.post("/api/v1/projects/{project_id}/files/rename")
def file_rename(project_id: str, body: RenameIn):
    """Rename or move a file inside the workspace; its history moves with it."""
    _project(project_id)
    root = workspace.project_root(project_id)
    src = _path(project_id, body.path).relative_to(root).as_posix()
    dst = _path(project_id, body.new_path.strip()).relative_to(root).as_posix()
    if Path(dst).suffix.lower() != Path(src).suffix.lower():
        raise HTTPException(400, "keep the same file extension")
    _agent_busy(project_id)
    try:
        out = versions.rename(store, project_id, src, dst)
    except versions.VersionError as exc:
        raise HTTPException(400, str(exc))
    store.log_activity(project_id, "file_renamed", f"{src} -> {dst}")
    return out


@app.get("/api/v1/backups")
def backups_list():
    return {"backups": backup.listing(store), "folder": str(backup.backups_dir())}


@app.post("/api/v1/backups", status_code=201)
def backups_create():
    try:
        return backup.create(store, "manual")
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@app.get("/api/v1/integrity")
def integrity(project_id: str | None = None, full: bool = False):
    """Read-only check: re-hash saved versions (a sample, or all with full=true) and compare database and disk."""
    return backup.audit(store, project_id, None if full else 200)


@app.on_event("startup")
def _start_daily_backups():
    backup.start_daily(store)


@app.on_event("startup")
def _backfill_memory():
    """Recorded loop outcomes become memories once (idempotent), so older projects get them too."""
    for p in store.all("SELECT id FROM projects"):
        memory_store.safe(memory_store.ingest_loops, store, p["id"])
        memory_store.safe(memory_store.ingest_reviews, store, p["id"])


# ---------------------------------------------------------------- experiment laboratory
def _lab(fn, *args):
    try:
        return fn(*args)
    except lab.LabError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/projects/{project_id}/lab")
def lab_tree(project_id: str):
    """Experiments (with their parent links), every recorded run with its fingerprints, and runs in progress."""
    _project(project_id)
    return lab.tree(store, project_id)


@app.get("/api/v1/projects/{project_id}/lab/runs/{run_id}")
def lab_run(project_id: str, run_id: str):
    _project(project_id)
    return _lab(lab.receipt, project_id, run_id)


@app.get("/api/v1/projects/{project_id}/agent-receipts")
def agent_receipt_list(project_id: str):
    """Server-written receipts of finished agent tasks (who did what, which files, how it ended)."""
    _project(project_id)
    return {"receipts": agent_receipts.listing(store, project_id)}


@app.get("/api/v1/projects/{project_id}/agent-receipts/{run_id}")
def agent_receipt(project_id: str, run_id: str):
    _project(project_id)
    rec = agent_receipts.read(project_id, run_id) if re.fullmatch(r"run_[A-Za-z0-9]+", run_id) else None
    if not rec:
        raise HTTPException(404, "no receipt for this task")
    return {**rec, "intact": agent_receipts.verify(rec)}


@app.get("/api/v1/projects/{project_id}/lab/compare")
def lab_compare(project_id: str, a: str, b: str):
    _project(project_id)
    return _lab(lab.compare, project_id, a, b)


@app.post("/api/v1/projects/{project_id}/lab/runs/{run_id}/repeat", status_code=201)
def lab_repeat(project_id: str, run_id: str):
    """Run the same commands again as a new, separately recorded run. The user's click is the approval;
    the project's results files are put back afterwards, so a repeat only checks reproducibility."""
    _project(project_id)
    rid = _lab(lab.repeat, store, project_id, run_id)
    store.log_activity(project_id, "experiment_repeated", f"{run_id} -> {rid}")
    return {"run_id": rid, "repeat_of": run_id}


class ParentIn(BaseModel):
    loop_id: str
    parent: str | None = None


@app.post("/api/v1/projects/{project_id}/lab/parent")
def loop_parent(project_id: str, body: ParentIn):
    """Link an experiment to the experiment or loop it builds on (shown as a tree in the lab)."""
    _project(project_id)
    loop_id = body.loop_id
    st = loops.load(project_id, loop_id)
    if not st:
        raise HTTPException(404, "unknown loop")
    if body.parent and (body.parent == loop_id or not loops.load(project_id, body.parent)):
        raise HTTPException(400, "the parent must be another loop in this project")
    seen, cur = {loop_id}, body.parent
    while cur:  # refuse cycles
        if cur in seen:
            raise HTTPException(400, "that link would make a loop of parents")
        seen.add(cur)
        ps = loops.load(project_id, cur) or {}
        cur = ps.get("parent") or (ps.get("inputs") or {}).get("from_loop")
    with loops._lock:
        st = loops.load(project_id, loop_id)
        st["parent"] = body.parent
        loops._save(project_id, st)
    return {"loop_id": loop_id, "parent": body.parent}


# ---------------------------------------------------------------- independent review packet
def _rp(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class PacketIn(BaseModel):
    path: str


@app.get("/api/v1/projects/{project_id}/review/external")
def external_review_list(project_id: str):
    """Packets built and external reviews imported, and the .tex manuscripts that can be reviewed."""
    _project(project_id)
    return review_packet.listing(project_id)


@app.post("/api/v1/projects/{project_id}/review/packet", status_code=201)
def external_review_packet(project_id: str, body: PacketIn):
    """Build the folder and zip to take to an outside reviewer (manuscript, evidence summary, reviewer prompt)."""
    _project(project_id)
    rel = _path(project_id, body.path).relative_to(workspace.project_root(project_id)).as_posix()
    return _rp(review_packet.build, store, project_id, rel)


class ImportIn(BaseModel):
    path: str
    text: str = Field(..., max_length=200_000)
    source: str = Field("External reviewer", max_length=80)


@app.post("/api/v1/projects/{project_id}/review/import", status_code=201)
def external_review_import(project_id: str, body: ImportIn):
    """Parse the outside reviewer's reply; a concern is VERIFIED only if its quote is really in the manuscript."""
    _project(project_id)
    rel = _path(project_id, body.path).relative_to(workspace.project_root(project_id)).as_posix()
    return _rp(review_packet.import_reply, store, project_id, rel, body.text, body.source)


# ---------------------------------------------------------------- methodology lock
def _lockcall(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/projects/{project_id}/paper/lock")
def paper_lock(project_id: str):
    """Whether the approved plan is locked, how the protocol and declared slots differ from the lock, amendments, and
    checks on the pre-experiment draft."""
    _project(project_id)
    return _lockcall(paper_studio.lock_status, project_id)


class AmendmentIn(BaseModel):
    reason: str = Field(..., max_length=2000)
    affects: str = Field("", max_length=1000)


@app.post("/api/v1/projects/{project_id}/paper/lock/amendments", status_code=201)
def paper_amendment(project_id: str, body: AmendmentIn):
    _project(project_id)
    return _lockcall(paper_studio.propose_amendment, store, project_id, body.reason, body.affects)


class AmendmentDecisionIn(BaseModel):
    approve: bool


@app.post("/api/v1/projects/{project_id}/paper/lock/amendments/{amendment_id}/decision")
def paper_amendment_decide(project_id: str, amendment_id: str, body: AmendmentDecisionIn):
    """Approving makes the changed protocol the new lock version and reopens the stages after Method; rejecting puts
    the locked protocol back."""
    _project(project_id)
    return _lockcall(paper_studio.decide_amendment, store, project_id, amendment_id, body.approve)


@app.post("/api/v1/projects/{project_id}/paper/lock", status_code=201)
def paper_lock_now(project_id: str):
    """Freeze an already-approved plan (for papers approved before locking existed)."""
    _project(project_id)
    return _lockcall(paper_studio.lock_plan_now, store, project_id)


@app.post("/api/v1/projects/{project_id}/paper/lock/restore")
def paper_lock_restore(project_id: str):
    _project(project_id)
    return _lockcall(paper_studio.restore_locked_protocol, store, project_id)


# ---------------------------------------------------------------- manuscript trace
@app.get("/api/v1/projects/{project_id}/manuscript/trace")
def manuscript_trace_view(project_id: str, path: str):
    """For a .tex manuscript: each reported number with its result file, run and ledger evidence, plus placeholders,
    sources and unused results. Read-only; shows where numbers come from, not that they are correct."""
    _project(project_id)
    rel = _path(project_id, path).relative_to(workspace.project_root(project_id)).as_posix()
    try:
        return manuscript_trace.trace(store, project_id, rel)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- mission control
@app.get("/api/v1/mission")
def mission_overview(hours: int = 24):
    """Every task in one view: running, queued (and what it waits for), interrupted, failed, completed in the last
    `hours`, what needs your decision, and each paper's stage pipeline."""
    return mission.overview(store, min(max(hours, 1), 168))


# ---------------------------------------------------------------- evidence ledger (C/E/R)
def _ledger(fn, *args):
    try:
        return fn(*args)
    except ledger_bridge.LedgerError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/projects/{project_id}/evidence")
def evidence_overview(project_id: str, sync: bool = True):
    """Claims (C###), evidence (E###) and runs (R####) from the project's ResearchLedger, plus integrity issues.
    sync=true first imports any newly recorded runs and pre-registered verdicts (idempotent)."""
    _project(project_id)
    report = ledger_bridge.safe_sync(store, project_id) if sync else None
    return {**_ledger(ledger_bridge.overview, store, project_id), "sync": report}


class ClaimIn(BaseModel):
    statement: str = Field(..., max_length=4000)
    name: str = Field("", max_length=200)
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)


@app.post("/api/v1/projects/{project_id}/claims", status_code=201)
def claim_add(project_id: str, body: ClaimIn):
    _project(project_id)
    return {"id": _ledger(ledger_bridge.add_claim, store, project_id, body.statement, body.name, body.supports,
                          body.contradicts)}


class EvidenceStatusIn(BaseModel):
    status: str
    reason: str = Field(..., max_length=1000)


@app.post("/api/v1/projects/{project_id}/evidence/{evidence_id}/status")
def evidence_status(project_id: str, evidence_id: str, body: EvidenceStatusIn):
    """Your judgment on one piece of evidence (checked = reviewed, verified = confirmed, invalidated). The ledger
    re-derives every claim's status from it; claim status is never set directly."""
    _project(project_id)
    return _ledger(ledger_bridge.set_status, store, project_id, evidence_id, body.status, body.reason)


class WithdrawIn(BaseModel):
    reason: str = Field(..., max_length=1000)


@app.post("/api/v1/projects/{project_id}/claims/{claim_id}/withdraw")
def claim_withdraw(project_id: str, claim_id: str, body: WithdrawIn):
    _project(project_id)
    _ledger(ledger_bridge.withdraw_claim, store, project_id, claim_id, body.reason)
    return {"ok": True}


class BindIn(BaseModel):
    claim: str
    relation: str = "supports"


@app.post("/api/v1/projects/{project_id}/evidence/{evidence_id}/bind")
def evidence_bind(project_id: str, evidence_id: str, body: BindIn):
    _project(project_id)
    _ledger(ledger_bridge.bind, store, project_id, evidence_id, body.claim, body.relation)
    return {"ok": True}


@app.get("/api/v1/projects/{project_id}/ledger/trace/{entity_id}")
def ledger_trace_view(project_id: str, entity_id: str):
    """The provenance chain of a claim, evidence or run, as the ledger's own trace prints it."""
    _project(project_id)
    if not re.fullmatch(r"[CER]\d{3,4}", entity_id):
        raise HTTPException(400, "give a claim (C###), evidence (E###) or run (R####) id")
    return {"id": entity_id, "text": _ledger(ledger_bridge.trace, project_id, entity_id)}


# ---------------------------------------------------------------- research memory v2
class MemoryIn(BaseModel):
    domain: str
    title: str = Field(..., max_length=300)
    content: str = Field(..., max_length=20000)
    sources: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    all_projects: bool = False


class MemoryCorrectIn(BaseModel):
    title: str = Field("", max_length=300)
    content: str = Field(..., max_length=20000)
    sources: list[dict] | None = None


class MemoryDecisionIn(BaseModel):
    approve: bool
    note: str = ""


def _mem(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except memory_store.MemoryError_ as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/v1/memory")
def memory_search(q: str = "", project_id: str | None = None, domain: str | None = None, status: str | None = None,
                  include_global: bool = True, limit: int = 100):
    """Search memories: one project (plus global ones) or, without project_id, all of them."""
    if project_id:
        _project(project_id)
    return memory_store.search(store, project_id, q, [domain] if domain else None, [status] if status else None,
                               include_global, min(max(limit, 1), 500))


@app.get("/api/v1/memory/{item_id}")
def memory_get(item_id: str):
    return _mem(memory_store.get, store, item_id)


@app.post("/api/v1/projects/{project_id}/memory", status_code=201)
def memory_add(project_id: str, body: MemoryIn):
    """Add a memory yourself (active at once). all_projects=true makes it visible to every project."""
    _project(project_id)
    return _mem(memory_store.add, store, None if body.all_projects else project_id, body.domain, body.title,
                body.content, "user", evidence=body.sources, tags=body.tags)


@app.post("/api/v1/memory/{item_id}/decision")
def memory_decide(item_id: str, body: MemoryDecisionIn):
    return _mem(memory_store.decide, store, item_id, body.approve, "user", body.note)


@app.post("/api/v1/memory/{item_id}/correct")
def memory_correct(item_id: str, body: MemoryCorrectIn):
    """Replace a memory with a corrected version; the old one is kept and marked superseded."""
    return _mem(memory_store.correct, store, item_id, body.title, body.content, "user", body.sources)


@app.post("/api/v1/projects/{project_id}/memory/refresh")
def memory_refresh(project_id: str):
    """Re-read recorded loop outcomes into memory (normally automatic) and rewrite memory/remembered.md."""
    _project(project_id)
    return {"added": memory_store.ingest_loops(store, project_id) + memory_store.ingest_reviews(store, project_id)}


@app.post("/api/v1/projects/{project_id}/files", status_code=201)
async def upload(project_id: str, file: UploadFile = File(...), folder: str = "uploads", unzip: bool = False):
    _project(project_id)
    name = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if not name or ext not in workspace.UPLOAD_EXT:
        raise HTTPException(415, f"file type {ext or '(none)'} is not accepted")
    dest = _path(project_id, f"{folder.strip('/')}/{name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    tmp = dest.with_name(dest.name + ".part")
    with tmp.open("wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                out.close(); tmp.unlink(missing_ok=True)
                raise HTTPException(413, "file too large")
            out.write(chunk)
    root = workspace.project_root(project_id)
    rel = dest.relative_to(root).as_posix()
    if dest.exists():  # the earlier content is kept as a version (see the file's History), not overwritten
        versions.record(store, project_id, rel, "external", note="saved automatically before an upload replaced it")
    tmp.replace(dest)
    version = versions.record(store, project_id, rel, "user", note="uploaded")
    store.log_activity(project_id, "file_uploaded", rel)
    if unzip and ext == ".zip":  # the paper's folder as a zip: unpack next to it, return every file
        versions.safe_sync(store, project_id, "external")  # files the zip overwrites keep their old version
        try:
            files = workspace.unzip_into(dest, dest.with_suffix(""))
        except workspace.PathError as exc:
            raise HTTPException(400, str(exc))
        for f in files:
            versions.record(store, project_id, f.relative_to(root).as_posix(), "user", note=f"unpacked from {name}")
        return {"path": rel, "size": size, "version": version,
                "files": [f.relative_to(root).as_posix() for f in files]}
    return {"path": rel, "size": size, "version": version}


@app.post("/api/v1/projects/{project_id}/export")
def export(project_id: str, body: ExportIn):
    _project(project_id)
    src = _path(project_id, body.path)
    if not src.is_file():
        raise HTTPException(404, "file not found")
    root = workspace.project_root(project_id)
    if body.to == "pdf":
        if src.suffix.lower() != ".tex":
            raise HTTPException(400, "PDF export takes a .tex file")
        try:
            res = workspace.latex_to_pdf(src)
        except RuntimeError as exc:
            raise HTTPException(501, str(exc))
        if not res["ok"]:
            raise HTTPException(422, {"message": "LaTeX compilation failed", "log_tail": res["log_tail"]})
        out, warnings = res["pdf"], []
    else:
        if src.suffix.lower() != ".md":
            raise HTTPException(400, "Word export takes a .md file")
        out = src.with_suffix(".docx")
        warnings = workspace.markdown_to_docx(src, out)
    rel = out.relative_to(root).as_posix()
    store.log_activity(project_id, f"export_{body.to}", rel)
    return {"path": rel, "warnings": warnings}
