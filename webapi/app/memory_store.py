"""Research memory v2: typed, sourced, versioned memories that agents read and the user governs.

Design (docs/RESEARCHLEDGER_OS_BLUEPRINT.md §5 P1; claim model after Hope Agent, failed-direction memory after
EvoScientist):
- five domains: literature, decision, experiment, failure, strategy;
- every memory has sources (`memory_evidence`: files, runs, loops, DOIs, URLs) and an append-only history
  (`memory_history`); nothing is edited in place: a correction is a new memory that supersedes the old one;
- statuses: proposed (by an agent, waits for the user) -> active, or rejected; needs_review (looks like it conflicts
  with an active memory) -> active or rejected; superseded (replaced by a correction);
- project-scoped by default; a memory with no project is global and is the only kind shared across projects;
- outcomes the server already records (idea scorecards, pre-registered experiment verdicts) are fed in
  automatically, so failed directions are never forgotten;
- agents read `memory/remembered.md` (generated here) and may propose memories in `memory/proposals.json`.

A memory is context, not proof: the text shown to agents says so.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import workspace
from .db import Store, new_id, now

DOMAINS = ("literature", "decision", "experiment", "failure", "strategy")
STATUSES = ("proposed", "active", "needs_review", "superseded", "rejected")
EVIDENCE_KINDS = ("file", "run", "loop", "doi", "arxiv", "url", "ledger", "note")
REMEMBERED_PATH = "memory/remembered.md"
PROPOSALS_PATH = "memory/proposals.json"
LABELS = {"failure": "Failed or rejected directions (including open verified reviewer findings)", "decision": "Decisions", "experiment": "Experiment results",
          "strategy": "Strategies that worked (including resolved verified reviewer findings)", "literature": "Literature notes"}
_lock = threading.Lock()


class MemoryError_(ValueError):
    pass


def _norm(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def _fts_put(store: Store, item_id: str, title: str, content: str, tags: list[str]) -> None:
    store.exec("DELETE FROM memory_fts WHERE item_id=?", (item_id,))
    store.exec("INSERT INTO memory_fts(item_id, title, content, tags) VALUES (?,?,?,?)",
               (item_id, title, content, " ".join(tags)))


def _history(store: Store, item_id: str, actor: str, action: str, detail: dict | None = None) -> None:
    store.exec("INSERT INTO memory_history(item_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (item_id, now(), actor, action, json.dumps(detail or {}, ensure_ascii=False)))


def add(store: Store, project_id: str | None, domain: str, title: str, content: str, origin: str,
        evidence: list[dict] | None = None, tags: list[str] | None = None, source_key: str | None = None,
        status: str | None = None, supersedes: str | None = None) -> dict:
    """Add a memory. Same `source_key` twice returns the existing one unchanged (auto-feed is idempotent)."""
    if domain not in DOMAINS:
        raise MemoryError_(f"domain must be one of {', '.join(DOMAINS)}")
    title, content = (title or "").strip()[:300], (content or "").strip()[:20000]
    if not title or not content:
        raise MemoryError_("a memory needs a title and content")
    if origin not in {"system", "user", "agent"}:
        raise MemoryError_("unknown origin")
    tags = [str(t).strip()[:40] for t in (tags or []) if str(t).strip()][:12]
    with _lock:
        if source_key:
            old = store.one("SELECT * FROM memory_items WHERE source_key=?", (source_key,))
            if old:
                return old
        status = status or ("proposed" if origin == "agent" else "active")
        conflict = None
        if status == "active" and not supersedes:
            for other in store.all("SELECT id, title FROM memory_items WHERE domain=? AND status='active' AND "
                                   "project_id IS ?", (domain, project_id)):
                if _norm(other["title"]) == _norm(title):
                    conflict, status = other["id"], "needs_review"
                    break
        mid, ts = new_id("mem"), now()
        store.exec("INSERT INTO memory_items(id, project_id, domain, title, content, status, origin, source_key, "
                   "confidence, tags, supersedes, conflict_with, created_at, updated_at) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (mid, project_id, domain, title, content, status, origin, source_key, "unassessed",
                    json.dumps(tags), supersedes, conflict, ts, ts))
        for e in evidence or []:
            kind = e.get("kind") if e.get("kind") in EVIDENCE_KINDS else "note"
            ref = str(e.get("ref") or "").strip()[:1000]
            if ref:
                store.exec("INSERT INTO memory_evidence(item_id, kind, ref, quote, created_at) VALUES (?,?,?,?,?)",
                           (mid, kind, ref, (e.get("quote") or None) and str(e["quote"])[:500], ts))
        _fts_put(store, mid, title, content, tags)
        _history(store, mid, origin, "created", {"status": status, "conflict_with": conflict})
    if project_id:
        render(store, project_id)
    return store.one("SELECT * FROM memory_items WHERE id=?", (mid,))


def get(store: Store, item_id: str) -> dict:
    it = store.one("SELECT * FROM memory_items WHERE id=?", (item_id,))
    if not it:
        raise MemoryError_("memory not found")
    it["tags"] = json.loads(it["tags"] or "[]")
    it["evidence"] = store.all("SELECT kind, ref, quote, created_at FROM memory_evidence WHERE item_id=? ORDER BY id",
                               (item_id,))
    it["history"] = store.all("SELECT ts, actor, action, detail FROM memory_history WHERE item_id=? ORDER BY id",
                              (item_id,))
    for h in it["history"]:
        h["detail"] = json.loads(h["detail"] or "{}")
    nxt = store.one("SELECT id FROM memory_items WHERE supersedes=?", (item_id,))
    it["superseded_by"] = nxt and nxt["id"]
    return it


def decide(store: Store, item_id: str, approve: bool, actor: str = "user", note: str = "") -> dict:
    """Approve or reject a proposed memory or one flagged as a possible conflict."""
    it = get(store, item_id)
    if it["status"] not in {"proposed", "needs_review"}:
        raise MemoryError_(f"this memory is {it['status']}; only proposed or flagged memories wait for a decision")
    status = "active" if approve else "rejected"
    store.exec("UPDATE memory_items SET status=?, updated_at=? WHERE id=?", (status, now(), item_id))
    _history(store, item_id, actor, "approved" if approve else "rejected", {"note": note[:500]} if note else None)
    if it["project_id"]:
        render(store, it["project_id"])
    return get(store, item_id)


def correct(store: Store, item_id: str, title: str, content: str, actor: str = "user",
            evidence: list[dict] | None = None) -> dict:
    """Replace a memory with a corrected one. The old one stays, marked superseded, with a link to the new one."""
    old = get(store, item_id)
    if old["status"] in {"superseded", "rejected"}:
        raise MemoryError_(f"this memory is already {old['status']}")
    new = add(store, old["project_id"], old["domain"], title or old["title"], content, actor if actor in
              {"user", "agent", "system"} else "user", evidence=evidence or old["evidence"], tags=old["tags"],
              status="active", supersedes=item_id)
    store.exec("UPDATE memory_items SET status='superseded', updated_at=? WHERE id=?", (now(), item_id))
    _history(store, item_id, actor, "superseded", {"by": new["id"]})
    if old["project_id"]:
        render(store, old["project_id"])
    return get(store, new["id"])


def search(store: Store, project_id: str | None = None, q: str = "", domains: list[str] | None = None,
           statuses: list[str] | None = None, include_global: bool = True, limit: int = 100) -> list[dict]:
    """Project memories (plus global ones), optionally full-text searched. project_id=None searches everything."""
    where, args = [], []
    if project_id:
        where.append("(m.project_id=?" + (" OR m.project_id IS NULL)" if include_global else ")"))
        args.append(project_id)
    if domains:
        where.append(f"m.domain IN ({','.join('?' * len(domains))})")
        args += domains
    if statuses:
        where.append(f"m.status IN ({','.join('?' * len(statuses))})")
        args += statuses
    terms = [t for t in re.findall(r"\w+", q or "") if len(t) > 1][:12]
    if terms:
        where.append("m.id IN (SELECT item_id FROM memory_fts WHERE memory_fts MATCH ?)")
        args.append(" OR ".join(f'"{t}"' for t in terms))
    sql = ("SELECT m.*, p.title AS project FROM memory_items m LEFT JOIN projects p ON p.id=m.project_id "
           + (("WHERE " + " AND ".join(where)) if where else "") + " ORDER BY m.updated_at DESC LIMIT ?")
    rows = store.all(sql, (*args, limit))
    for r in rows:
        r["tags"] = json.loads(r["tags"] or "[]")
        r["sources"] = store.one("SELECT COUNT(*) n FROM memory_evidence WHERE item_id=?", (r["id"],))["n"]
    return rows


def render(store: Store, project_id: str) -> str:
    """Write memory/remembered.md: the active memories agents read before every task (newest first per domain)."""
    rows = search(store, project_id, statuses=["active"], limit=400)
    lines = ["# What this project remembers", "",
             "Generated by ResearchLedger from the memory store; do not edit this file (use the Memory page).",
             "These are records of earlier work, each with its sources. Use them as context, not as proof: check a",
             "source before relying on it. Do not repeat a failed direction unless you address why it failed.", ""]
    order = ["failure", "decision", "experiment", "strategy", "literature"]
    for d in order:
        items = [r for r in rows if r["domain"] == d][:25]
        if not items:
            continue
        lines += [f"## {LABELS[d]}", ""]
        for r in items:
            ev = store.all("SELECT kind, ref FROM memory_evidence WHERE item_id=? ORDER BY id LIMIT 4", (r["id"],))
            src = "; ".join(f"{e['kind']}: {e['ref']}" for e in ev) or "no source recorded"
            scope = " (all projects)" if r["project_id"] is None else ""
            body = r["content"] if len(r["content"]) <= 700 else r["content"][:700] + " …"
            lines += [f"- **{r['title']}**{scope} — {body}", f"  - Sources: {src} · memory id `{r['id']}`"]
        lines.append("")
    if len(lines) <= 6:
        lines.append("Nothing recorded yet.")
    text = "\n".join(lines) + "\n"
    p = workspace.project_root(project_id) / REMEMBERED_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return text


# ------------------------------------------------------------------ automatic feed from recorded outcomes
def _first_heading(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        return None
    return None


def ingest_loops(store: Store, project_id: str) -> int:
    """Turn finished idea scorecards and experiment verdicts into memories (idempotent). Returns how many were added."""
    from . import loops
    root = workspace.project_root(project_id)
    added = 0
    for st in loops.all_states(project_id):
        lid, base = st["id"], f"loops/{st['id']}"
        if st["type"] == "idea_forge":
            target = float(st.get("params", {}).get("target_total", 75))
            for n, rnd in sorted((st.get("rounds") or {}).items(), key=lambda kv: int(kv[0])):
                m = rnd.get("metrics") or {}
                total = m.get("total")
                if total is None or int(n) == 0:
                    continue
                idea_file = f"{base}/idea_0.md" if int(n) == 1 else f"{base}/round_{int(n) - 1}/idea.md"
                title = _first_heading(root / idea_file) or f"Idea in loop {lid}, round {int(n) - 1}"
                flaws = m.get("fatal_flaws") or []
                passed = float(total) >= target and not flaws
                content = (f"Scored {total:g}/100 in round {n} (pass mark {target:g}). "
                           + (m.get("verdict") or "") + ("\nFatal flaws: " + " | ".join(flaws) if flaws else ""))
                ev = [{"kind": "loop", "ref": f"{lid} round {n}"}, {"kind": "file", "ref": idea_file}]
                for f in ("scorecard.json", "attack.md", "competitors.csv"):
                    if (root / base / f"round_{n}" / f).is_file():
                        ev.append({"kind": "file", "ref": f"{base}/round_{n}/{f}"})
                before = store.one("SELECT 1 FROM memory_items WHERE source_key=?", (f"loop:{lid}:r{n}:score",))
                add(store, project_id, "decision" if passed else "failure",
                    ("Idea passed scoring: " if passed else "Idea did not pass: ") + title, content, "system",
                    evidence=ev, tags=["idea", "scorecard"], source_key=f"loop:{lid}:r{n}:score")
                added += 0 if before else 1
        elif st["type"] == "experiment":
            prereg = {}
            try:
                prereg = {e["id"]: e for e in json.loads((root / base / "preregistration.json")
                                                         .read_text(encoding="utf-8")).get("experiments", [])}
            except (OSError, ValueError, KeyError, AttributeError):
                pass
            for n in sorted((st.get("rounds") or {}), key=int):
                vpath = root / base / f"round_{n}" / "verdicts.json"
                if not vpath.is_file():
                    continue
                try:
                    verdicts = json.loads(vpath.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                for eid, v in verdicts.items():
                    if not isinstance(v, dict) or v.get("verdict") not in {"supported", "not_supported", "inconclusive"}:
                        continue
                    hyp = (prereg.get(eid) or {}).get("hypothesis", "")
                    q = (prereg.get(eid) or {}).get("question") or eid
                    ok = v["verdict"] == "supported"
                    content = (f"Pre-registered {eid}: {hyp}\nVerdict: {v['verdict'].replace('_', ' ')}. "
                               f"{v.get('reason', '')}")
                    ev = [{"kind": "loop", "ref": f"{lid} round {n}"}, {"kind": "file", "ref": f"{base}/round_{n}/verdicts.json"}]
                    for f in ("analysis.md", "run_log.json"):
                        if (root / base / f"round_{n}" / f).is_file():
                            ev.append({"kind": "file", "ref": f"{base}/round_{n}/{f}"})
                    key = f"loop:{lid}:r{n}:{eid}"
                    before = store.one("SELECT 1 FROM memory_items WHERE source_key=?", (key,))
                    add(store, project_id, "experiment" if ok else "failure",
                        f"{eid} {'supported' if ok else v['verdict'].replace('_', ' ')}: {q}"[:300], content, "system",
                        evidence=ev, tags=["experiment", "pre-registered", v["verdict"]], source_key=key)
                    added += 0 if before else 1
    render(store, project_id)
    return added


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _quote_in(quote: str, text: str) -> bool:
    q = _norm_text(quote)
    return bool(q) and (q in text or (len(q) > 60 and q[:60] in text))


def _review_memory(store: Store, project_id: str, src: str, n: int, row: dict, closure: dict | None,
                   manuscript: str, revised: str | None, files: list[str]) -> bool:
    """One reviewer concern -> a memory, only if it is VERIFIED and its quote is really in the manuscript that was
    reviewed. A concern that is resolved becomes a strategy (the fix that worked); one that is still open stays a
    failure. A resolution counts as text-checked only when its new text is found in the revised manuscript.
    Returns True if a memory was added or superseded."""
    cid = row.get("id", "").upper() or "?"
    if row.get("verification", "").upper() != "VERIFIED" or not _quote_in(row.get("quote", ""), manuscript):
        return False  # an unverified comment stays a hypothesis, not a lesson
    sev = (row.get("severity") or "?").lower()
    resolved = bool(closure) and closure.get("status", "").lower() == "resolved"
    base = f"review:{src}:{n}:{cid}"
    key = f"{base}:{'resolved' if resolved else 'open'}"
    if store.one("SELECT 1 FROM memory_items WHERE source_key=?", (key,)):
        return False
    concern = row.get("concern", "")
    lines = [f"Verified reviewer finding ({sev}) in {row.get('location') or 'the manuscript'}: {concern}"]
    if row.get("minimum_fix"):
        lines.append(f"Minimum fix asked for: {row['minimum_fix']}")
    ev = [{"kind": "file", "ref": f} for f in files]
    ev.append({"kind": "note", "ref": f"reviewer perspective: {row.get('reviewer') or 'unknown'}",
               "quote": row.get("quote", "")[:400]})
    if resolved:
        how = closure.get("evidence") or closure.get("new_text") or ""
        text_checked = bool(revised) and _quote_in(closure.get("new_text", ""), revised or "")
        lines.append(("How it was resolved: " + how[:600]) if how else "Marked resolved.")
        lines.append("Resolution check: the new text was found in the revised manuscript." if text_checked
                     else "Resolution check: reported by the agent; the new text was not checked against the revised manuscript.")
        lesson = "Lesson: check for this before the manuscript is drafted."
        lines.append(lesson)
    else:
        lines.append("Status: still open when last recorded.")
    domain = "strategy" if resolved else "failure"
    title = (f"Reviewer finding ({sev}, resolved): " if resolved else f"Reviewer finding ({sev}, open): ") + concern[:150]
    old = store.one("SELECT id FROM memory_items WHERE source_key=?", (f"{base}:open",)) if resolved else None
    m = add(store, project_id, domain, title, "\n".join(lines), "system", evidence=ev,
            tags=["reviewer", sev, "verified"], source_key=key, supersedes=old and old["id"])
    if old and m.get("supersedes") == old["id"]:
        store.exec("UPDATE memory_items SET status='superseded', updated_at=? WHERE id=?", (now(), old["id"]))
        _history(store, old["id"], "system", "superseded", {"by": m["id"], "reason": "the finding was resolved"})
    return True


def ingest_reviews(store: Store, project_id: str) -> int:
    """Verified reviewer concerns from Paper Studio's review loop and from review-and-fix loops (idempotent)."""
    from . import loops, review_loop
    root = workspace.project_root(project_id)
    added = 0

    def text(rel: str | None) -> str | None:
        p = root / rel if rel else None
        return _norm_text(p.read_text(encoding="utf-8", errors="replace")) if p and p.is_file() else None

    # Paper Studio: review/concern_matrix.csv (+ closure.csv) per round; round 1 reviews paper/main.tex.
    for n in range(1, review_loop.MAX_ROUNDS + 1):
        f = review_loop.round_files(n)
        rows = review_loop._rows(root / f["matrix"])
        if not rows:
            break
        reviewed = text("paper/main.tex" if n == 1 else review_loop.round_files(n - 1)["tex"])
        if reviewed is None:
            continue
        closure = {r.get("id", "").upper(): r for r in review_loop._rows(root / f["closure"])}
        revised = text(f["tex"])
        for r in rows:
            if _review_memory(store, project_id, "paper", n, r, closure.get(r.get("id", "").upper()), reviewed, revised,
                              [f["matrix"], f["closure"], f["tex"]]):
                added += 1
    # Review-and-fix loops: loops/<id>/round_n/concerns.csv (+ closure.csv from the fix move).
    for st in loops.all_states(project_id):
        if st.get("type") != "review_fix" or "inputs" not in st:
            continue
        for n_s in sorted(st.get("rounds") or {}, key=int):
            n = int(n_s)
            cp = loops._rel(st, n, "concerns.csv")
            rows = loops._rows(root / cp)
            if not rows:
                continue
            try:
                reviewed = text(loops._manuscript_for(st, n))
            except (KeyError, TypeError):
                reviewed = None
            if reviewed is None:
                continue
            cl_rel = loops._rel(st, n, "closure.csv")
            closure = {r.get("id", "").upper(): r for r in loops._rows(root / cl_rel)}
            revised = text(loops._fixed_tex(st, n))
            for r in rows:
                if _review_memory(store, project_id, st["id"], n, r, closure.get(r.get("id", "").upper()), reviewed,
                                  revised, [cp, cl_rel]):
                    added += 1
    render(store, project_id)
    return added


def ingest_proposals(store: Store, project_id: str, run_id: str | None) -> int:
    """Read memory/proposals.json written by an agent: each becomes a *proposed* memory for the user to approve."""
    p = workspace.project_root(project_id) / PROPOSALS_PATH
    if not p.is_file():
        return 0
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    items = raw.get("memories") if isinstance(raw, dict) else raw
    n = 0
    for it in (items if isinstance(items, list) else [])[:20]:
        if not isinstance(it, dict):
            continue
        ev = [e for e in (it.get("sources") or []) if isinstance(e, dict)]
        if run_id:
            ev.append({"kind": "run", "ref": run_id})
        try:
            add(store, project_id, str(it.get("domain", "")), str(it.get("title", "")), str(it.get("content", "")),
                "agent", evidence=ev, tags=it.get("tags") if isinstance(it.get("tags"), list) else None)
            n += 1
        except MemoryError_:
            continue
    p.unlink()  # its content is kept by the file-version history and now lives in the memory store
    return n


def safe(fn, *args) -> int:
    """Run an ingest without ever breaking the run or loop it is attached to."""
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001
        return 0
