"""Independent review by another model, with the copy-and-paste made safe (docs/RESEARCHLEDGER_OS_BLUEPRINT.md).

Export: one folder and zip holding everything an outside reviewer (e.g. a ChatGPT temporary chat) needs: the
manuscript (PDF and LaTeX), an evidence summary (which numbers are backed, placeholders, the locked protocol), and
the Referee-Lean reviewer prompt plus an output contract that makes the reply importable. Nothing is sent anywhere;
the user takes the packet to the other tool.

Import: the pasted reply is parsed (JSON, CSV or a Markdown table) and every concern is checked against the
manuscript: it is VERIFIED only if its quote is really in the manuscript, otherwise UNVERIFIED. The result is saved as a
normal concern matrix (review/external_<n>/concern_matrix.csv), so the existing machinery (verified-major counting,
reviewer-finding memory, the Revise stage) works on it unchanged. An unsupported comment is shown, never acted on.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

from . import manuscript_trace, paper_studio, workspace
from .config import REPO_ROOT
from .db import Store, now

PACKETS = "review_packets"
EXTERNAL = "review"
LEAN = "vendor/20- Paper Review Agent/Referee-Lean-v2/core"
COLUMNS = ["id", "reviewer", "severity", "location", "concern", "quote", "verification", "minimum_fix", "closure_criterion"]
SEVERITIES = {"critical": "Major", "blocker": "Major", "fatal": "Major", "major": "Major", "high": "Major",
              "moderate": "Major", "medium": "Minor", "minor": "Minor", "low": "Minor", "nit": "Minor"}

CONTRACT = """# How to answer (required, so the reply can be imported)

Return ONE table in Markdown, and nothing after it, with exactly these columns:

| id | severity | location | concern | quote | minimum_fix |
|---|---|---|---|---|---|

- `id`: R1, R2, ... in order of importance.
- `severity`: Major or Minor. Major only if it could change what the paper's central claims support.
- `location`: section, table or figure.
- `concern`: one or two sentences. Say what is wrong and why it matters. Separate "not reported" from "reported and invalid".
- `quote`: a SHORT passage copied EXACTLY, character for character, from the manuscript text that the concern is about
  (at most one sentence). A concern whose quote is not found in the manuscript will be discarded, so do not paraphrase,
  and do not quote from this prompt or from the evidence summary.
- `minimum_fix`: the smallest change that would resolve it, without inventing results or citations.

