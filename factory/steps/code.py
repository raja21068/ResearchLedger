"""Step 4 -- the empty-results draft -> code (PaperCompiler method) -> sandboxed run.

The draft's empty tables and figures are the requirement document: `results_spec.json`
names every number and plot the paper needs, and the code must produce exactly those.

Two ways to produce the repository, both keyless (Claude Code under your login):

  agent     (default) Claude Code reads PaperCompiler (`vendor/PaperCompiler-main`) as
            its method, writes the stage artifacts, then the repo. It has file tools
            only, no shell, so it cannot run what it writes.
  pipeline  PaperCompiler's own scripts, run unmodified, with `factory/shims/openai`
            answering their OpenAI calls through `claude -p`; then a session adds the
            harness.

Either way the repo gets `pf_run.py`, which writes `$PF_OUT_DIR/results.json` against
the spec's ids. The harness runs only inside the Docker sandbox, network off. Failures
(or missing slots) go back to Claude Code to fix, up to `code_run_attempts` times.
Results are pilot-scale and the log says so; if the slots cannot be filled, the stage
blocks and nothing is invented.
"""
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

from factory import results as results_mod
from factory import sandbox as sandbox_mod
from factory.agents.session import run_session

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAPERCOMPILER = ROOT / "vendor" / "PaperCompiler-main"
SHIMS = ROOT / "factory" / "shims"
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
UNRESOLVED_KEYS = {"open_design_choices", "unresolved", "unresolved_issues", "open_questions"}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def tree_hash(directory):
    """Historical tree digest, streamed to avoid reading entire datasets into RAM.

    Preserve the existing digest format so older recorded runs still verify.
    A symlink is forbidden instead of silently hashing a file outside the repo.
    """
    root = pathlib.Path(directory)
    if any(component.is_symlink() for component in (root.absolute(), *root.absolute().parents)) or not root.is_dir():
        raise ValueError(f"repository is absent or symlinked: {root}")
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"repository contains unsafe symlink: {path}")
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


# -- PaperCompiler's own pipeline (code_mode = pipeline) ----------------------

def pipeline_commands(tex, artifacts, repo, gpt_version="o3-mini"):
    """PaperCompiler's stages, as scripts/run.sh runs them, LaTeX input, no evaluation."""
    codes = PAPERCOMPILER / "codes"
    paper = ["--paper_name", "paper", "--gpt_version", gpt_version,
             "--paper_format", "LaTeX", "--pdf_latex_path", str(tex)]
    a = pathlib.Path(artifacts)
    blueprint, spec = a / "translating_blueprint.txt", a / "reconciling_spec.json"
    plan = a / "architecting_plan.json"
    return [
        ("1_translating", ["1_translating.py", *paper, "--output_dir", str(a)], blueprint),
        ("1_5_reference", ["1_5_reference_extraction.py", *paper, "--output_dir", str(a),
                           "--s1_blueprint_path", str(blueprint)], a / "reference_registry.json"),
        ("2_reconciling", ["2_reconciling.py", *paper, "--output_dir", str(a),
                           "--translating_blueprint_path", str(blueprint)], spec),
        ("3_architecting", ["3_architecting.py", *paper, "--output_dir", str(a),
                            "--translating_blueprint_path", str(blueprint),
                            "--reconciling_spec_path", str(spec)], plan),
        ("3_5_info", ["3_5_info_seperating.py", "--output_dir", str(a),
                      "--reconciling_spec_path", str(spec),
                      "--architecting_plan_path", str(plan),
                      "--translating_blueprint_path", str(blueprint),
                      "--preprocess_subdir", "info_seperating_inputs",
                      "--use_generation_order"], a / "info_seperating_inputs"),
        ("4_contracting", ["4_contracting.py", "--paper_name", "paper",
                           "--gpt_version", gpt_version, "--reasoning_effort", "high",
                           "--output_dir", str(a),
                           "--preprocess_dir", str(a / "info_seperating_inputs"),
                           "--artifact_subdir", "contracting_artifacts"],
         a / "contracting_implementation_contract.json"),
        ("5_engineering", ["5_engineering.py", *paper, "--output_dir", str(a),
                           "--output_repo_dir", str(repo),
                           "--translating_blueprint_path", str(blueprint),
                           "--reconciling_dag_path", str(a / "reconciling_dag.json"),
                           "--architecting_structure_path", str(a / "architecting_structure.json"),
                           "--contracting_contract_path",
                           str(a / "contracting_implementation_contract.json"),
                           "--reference_registry_path", str(a / "reference_registry.json")], repo),
    ], codes


