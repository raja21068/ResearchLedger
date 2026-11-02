"""Per-project literature library.

A paper is a record with an identity (DOI, arXiv id, other id), where and when it was retrieved, and four SEPARATE
verification levels that never imply each other:

  exists       the DOI / arXiv id resolves at Crossref or arXiv                (machine)
  metadata     the registry's title (and year) match the record               (machine)
  retrievable  an open page or PDF for it can be fetched                       (machine)
  supports     the paper really supports the statement it is cited for        (HUMAN ONLY, never automatic)

Duplicates are merged only on identity: DOI, then arXiv id, then another id, then an exact normalised title with the
same first author and year. Similar titles are never merged. Network access goes through one injectable `fetch(url) -> str`
(the same one refcheck uses), so tests run offline. Semantic Scholar is intentionally not an adapter.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Callable

from . import refcheck, workspace
from .db import Store, new_id, now

LIBRARY_MD = "literature/library.md"
SOURCES = ("openalex", "arxiv", "crossref")
LEVELS = ("exists", "metadata", "retrievable")
SUPPORT = ("unreviewed", "supported", "partly", "not_supported")


class LibraryError(Exception):
    pass


# ------------------------------------------------------------------ identity
def norm_doi(v: str | None) -> str | None:
    v = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", (v or "").strip(), flags=re.I).strip().lower()
    return v if re.fullmatch(r"10\.\d{4,9}/\S+", v) else None


def norm_arxiv(v: str | None) -> str | None:
    m = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", v or "")
    return m.group(1) if m else None


def _surname(authors: list[str]) -> str:
    if not authors:
        return ""
    a = authors[0].strip()
    a = a.split(",")[0] if "," in a else a.split()[-1] if a.split() else ""
    return re.sub(r"[^a-z]", "", a.lower())


def title_key(title: str, authors: list[str], year) -> str:
    return f"{refcheck._norm(title)}|{_surname(authors)}|{year or ''}"


def _clean(rec: dict) -> dict:
    authors = rec.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in re.split(r";|\band\b", authors) if a.strip()]
    try:
        year = int(rec.get("year")) if str(rec.get("year") or "").strip() else None
    except ValueError:
        year = None
    title = re.sub(r"\s+", " ", re.sub(r"[{}]", "", str(rec.get("title") or ""))).strip()
    if not title:
        raise LibraryError("a paper needs a title")
    arxiv = norm_arxiv(rec.get("arxiv_id") or rec.get("arxiv")) or norm_arxiv(rec.get("url") if "arxiv" in str(rec.get("url")) else "")
    return {"doi": norm_doi(rec.get("doi")), "arxiv_id": arxiv, "other_id": (str(rec.get("other_id") or "").strip() or None),
            "title": title[:500], "authors": [str(a)[:120] for a in authors][:60], "year": year,
            "venue": (str(rec.get("venue") or "").strip() or None), "url": (str(rec.get("url") or "").strip() or None),
            "abstract": (str(rec.get("abstract") or "").strip()[:4000] or None)}


def find(store: Store, project_id: str, c: dict) -> dict | None:
    """The existing record this one duplicates, or None. Identity ids first; a title match is only a duplicate when
    first author and year agree too and the two records do not carry different DOIs."""
    for col in ("doi", "arxiv_id", "other_id"):
        if c[col]:
            row = store.one(f"SELECT * FROM library_papers WHERE project_id=? AND {col}=?", (project_id, c[col]))
            if row:
                return row
    row = store.one("SELECT * FROM library_papers WHERE project_id=? AND title_key=?",
                    (project_id, title_key(c["title"], c["authors"], c["year"])))
    if row and not (row["doi"] and c["doi"] and row["doi"] != c["doi"]):
        return row if c["authors"] and c["year"] else None
    return None


# ------------------------------------------------------------------ records
def _row(r: dict) -> dict:
    r = dict(r)
    r["authors"], r["sources"] = json.loads(r["authors"] or "[]"), json.loads(r["sources"] or "[]")
    return r


def add(store: Store, project_id: str, rec: dict, source: str) -> tuple[dict, bool]:
    """Add a paper or fold it into its duplicate (only filling fields that are empty). Returns (record, created)."""
    c = _clean(rec)
    src = {"source": source, "retrieved_at": now()}
    dup = find(store, project_id, c)
    if dup:
        sets, args = [], []
        for col in ("doi", "arxiv_id", "other_id", "year", "venue", "url", "abstract"):
            if dup[col] in (None, "") and c[col]:
                sets.append(f"{col}=?")
                args.append(c[col])
        if not json.loads(dup["authors"] or "[]") and c["authors"]:
            sets.append("authors=?")
            args.append(json.dumps(c["authors"]))
        sources = json.loads(dup["sources"] or "[]")
        if not any(s["source"] == source for s in sources):
            sources.append(src)
        sets += ["sources=?", "updated_at=?"]
        args += [json.dumps(sources), now()]
        if any(s.startswith(("doi", "arxiv_id")) for s in sets):   # a new identity: earlier checks no longer cover it
            sets += ["exists_level='unchecked'", "metadata_level='unchecked'", "retrievable_level='unchecked'"]
        store.exec(f"UPDATE library_papers SET {', '.join(sets)} WHERE id=?", (*args, dup["id"]))
        return get(store, project_id, dup["id"]), False
    pid = new_id("lib")
    store.exec("INSERT INTO library_papers(id,project_id,doi,arxiv_id,other_id,title,title_key,authors,year,venue,url,abstract,"
               "sources,retrieved_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (pid, project_id, c["doi"], c["arxiv_id"], c["other_id"], c["title"],
                title_key(c["title"], c["authors"], c["year"]), json.dumps(c["authors"]), c["year"], c["venue"], c["url"],
                c["abstract"], json.dumps([src]), now(), now(), now()))
    return get(store, project_id, pid), True


def get(store: Store, project_id: str, paper_id: str) -> dict:
    r = store.one("SELECT * FROM library_papers WHERE id=? AND project_id=?", (paper_id, project_id))
    if not r:
        raise LibraryError("paper not found in this project's library")
    return _row(r)


def listing(store: Store, project_id: str) -> list[dict]:
    return [_row(r) for r in store.all("SELECT * FROM library_papers WHERE project_id=? ORDER BY created_at, id", (project_id,))]


# ------------------------------------------------------------------ adapters (parse only; the fetcher is injected)
def _openalex_abstract(inv: dict | None) -> str | None:
    if not inv:
        return None
    words = sorted((pos, w) for w, ps in inv.items() for pos in ps)
    return " ".join(w for _, w in words)[:4000] or None


def search_openalex(query: str, fetch: Callable[[str], str], n: int = 10) -> list[dict]:
    data = json.loads(fetch("https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per-page": n})))
    out = []
    for w in data.get("results") or []:
        loc = w.get("primary_location") or {}
        urls = [loc.get("landing_page_url") or ""] + [(x or {}).get("landing_page_url") or "" for x in w.get("locations") or []]
        arx = next((norm_arxiv(u) for u in urls if "arxiv.org" in u), None)
        out.append({"title": w.get("title") or w.get("display_name") or "", "year": w.get("publication_year"),
                    "doi": w.get("doi"), "arxiv_id": arx, "other_id": w.get("id"),
                    "authors": [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []],
                    "venue": ((loc.get("source") or {}).get("display_name")),
                    "url": (w.get("open_access") or {}).get("oa_url") or loc.get("landing_page_url"),
                    "abstract": _openalex_abstract(w.get("abstract_inverted_index"))})
    return [r for r in out if r["title"]]


def search_arxiv(query: str, fetch: Callable[[str], str], n: int = 10) -> list[dict]:
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom"}
    xml = fetch("http://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f"all:{query}", "max_results": n}))
    out = []
    for e in ET.fromstring(xml).findall("a:entry", ns):
        aid = norm_arxiv(e.findtext("a:id", "", ns))
        title = re.sub(r"\s+", " ", e.findtext("a:title", "", ns)).strip()
        if aid and title:
            out.append({"title": title, "year": (e.findtext("a:published", "", ns) or "")[:4], "arxiv_id": aid,
                        "authors": [x.findtext("a:name", "", ns) for x in e.findall("a:author", ns)], "venue": "arXiv",
                        "url": f"https://arxiv.org/abs/{aid}", "abstract": re.sub(r"\s+", " ", e.findtext("a:summary", "", ns)).strip()})
    return out


def search_crossref(query: str, fetch: Callable[[str], str], n: int = 10) -> list[dict]:
    data = json.loads(fetch("https://api.crossref.org/works?" + urllib.parse.urlencode({"query": query, "rows": n})))
    out = []
    for w in (data.get("message") or {}).get("items") or []:
        year = (((w.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
        out.append({"title": (w.get("title") or [""])[0], "year": year, "doi": w.get("DOI"),
                    "authors": [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in w.get("author") or []],
                    "venue": (w.get("container-title") or [""])[0] or None, "url": w.get("URL")})
    return [r for r in out if r["title"]]


def search(source: str, query: str, fetch: Callable[[str], str], n: int = 10) -> list[dict]:
    fn = {"openalex": search_openalex, "arxiv": search_arxiv, "crossref": search_crossref}.get(source)
    if not fn:
        raise LibraryError(f"source must be one of {', '.join(SOURCES)}")
    if len((query or "").strip()) < 3:
        raise LibraryError("type at least a few letters to search for")
    return fn(query.strip(), fetch, max(1, min(n, 25)))


def mark_known(store: Store, project_id: str, hits: list[dict]) -> list[dict]:
    """Tell the caller which search hits are already in the library (so the same paper is not re-found each round)."""
    out = []
    for h in hits:
        try:
            dup = find(store, project_id, _clean(h))
        except LibraryError:
            continue
        out.append({**h, "in_library": dup["id"] if dup else None})
    return out


# ------------------------------------------------------------------ import
def import_csv(store: Store, project_id: str, text: str, source: str = "import_csv") -> dict:
    created = merged = skipped = 0
    for row in csv.DictReader(io.StringIO(text)):
        try:
            _, new = add(store, project_id, {**row, "arxiv_id": row.get("arxiv") or row.get("arxiv_id")}, source)
        except LibraryError:
            skipped += 1
            continue
        created, merged = created + new, merged + (not new)
    return {"created": created, "merged": merged, "skipped": skipped}


def import_bib(store: Store, project_id: str, text: str, source: str = "import_bib") -> dict:
    created = merged = skipped = 0
    for e in refcheck.parse_bib(text):
        f = e["fields"]
        try:
            _, new = add(store, project_id, {"title": f.get("title"), "authors": f.get("author", ""), "year": f.get("year"),
                                             "doi": f.get("doi"), "arxiv_id": refcheck.arxiv_id(f),
                                             "venue": f.get("journal") or f.get("booktitle"), "url": f.get("url"),
                                             "other_id": f"bib:{e['key']}"}, source)
        except LibraryError:
            skipped += 1
            continue
        created, merged = created + new, merged + (not new)
    return {"created": created, "merged": merged, "skipped": skipped}


def import_file(store: Store, project_id: str, rel: str) -> dict:
    p = workspace.resolve(project_id, rel)
    if not p.is_file():
        raise LibraryError("file not found")
    text = p.read_text(encoding="utf-8", errors="replace")
    low = rel.lower()
    if low.endswith(".csv"):
        return import_csv(store, project_id, text)
    if low.endswith(".bib"):
        return import_bib(store, project_id, text)
    raise LibraryError("import a .csv (such as competitors.csv) or a .bib file")


# ------------------------------------------------------------------ verification (machine levels only)
def verify(store: Store, project_id: str, paper_id: str, fetch: Callable[[str], str]) -> dict:
    """Set exists / metadata / retrievable from the registries. Never touches the human `supports` level."""
    p = get(store, project_id, paper_id)
    exists, meta, retr, note = "unchecked", "unchecked", "unchecked", []
    found, unreachable = None, False
    for kind, ident in (("crossref", p["doi"]), ("arxiv", p["arxiv_id"])):
        if not ident or (kind == "crossref" and ident.startswith("10.48550/arxiv")):
            continue
        try:
            found = refcheck.lookup_crossref(ident, fetch) if kind == "crossref" else refcheck.lookup_arxiv(ident, fetch)
        except Exception as exc:  # noqa: BLE001 — network or parse problem: unknown, not "false"
            unreachable = True
            note.append(f"{kind} unreachable ({type(exc).__name__})")
            continue
        if found:
            break
    if not p["doi"] and not p["arxiv_id"]:
        note.append("no DOI or arXiv id, so existence cannot be checked")
    elif found:
        exists = "yes"
        sim = refcheck.title_similarity(p["title"], found["title"])
        year_ok = not (p["year"] and found.get("year")) or str(p["year"]) == str(found["year"])
        meta = "yes" if sim >= 0.8 and year_ok else "no"
        if meta == "no":
            note.append(f"registry says: {found['title'][:140]} ({found.get('year') or 'no year'})")
    elif found == {} and not unreachable:
        exists = "no"
        note.append("the identifier was not found at the registry")
    page = f"https://arxiv.org/abs/{p['arxiv_id']}" if p["arxiv_id"] else p["url"]
    if page and exists != "no":
        try:
            fetch(page)
            retr = "yes"
        except Exception as exc:  # noqa: BLE001
            retr = "no" if isinstance(exc, urllib.error.HTTPError) and exc.code in {403, 404, 410} else "unchecked"
            note.append(f"page not retrievable ({type(exc).__name__})")
    store.exec("UPDATE library_papers SET exists_level=?, metadata_level=?, retrievable_level=?, checked_at=?, check_note=?, "
               "updated_at=? WHERE id=?", (exists, meta, retr, now(), "; ".join(note)[:500] or None, now(), paper_id))
    return get(store, project_id, paper_id)


def set_supports(store: Store, project_id: str, paper_id: str, level: str, note: str) -> dict:
    """The human judgment that the paper supports the statement it is cited for. Needs a written reason."""
    if level not in SUPPORT:
        raise LibraryError(f"level must be one of {', '.join(SUPPORT)}")
    if level != "unreviewed" and len((note or "").strip()) < 10:
        raise LibraryError("say which statement and what you read in the paper (at least a short sentence)")
    get(store, project_id, paper_id)
    store.exec("UPDATE library_papers SET supports_level=?, supports_note=?, supports_at=?, updated_at=? WHERE id=?",
               (level, (note or "").strip()[:1000] or None, now(), now(), paper_id))
    return get(store, project_id, paper_id)


# ------------------------------------------------------------------ the file agents read
def render(store: Store, project_id: str) -> str:
    rows = listing(store, project_id)
    lines = ["# Literature library", "",
             "Generated by ResearchLedger; do not edit (use the Library page). One entry per paper, merged by DOI, arXiv id",
             "or exact title. Search this list BEFORE searching again, and do not re-add a paper that is here.",
             "Verification levels are separate: `exists` = the id resolves; `metadata` = the registry's title and year",
             "match; `retrievable` = an open page was fetched; `supported` = a person read it for a specific statement.",
             "Only `supported: yes` means the paper backs a claim. An existing DOI proves none of that.", ""]
    for r in rows:
        ident = " · ".join(x for x in (f"doi:{r['doi']}" if r["doi"] else "", f"arXiv:{r['arxiv_id']}" if r["arxiv_id"] else "",
                                        r["other_id"] or "") if x) or "no identifier"
        who = (r["authors"][0] + (" et al." if len(r["authors"]) > 1 else "")) if r["authors"] else "unknown authors"
        sup = {"supported": "yes", "partly": "partly", "not_supported": "NO", "unreviewed": "not reviewed"}[r["supports_level"]]
        lines += [f"- **{r['title']}** — {who}, {r['year'] or 'n.d.'}" + (f", {r['venue']}" if r["venue"] else ""),
                  f"  - {ident} · id `{r['id']}`",
                  f"  - exists: {r['exists_level']} · metadata: {r['metadata_level']} · retrievable: {r['retrievable_level']}"
                  f" · supported: {sup}" + (f" ({r['supports_note']})" if r["supports_note"] else "")]
    if not rows:
        lines.append("No papers recorded yet.")
    text = "\n".join(lines) + "\n"
    p = workspace.project_root(project_id) / LIBRARY_MD
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return text