Give at most 12 concerns. Report only what you can support from the manuscript and the evidence summary. If a
number is marked "untraced" in the evidence summary, you may ask for its source, but do not call it wrong without a
reason. Do not invent facts, citations, datasets or analyses.
"""


def _read(rel: str) -> str:
    p = REPO_ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _evidence_summary(store: Store, project_id: str, tex_rel: str) -> str:
    t = manuscript_trace.trace(store, project_id, tex_rel)
    c = t["counts"]
    lines = [f"# Evidence summary for `{tex_rel}`", "",
             "Prepared by ResearchLedger from the project's own records. It shows where numbers come from; it does not "
             "prove they are correct.", "",
             f"- Sources cited: {t['sources']} · tables: {t['tables']} · figures: {t['figures']} · words: {t['words']}",
             f"- Numbers in tables and the abstract: {t['reported']} "
             f"(backed by reviewed evidence: {c['backed']}, recorded by a run but not reviewed: {c['recorded']}, in a "
             f"results file only: {c['measured']}, matching no measured result: {c['untraced']})", ""]
    untraced = [n for n in t["numbers"] if n["backing"] == "untraced"]
    if untraced:
        lines += ["## Numbers that match no measured result (planned values such as thresholds are expected here)", ""]
        lines += [f"- `{n['value']}` ({n['where']}): …{n['context'][:120]}…" for n in untraced[:20]] + [""]
    if t["placeholders"]:
        lines += [f"## Placeholders still in the manuscript ({len(t['placeholders'])})", ""]
        lines += [f"- line {p['line']}: {p['text']}" for p in t["placeholders"][:20]] + [""]
    try:
        lk = paper_studio.lock_status(project_id)
    except ValueError:
        lk = {"locked": False}
    if lk.get("locked"):
        lines += ["## Protocol", "", f"The plan was locked (version {lk['version']}). "
                  + ("The protocol or declared results have changed since the lock." if lk.get("changed")
                     else "Nothing changed since the lock."),
                  *[f"Amendment {a['id']} ({a['status']}): {a['reason']}" for a in lk.get("amendments", [])], ""]
    else:
        lines += ["## Protocol", "", "The plan was not locked for this paper.", ""]
    return "\n".join(lines)


def build(store: Store, project_id: str, tex_rel: str) -> dict:
    root = workspace.project_root(project_id)
    tex = workspace.resolve(project_id, tex_rel)
    if tex.suffix.lower() != ".tex" or not tex.is_file():
        raise ValueError("choose a .tex manuscript in this project")
    summary = _evidence_summary(store, project_id, tex_rel)
    n = 1 + sum(1 for x in (root / PACKETS).glob("packet_*") if x.is_dir()) if (root / PACKETS).is_dir() else 1
    name = f"packet_{n}"
    d = root / PACKETS / name
    d.mkdir(parents=True, exist_ok=True)
    prompt = ("# Independent review of a manuscript\n\nYou are reviewing the attached manuscript as an independent "
              "referee. Read `evidence_summary.md` and the manuscript, then follow the reviewer discipline below and "
              "answer in the required format.\n\n" + CONTRACT + "\n---\n\n# Reviewer discipline (Referee Lean v2)\n\n"
              + _read(f"{LEAN}/LEAN_CORE_REVIEWER_PROMPT.md") + "\n\n---\n\n"
              + _read(f"{LEAN}/SEVERITY_ACTIONABILITY.md"))
    (d / "REVIEW_PROMPT.md").write_text(prompt, encoding="utf-8")
    (d / "evidence_summary.md").write_text(summary, encoding="utf-8")
    (d / "manuscript.tex").write_text(tex.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    pdf = tex.with_suffix(".pdf")
    if pdf.is_file():
        (d / "manuscript.pdf").write_bytes(pdf.read_bytes())
    (d / "README.txt").write_text(
        "How to use this packet\n1. Open a new private chat in the other tool (for example a ChatGPT temporary chat).\n"
        "2. Attach manuscript.pdf (or paste manuscript.tex) and evidence_summary.md, then paste REVIEW_PROMPT.md.\n"
        "3. Copy the reply (the table) and paste it into ResearchLedger: paper page -> Independent review -> Import.\n"
        "Do not paste anything secret into another tool. Nothing in this folder was sent anywhere by ResearchLedger.\n",
        encoding="utf-8")
    zpath = root / PACKETS / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(d.iterdir()):
            z.write(f, f.name)
    store.log_activity(project_id, "review_packet_built", f"{name} for {tex_rel}")
    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
    return {"packet": name, "folder": rel(d), "zip": rel(zpath), "manuscript": tex_rel, "has_pdf": pdf.is_file(),
            "prompt_file": rel(d / "REVIEW_PROMPT.md"), "summary_file": rel(d / "evidence_summary.md")}


# ------------------------------------------------------------------ import
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("“", '"').replace("”", '"').replace("’", "'")).lower().strip()


def _clean_cell(c: str) -> str:
    return re.sub(r"^[\s`*]+|[\s`*]+$", "", c or "").replace("\\|", "|").strip()


def parse_reply(text: str) -> list[dict]:
    """Rows from a JSON array/object, a CSV, or a Markdown table. Keys are lower-cased."""
    t = (text or "").strip()
    rows: list[dict] = []
    m = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", t, re.S)
    for cand in ([m.group(1)] if m else []) + [t]:
        try:
            data = json.loads(cand)
        except ValueError:
            continue
        data = data.get("concerns", data.get("issues", [data])) if isinstance(data, dict) else data
        if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
            return [{str(k).strip().lower(): str(v) for k, v in r.items()} for r in data]
    table = [l.strip() for l in t.splitlines() if l.strip().startswith("|") and l.strip().endswith("|")]
    if len(table) >= 3:
        head = [_clean_cell(c).lower() for c in table[0].strip("|").split("|")]
        for line in table[1:]:
            cells = [_clean_cell(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if len(cells) >= len(head):
                rows.append(dict(zip(head, cells[:len(head)])))
        if rows:
            return rows
    if "," in t and "\n" in t:
        try:
            rd = csv.DictReader(io.StringIO(t))
            rows = [{(k or "").strip().lower(): v or "" for k, v in r.items()} for r in rd]
            if rows and "concern" in rows[0]:
                return rows
        except csv.Error:
            pass
    return []


def import_reply(store: Store, project_id: str, tex_rel: str, text: str, source: str = "External reviewer") -> dict:
    root = workspace.project_root(project_id)
    tex = workspace.resolve(project_id, tex_rel)
    if tex.suffix.lower() != ".tex" or not tex.is_file():
        raise ValueError("choose a .tex manuscript in this project")
    rows = [r for r in parse_reply(text) if r.get("concern", "").strip()]
    if not rows:
        raise ValueError("I could not find a table of concerns in that reply. Ask the reviewer to answer in the table "
                         "format from REVIEW_PROMPT.md (columns: id, severity, location, concern, quote, minimum_fix).")
    manuscript = _norm(tex.read_text(encoding="utf-8", errors="replace"))
    out, seen = [], set()
    for i, r in enumerate(rows[:40], 1):
        q = r.get("quote", "").strip()
        qn = _norm(q)
        found = bool(qn) and (qn in manuscript or (len(qn) > 60 and qn[:60] in manuscript))
        cid = (r.get("id") or f"R{i}").strip().upper() or f"R{i}"
        while cid in seen:
            cid += "b"
        seen.add(cid)
        raw_sev = re.sub(r"[^a-z]", "", r.get("severity", "").lower())
        sev = "Major" if SEVERITIES.get(raw_sev) == "Major" or raw_sev.startswith("major") else "Minor"
        out.append({"id": cid, "reviewer": source[:80], "severity": sev, "location": r.get("location", "")[:200],
                    "concern": r.get("concern", "").strip()[:1500], "quote": q[:600],
                    "verification": "VERIFIED" if found else "UNVERIFIED", "minimum_fix": r.get("minimum_fix", r.get("fix", ""))[:800],
                    "closure_criterion": "The concern no longer applies to the revised manuscript."})
    k = 1 + sum(1 for x in (root / EXTERNAL).glob("external_*") if x.is_dir()) if (root / EXTERNAL).is_dir() else 1
    d = root / EXTERNAL / f"external_{k}"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "concern_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    (d / "raw_reply.md").write_text(text, encoding="utf-8")
    meta = {"manuscript": tex_rel, "source": source, "imported_at": now(), "total": len(out)}
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    verified = [r for r in out if r["verification"] == "VERIFIED"]
    major = [r for r in verified if r["severity"] == "Major"]
    store.log_activity(project_id, "external_review_imported", f"external_{k}: {len(verified)}/{len(out)} verified")
    feedback = ("Address these verified concerns from an independent reviewer (`" + f"{EXTERNAL}/external_{k}/concern_matrix.csv"
                + "`). Fix each in the manuscript with the smallest change that resolves it, without inventing results or "
                "citations; narrow a claim when the evidence does not exist. Concerns marked UNVERIFIED are not to be acted on.\n"
                + "\n".join(f"- {r['id']} ({r['severity']}): {r['concern']} | fix: {r['minimum_fix']}" for r in verified[:20]))
    return {"folder": f"{EXTERNAL}/external_{k}", "file": f"{EXTERNAL}/external_{k}/concern_matrix.csv", "total": len(out),
            "verified": len(verified), "verified_major": len(major), "unverified": len(out) - len(verified),
            "concerns": out, "feedback_for_revise": feedback if verified else None}


def listing(project_id: str) -> dict:
    root = workspace.project_root(project_id)
    packets = [{"name": p.stem, "zip": p.relative_to(root).as_posix()} for p in sorted((root / PACKETS).glob("packet_*.zip"))] \
        if (root / PACKETS).is_dir() else []
    imports = []
    for d in sorted((root / EXTERNAL).glob("external_*")) if (root / EXTERNAL).is_dir() else []:
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        imports.append({"folder": d.relative_to(root).as_posix(), **meta})
    tex = sorted(p.relative_to(root).as_posix() for p in (root / "paper").glob("*.tex")) if (root / "paper").is_dir() else []
    return {"packets": packets, "imports": imports, "manuscripts": tex}