def run_papercompiler(project, context):
    """Run the stages in order. A finished stage leaves a marker so a rerun resumes."""
    project = pathlib.Path(project)
    out = project / "4_code"
    artifacts, repo, logs = out / "artifacts", out / "repo", out / "logs"
    for directory in (artifacts, logs):
        directory.mkdir(parents=True, exist_ok=True)
    stages, codes = pipeline_commands(project / "2_paper" / "paper.tex", artifacts, repo,
                                      context.get("compiler_model", "o3-mini"))
    env = {**os.environ, "OPENAI_API_KEY": "unused-shim",
           "PYTHONPATH": str(SHIMS) + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "PYTHONIOENCODING": "utf-8"}
    if context.get("code_model"):
        env["PF_CLAUDE_MODEL"] = context["code_model"]
    for name, args, _expected in stages:
        marker = artifacts / f".done_{name}"
        if marker.is_file():
            continue
        done = subprocess.run([sys.executable, str(codes / args[0]), *args[1:]], cwd=PAPERCOMPILER,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=env, shell=False)
        (logs / f"{name}.log").write_text(done.stdout + "\n--- stderr ---\n" + done.stderr,
                                          encoding="utf-8")
        if done.returncode != 0:
            raise ValueError(f"PaperCompiler stage {name} failed (exit {done.returncode}); "
                             f"see {logs / (name + '.log')}")
        marker.write_text(now(), encoding="utf-8")
    if not repo.is_dir() or not any(repo.rglob("*.py")):
        raise ValueError("PaperCompiler produced no Python files in 4_code/repo")
    return repo


def unresolved_items(path, limit=15):
    """What PaperCompiler could not take from the paper, as weaknesses for the writer.

    Reads either `artifacts/open_design_choices.json` (agent mode: a list of strings) or
    PaperCompiler's `reconciling_spec.json` (pipeline mode: keys like open_design_choices).
    """
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    found = []

    def add(key, item):
        text = item if isinstance(item, str) else " ".join(
            str(v) for v in (item.values() if isinstance(item, dict) else [item]))
        if text.strip():
            found.append({"location": f"PaperCompiler: {key}", "issue": text.strip()[:300],
                          "fix": "State this in the paper (value, definition or protocol), or "
                                 "narrow the claim that depends on it."})

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in UNRESOLVED_KEYS and isinstance(value, list):
                    for item in value:
                        add(key, item)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if isinstance(data, list):
        for item in data:
            add("open_design_choices", item)
    else:
        walk(data)
    return found[:limit]


# -- prompts -----------------------------------------------------------------

CONTRACT = (
    "RESULTS CONTRACT\n"
    "- ./2_paper/results_spec.json lists the result slots the paper needs; ./2_paper/paper.tex "
    "shows where each lands (\\PFVAL = one number, \\PFFIG = a figure). The repository must compute "
    "every non-optional slot.\n"
    "- Write ./4_code/repo/pf_run.py. When run as `python pf_run.py` it runs the paper's "
    "experiments at PILOT SCALE and writes the file $PF_OUT_DIR/results.json (read PF_OUT_DIR from "
    "the environment) shaped as {\"values\": {\"<slot id>\": <number>}, \"series\": {\"<slot id>\": "
    "{\"x\": [...], \"series\": {\"<name>\": [...numbers, one per x]}}}, \"notes\": \"what was run, "
    "at what scale, on what data\"}.\n"
    "- Report only numbers the code computes. Never hard-code a result or copy one from the paper.\n"
    "- The sandbox has NO network and a read-only repository. Use data under $PF_DATA_DIR when it "
    "exists, otherwise a small synthetic dataset that fits the paper's setup, and say so in notes. "
    "The whole run must finish within about 20 minutes on 2 CPUs.\n"
    "- Import the repository's own modules from pf_run.py; do not reimplement the method there.\n"
    "- List every third-party package in ./4_code/repo/requirements.txt.\n"
    "- You have no shell: do not try to run code. Do not modify anything outside ./4_code.\n")


