"""Document tools for Paper Studio: compare versions, targeted "revise this passage", submission package.

Edits are proposals: the agent writes `paper/edits/<id>.json` ({file, original, revised, rationale});
nothing changes in the manuscript until the user applies it, and applying replaces exactly the
quoted passage (it must occur once), after saving a backup.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import zipfile
from pathlib import Path

from . import claude_runner, review_loop, workspace
from .db import Store, new_id, now

EDITABLE = {".tex", ".md"}
EDIT_DIR = "paper/edits"
MAX_DIFF_LINES = 4000


def _text_file(project_id: str, rel: str) -> Path:
    p = workspace.resolve(project_id, rel)
    if not p.is_file() or p.suffix.lower() not in workspace.TEXT_EXT:
        raise ValueError(f"{rel} is not a text file in this project")
    return p


# ---------------------------------------------------------------- compare
def compare(project_id: str, a: str, b: str) -> dict:
    ta = _text_file(project_id, a).read_text(encoding="utf-8", errors="replace").splitlines()
    tb = _text_file(project_id, b).read_text(encoding="utf-8", errors="replace").splitlines()
    diff = list(difflib.unified_diff(ta, tb, fromfile=a, tofile=b, lineterm="", n=2))
    added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    return {"a": a, "b": b, "added": added, "removed": removed, "identical": not diff,
            "diff": diff[:MAX_DIFF_LINES], "truncated": len(diff) > MAX_DIFF_LINES}


# ---------------------------------------------------------------- targeted edits
def _edit_path(project_id: str, edit_id: str, suffix: str = ".json") -> Path:
    if not re.fullmatch(r"edt_[0-9a-f]+", edit_id):
        raise ValueError("bad edit id")
    return workspace.project_root(project_id) / EDIT_DIR / f"{edit_id}{suffix}"


def request_edit(store: Store, project_id: str, conversation_id: str, file: str, selection: str,
                 instruction: str) -> dict:
    p = _text_file(project_id, file)
    if p.suffix.lower() not in EDITABLE:
        raise ValueError("only .tex and .md files can be revised this way")
    selection = selection.strip()
    if len(selection) < 10:
        raise ValueError("select a longer passage (at least a sentence)")
    count = p.read_text(encoding="utf-8", errors="replace").count(selection)
    if count != 1:
        raise ValueError("the selected passage must appear exactly once in the file" if count else
                         "the selected passage was not found in the file (copy it exactly)")
    eid = new_id("edt")
    req = _edit_path(project_id, eid, ".request.json")
    req.parent.mkdir(parents=True, exist_ok=True)
    out = f"{EDIT_DIR}/{eid}.json"
    prompt = (f"Paper Studio — revise one passage.\nFile: `{file}`.\nPassage to revise (copy verbatim, appears once):\n"
              f"<<<\n{selection}\n>>>\n\nUser request: {instruction.strip() or 'improve clarity and concision'}\n\n"
              f"Read `{file}` for context (and `paper/refs.bib`, `results/*.json` if you need facts). Do NOT edit `{file}`. "
              f"Write `{out}` as JSON: {{\"file\": \"{file}\", \"original\": <the passage exactly as given>, "
              "\"revised\": <your replacement, same markup (LaTeX commands, \\\\cite keys) and same language>, "
              "\"rationale\": <one or two sentences>}. Rules: change only what the request needs; keep every number, "
              "citation key and label unless the request says otherwise; never add results, statistics or citations that "
              "are not already in the project files. Keep a TodoWrite checklist.")
    rid, ts = new_id("run"), now()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)", (rid, project_id, conversation_id, "paper:edit", prompt, "queued",
                                           "claude_code_cli", ts))
    req.write_text(json.dumps({"id": eid, "file": file, "selection": selection, "instruction": instruction,
                               "run_id": rid, "created_at": ts}, indent=2), encoding="utf-8")
    store.log_activity(project_id, "paper_edit_requested", f"{eid} {file}")
    claude_runner.start_run(store, rid)
    return {"edit_id": eid, "run_id": rid}


def _numbers(s: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", s))


def list_edits(store: Store, project_id: str) -> list[dict]:
    d = workspace.project_root(project_id) / EDIT_DIR
    out = []
    for req in sorted(d.glob("edt_*.request.json"), reverse=True) if d.is_dir() else []:
        r = json.loads(req.read_text(encoding="utf-8"))
        prop = d / f"{r['id']}.json"
        item = {**r, "status": "waiting", "proposal": None, "warnings": []}
        run = store.one("SELECT status FROM runs WHERE id=?", (r["run_id"],))
        if prop.is_file():
            try:
                pr = json.loads(prop.read_text(encoding="utf-8"))
                item["proposal"] = {k: str(pr.get(k, "")) for k in ("original", "revised", "rationale")}
                item["status"] = "applied" if pr.get("applied_at") else "proposed"
                item["applied_at"] = pr.get("applied_at")
                if pr.get("original", "").strip() != r["selection"]:
                    item["warnings"].append("the proposal's 'original' differs from the passage you selected")
                new = _numbers(item["proposal"]["revised"]) - _numbers(r["selection"])
                if new:
                    item["warnings"].append("new numbers not in the original passage: " + ", ".join(sorted(new)))
            except json.JSONDecodeError:
                item["status"] = "failed"
        elif run and run["status"] in {"failed", "cancelled"}:
            item["status"] = "failed"
        elif run and run["status"] == "succeeded":
            item["status"] = "failed"  # finished without writing the proposal
        out.append(item)
    return out


def apply_edit(store: Store, project_id: str, edit_id: str) -> dict:
    req_p, prop_p = _edit_path(project_id, edit_id, ".request.json"), _edit_path(project_id, edit_id)
    if not req_p.is_file() or not prop_p.is_file():
        raise ValueError("no proposal to apply")
    req, prop = json.loads(req_p.read_text(encoding="utf-8")), json.loads(prop_p.read_text(encoding="utf-8"))
    if prop.get("applied_at"):
        raise ValueError("this edit was already applied")
    target = _text_file(project_id, req["file"])
    text = target.read_text(encoding="utf-8")
    original, revised = req["selection"], str(prop.get("revised", ""))
    if not revised.strip():
        raise ValueError("the proposal is empty")
    if text.count(original) != 1:
        raise ValueError("the passage no longer appears exactly once in the file (it changed); request the edit again")
    backup = prop_p.parent / "backups" / f"{edit_id}_{target.name}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(text, encoding="utf-8")
    target.write_text(text.replace(original, revised, 1), encoding="utf-8")
    prop["applied_at"] = now()
    prop["backup"] = str(backup.relative_to(workspace.project_root(project_id))).replace("\\", "/")
    prop_p.write_text(json.dumps(prop, indent=2), encoding="utf-8")
    store.log_activity(project_id, "paper_edit_applied", f"{edit_id} {req['file']}")
    return {"edit_id": edit_id, "file": req["file"], "backup": prop["backup"]}


# ---------------------------------------------------------------- submission package
def _latest_manuscript(root: Path) -> tuple[str, str | None]:
    s = review_loop.summarize(root)
    tex = s["latest_tex"] or ("paper/main_revised.tex" if (root / "paper/main_revised.tex").is_file() else "paper/main.tex")
    pdf = tex[:-4] + ".pdf"
    return tex, pdf if (root / pdf).is_file() else None


def build_package(project_id: str) -> dict:
    root = workspace.project_root(project_id)
    tex, pdf = _latest_manuscript(root)
    if not (root / tex).is_file():
        raise ValueError("there is no manuscript to package yet (paper/main.tex)")
    warnings, files = [], {}  # archive name -> source path

    def add(rel: str, arc: str | None = None):
        p = root / rel
        if p.is_file():
            files[arc or rel] = p

    add(tex, "main.tex")
    if pdf:
        add(pdf, "main.pdf")
    else:
        warnings.append("no compiled PDF for the latest manuscript")
    add("paper/refs.bib", "refs.bib")
    for ext in ("*.sty", "*.cls", "*.bst"):
        for p in (root / "paper").glob(ext):
            add(f"paper/{p.name}", p.name)
    for fig_dir in ("paper/figures", "figures"):
        d = root / fig_dir
        for p in sorted(d.rglob("*")) if d.is_dir() else []:
            if p.is_file():
                add(str(p.relative_to(root)).replace("\\", "/"), f"figures/{p.relative_to(d)}".replace("\\", "/"))
    letter = next((r for n in range(review_loop.MAX_ROUNDS, 0, -1)
                   if (root / (r := review_loop.round_files(n)["response"])).is_file()), None)
    if letter:
        add(letter, "response_letter.md")
    else:
        warnings.append("no response letter yet (review/response_letter.md)")
    tex_text = (root / tex).read_text(encoding="utf-8", errors="replace")
    n_ph = len(re.findall(r"\\PF(?:VAL|FIG)\{", tex_text))
    if n_ph:
        warnings.append(f"{n_ph} placeholder(s) (\\PFVAL / \\PFFIG) are still in the manuscript: results not measured yet")
    if "[CITATION NEEDED]" in tex_text:
        warnings.append("the manuscript still contains [CITATION NEEDED]")
    prov = root / "results" / "provenance.json"
    if prov.is_file():
        add("results/provenance.json", "provenance.json")
    manifest = {"created_at": now(), "source_manuscript": tex, "warnings": warnings,
                "files": {a: hashlib.sha256(p.read_bytes()).hexdigest() for a, p in sorted(files.items())}}
    out_dir = root / "paper" / "package"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"submission_{now()[:19].replace(':', '').replace('-', '')}.zip"
    with zipfile.ZipFile(out_dir / name, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, p in sorted(files.items()):
            z.write(p, arc)
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
    return {"path": f"paper/package/{name}", "files": sorted(files), "warnings": warnings}
