"""FastAPI application: /api/v1 routes for the ResearchLedger web workspace."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import shutil

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import (bridge, claude_runner, director, experiments, memory, paper_studio, recipes, refcheck, registry, skills_catalog,
               workflows, workspace)
from .config import settings
from .db import Store, TERMINAL_STATES, new_id, now

app = FastAPI(title="ResearchLedger Web API", version="0.1.0")
store = Store(settings.db_path)

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


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    domain: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


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
    type: str = Field(pattern="^(research_article|review_paper)$")
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
        return paper_studio.create(store, project_id, body.type, body.venue, body.topic)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


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
    run_id = state["stages"].get("experiments", {}).get("run_id")
    return experiments.collect(workspace.project_root(project_id), run_id)


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
    kind: str = Field(pattern="^(say|step|todos)$")
    text: str = Field(min_length=1, max_length=20_000)


class BridgeDoneIn(BaseModel):
    summary: str = Field(default="", max_length=50_000)
    failed: bool = False


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
        bridge.add_event(store, run_id, body.kind, body.text)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


@app.post("/api/v1/bridge/runs/{run_id}/done")
def bridge_done(run_id: str, body: BridgeDoneIn):
    try:
        return bridge.complete(store, run_id, body.summary, body.failed)
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
def list_projects(status: str = "active"):
    return store.all("SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,))


@app.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectIn):
    pid, ts = new_id("prj"), now()
    store.exec("INSERT INTO projects(id,title,description,domain,created_at,updated_at) VALUES (?,?,?,?,?,?)",
               (pid, body.title.strip(), body.description, body.domain, ts, ts))
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
        "SELECT c.id, c.project_id, c.title, c.updated_at, p.title project_title, "
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


@app.post("/api/v1/projects/{project_id}/files", status_code=201)
async def upload(project_id: str, file: UploadFile = File(...), folder: str = "uploads"):
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
    if dest.exists():  # keep earlier versions instead of overwriting silently
        n = 1
        while (v := dest.with_name(f"{dest.stem}.v{n}{dest.suffix}")).exists():
            n += 1
        shutil.move(dest, v)
    tmp.replace(dest)
    rel = dest.relative_to(workspace.project_root(project_id)).as_posix()
    store.log_activity(project_id, "file_uploaded", rel)
    return {"path": rel, "size": size}


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