def generate_prompt(slots):
    ids = "\n".join(f"- {s['id']} ({s['kind']}): {s['describe']}" for s in slots)
    return (
        "Implement the paper in ./2_paper/paper.tex as a code repository using the PaperCompiler "
        f"method. The method is defined by the files in {PAPERCOMPILER}: read README.md and "
        "codes/*.py (the prompt text inside each stage script is that stage's instruction; read "
        "them, do not run them). Work through the stages on this paper:\n"
        "1. implementation blueprint: what the paper states, what it leaves open;\n"
        "2. reconcile into explicit requirements, each labelled paper_fact / inferred / unresolved;\n"
        "3. repository architecture, with every requirement owned by a file;\n"
        "4. a contract per file (interfaces, inputs, outputs);\n"
        "5. write the files in dependency order, honouring the contracts.\n"
        "Write the stage artifacts to ./4_code/artifacts/ (blueprint.md, requirements.json, "
        "architecture.json) and every question the paper left open to "
        "./4_code/artifacts/open_design_choices.json as a JSON list of short strings. Write the "
        "repository to ./4_code/repo/.\n\n"
        "The paper's tables and figures are still EMPTY: they are the requirements. Slots:\n"
        f"{ids}\n\n{CONTRACT}")


def harness_prompt(slots):
    ids = "\n".join(f"- {s['id']} ({s['kind']}): {s['describe']}" for s in slots)
    return ("A repository was generated from ./2_paper/paper.tex in ./4_code/repo. Add the "
            f"results harness.\nSlots:\n{ids}\n\n{CONTRACT}")


def repair_prompt(problems, slots):
    ids = ", ".join(s["id"] for s in slots if not s.get("optional"))
    return ("The repository in ./4_code/repo failed in the sandbox. Fix it: edit the files, "
            "keep the contract, and do not hard-code results.\n\nPROBLEMS\n"
            + "\n".join(f"- {p}" for p in problems)[-6000:]
            + f"\n\nRequired slot ids: {ids}\n\n{CONTRACT}")


# -- checks ------------------------------------------------------------------

def repo_problems(repo, slots):
    """Static checks before spending a sandbox run."""
    repo = pathlib.Path(repo)
    if repo.is_symlink() or any(path.is_symlink() for path in repo.rglob("*")):
        return ["generated repo contains symlinks; refuse host-path escape"]
    harness = repo / "pf_run.py"
    if not harness.is_file():
        return ["pf_run.py is missing from the repository root"]
    problems = []
    source = harness.read_text(encoding="utf-8", errors="replace")
    try:
        compile(source, "pf_run.py", "exec")
    except SyntaxError as exc:
        problems.append(f"pf_run.py does not parse: {exc}")
    if "PF_OUT_DIR" not in source or "results.json" not in source:
        problems.append("pf_run.py must write results.json into the PF_OUT_DIR directory")
    corpus = "".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in repo.rglob("*.py") if "__pycache__" not in p.parts)
    missing = [s["id"] for s in slots if not s.get("optional") and s["id"] not in corpus]
    if missing:
        problems.append("slot ids never mentioned in the code: " + ", ".join(missing))
    return problems


def results_log(payload, command, image, repo_hash, scale='pilot'):
    mode_text = (
        "Generated code ran in network-isolated Docker with a *self-reported* "
        "provided dataset and registered seeds. Actual data usage and scientific "
        "validity have not been independently verified."
        if scale == 'validation_data_attempt' else
        "Generated code ran in network-isolated Docker at pilot scale; results "
        "are not full-scale evidence and must not be presented as such."
    )
    lines = ["", "## Results from running the paper's generated code", "",
             mode_text, "",
             f"* **Run notes:** {payload.get('notes', 'none')}",
             f"* **Command:** `{' '.join(command)}`",
             f"* **Image:** `{image}`", f"* **Repository hash:** `{repo_hash}`", "",
             "| slot id | value |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted((payload.get("values") or {}).items())]
    for key, item in sorted((payload.get("series") or {}).items()):
        curves = "; ".join(f"{n}: {ys[0]} .. {ys[-1]}" for n, ys in item["series"].items())
        lines.append(f"| {key} (series over {len(item['x'])} points) | {curves} |")
    return "\n".join(lines) + "\n"


def artifact_ok(project):
    """True when 4_code/results.json is valid and covers every required slot."""
    project = pathlib.Path(project)
    try:
        spec = results_mod.load_spec(project / "2_paper" / "results_spec.json")
        payload = results_mod.read_results(project / "4_code" / "results.json")
    except ValueError as exc:
        return False, str(exc)
    missing = results_mod.missing_slots(spec, payload)
    if missing:
        return False, "slots without results: " + ", ".join(missing)
    return True, (f"{len(payload.get('values') or {})} values, "
                  f"{len(payload.get('series') or {})} series from the sandbox")


# -- the stage ---------------------------------------------------------------

VALIDATION_CONTRACT = (
    "\nVALIDATION EXPERIMENT CONTRACT (OVERRIDES ALL PILOT/SYNTHETIC FALLBACKS):\n"
    "- Read the locked _inputs/research_protocol.json and implement its split, baselines, "
    "analysis, metric and ablation commitments.\n"
    "- Use ONLY the mounted $PF_DATA_DIR for experimental data. If real data are absent, "
    "or the split cannot be implemented, FAIL and do not emit metrics.\n"
    "- Run each registered seed, preserve per-seed metrics in notes/artifacts, "
    "and NEVER select the best seed post hoc.\n"
    "- Output data_source='provided', seeds=<exact preregistered seed list>, "
    "n_samples=<positive number of real samples actually evaluated>, and "
    "seed_metrics={<metric ID>: [one value per registered seed]}; report the "
    "arithmetic mean as values[metric ID] for each seed_metrics entry.\n"
    "- Do not claim independently validated results; the run is still model-generated code.\n"
)


def _validate_data_attestation(project, payload):
    from factory.science.protocol import check, PROTOCOL
    ok, problems = check(project, {'science_mode': 'validation'})
    if not ok:
        raise ValueError('invalid validation preregistration: ' + '; '.join(problems))
    spec = json.loads((project / PROTOCOL).read_text(encoding='utf-8'))
    if payload.get('data_source') != 'provided':
        raise ValueError('validation experiment must explicitly report provided data source')
    if payload.get('seeds') != spec['design']['random_seeds']:
        raise ValueError('validation experiment did not report all locked random seeds in order')
    count = payload.get('n_samples')
    if type(count) is not int or count <= 0:
        raise ValueError('validation experiment must report a positive real sample count')
    from factory.science.statistics import summarize
    stat = summarize(payload, primary_metric=spec['design']['primary_metric'],
                     seeds=spec['design']['random_seeds'])
    if stat['status'] != 'PASS':
        raise ValueError('per-seed metric checks failed: ' + '; '.join(stat['issues']))


def run(project, context=None, sandbox=None, session=run_session, build_repo=None,
        health=sandbox_mod.healthcheck):
    """Generate code from the empty-results draft, run it sandboxed, write 4_code/results.json."""
    project = pathlib.Path(project).resolve()
    context = context or {}
    if sandbox is None:
        status = health()
        if status["status"] != "PASS":
            raise ValueError(f"{status['detail']} -- {status.get('remedy', '')}".strip(" -"))
        sandbox = sandbox_mod.Sandbox(context.get("sandbox_image", sandbox_mod.DEFAULT_IMAGE),
                                      allow_network_install=context.get("allow_network_install", False))
    if not (project / "2_paper" / "paper.tex").is_file():
        raise ValueError("no 2_paper/paper.tex; run the write step first")
    spec = results_mod.load_spec(project / "2_paper" / "results_spec.json")
    slots = spec["slots"]
    out = project / "4_code"
    out.mkdir(parents=True, exist_ok=True)
    repo = out / "repo"
    options = {"cwd": project, "tools": TOOLS, "add_dirs": [PAPERCOMPILER],
               "model": context.get("code_model"), "timeout": int(context.get("code_timeout", 5400))}
    vendor_before = tree_hash(PAPERCOMPILER) if PAPERCOMPILER.is_dir() else ""

    validation = context.get('science_mode') == 'validation'
    if validation:
        from factory.science.protocol import check
        ok, problems = check(project, context)
        if not ok:
            raise ValueError('experiment requires locked protocol: ' + '; '.join(problems))
    mode = context.get("code_mode", "agent")
    if mode == "pipeline":
        (build_repo or run_papercompiler)(project, context)
        session(harness_prompt(slots) + (VALIDATION_CONTRACT if validation else ""), **options)
        open_choices = out / "artifacts" / "reconciling_spec.json"
    elif mode == "agent":
        from factory.integrations.ledger import enabled
        from factory.integrations.methodology import brief
        methodology = brief("experiment") if enabled(context) else ""
        session(generate_prompt(slots) + "\n\n" + methodology + (VALIDATION_CONTRACT if validation else ""), **options)
        open_choices = out / "artifacts" / "open_design_choices.json"
    else:
        raise ValueError("code_mode must be 'agent' or 'pipeline'")

    attempts, payload, command = [], None, ["python", "pf_run.py"]
    problems = repo_problems(repo, slots)
    for attempt in range(1, int(context.get("code_run_attempts", 3)) + 1):
        record = {"attempt": attempt}
        if not problems:
            requirements = repo / "requirements.txt"
            if not requirements.is_file():
                requirements.write_text("", encoding="utf-8")
            installed = sandbox.install(repo, out / "deps")
            scratch = out / "sandbox_out"
            if scratch.exists():
                shutil.rmtree(scratch)
            data = project / "_inputs" / "data"
            if installed.get("status") == "FAIL":
                ran = {"status": "FAIL", "returncode": -1, "stdout": "",
                       "stderr": "dependency installation failed"}
            else:
                ran = sandbox.run(repo, command, scratch, deps=out / "deps",
                                  data=data if data.is_dir() else None,
                                  timeout=int(context.get("code_timeout", 3600)))
            record.update(install=installed.get("status"), run=ran["status"],
                          returncode=ran.get("returncode"))
            (out / "run.log").write_text(
                f"attempt {attempt}\n--- install ---\n{installed.get('stdout', '')}"
                f"{installed.get('stderr', '')}\n--- run stdout ---\n{ran['stdout']}\n"
                f"--- run stderr ---\n{ran['stderr']}\n", encoding="utf-8")
            try:
                payload = results_mod.read_results(scratch / "results.json")
                if validation:
                    _validate_data_attestation(project, payload)
                gaps = results_mod.missing_slots(spec, payload)
                problems = ([f"results.json has no result for: {', '.join(gaps)}"] if gaps else [])
                if installed.get("status") == "FAIL" or ran.get("status") != "PASS" or ran.get("returncode", 1) != 0:
                    problems.append("sandbox install/run did not exit successfully; results are not trustworthy")
            except ValueError as exc:
                payload = None
                problems = [str(exc), (ran["stderr"] or ran["stdout"])[-3000:],
                            (installed.get("stderr") or "")[-1500:]]
                problems = [p for p in problems if p]
        record["problems"] = problems
        attempts.append(record)
        if not problems:
            break
        if attempt < int(context.get("code_run_attempts", 3)):
            session(repair_prompt(problems, slots) + (VALIDATION_CONTRACT if validation else ""), **options)
            problems = repo_problems(repo, slots)
            payload = None
    if payload is None or problems:
        raise ValueError("the generated code did not produce results for every slot after "
                         f"{len(attempts)} attempt(s): {'; '.join(problems)[:500]}; see 4_code/run.log")

    if vendor_before and tree_hash(PAPERCOMPILER) != vendor_before:
        raise ValueError("the session modified vendor/PaperCompiler-main; refusing the result")
    repo_hash = tree_hash(repo)
    saved = {"schema_version": 1, "generated_at": now(), "values": payload.get("values") or {},
             "series": payload.get("series") or {}, "notes": payload.get("notes", ""),
             "command": command, "image": sandbox.image, "repo_sha256": repo_hash,
             "attempts": attempts, "scale": "validation_data_attempt" if validation else "pilot",
             "data_source": payload.get('data_source', 'unverified'),
             "seeds": payload.get('seeds', []), "n_samples": payload.get('n_samples'),
             "seed_metrics": payload.get('seed_metrics', {}),
             "mode": mode}
    (out / "results.json").write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    (out / "experimental_log.generated.md").write_text(
        (results_log(payload, command, sandbox.image, repo_hash,
                     scale="validation_data_attempt" if validation else "pilot")
         + ("\n## Validation-mode attestation\n"
            "Generated code reports using the provided dataset and all locked seeds. "
            "This attestation has not been independently validated.\n" if validation else "")),
        encoding="utf-8")
    unresolved = unresolved_items(open_choices)
    (out / "unresolved.json").write_text(json.dumps(unresolved, indent=2) + "\n", encoding="utf-8")
    saved["unresolved"] = len(unresolved)
    return saved
