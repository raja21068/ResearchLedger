"""Check `paper/refs.bib` against Crossref (DOI) and arXiv (eprint / arXiv DOI).

Lightweight on purpose: for each entry we look the work up, compare the title, fill a field only
when it is missing, and flag entries that cannot be found. Network failure never fails the check;
the entry is marked "not_checked". Result is written to `paper/refcheck.json`.
"""
from __future__ import annotations

import difflib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from .db import now

BIB = "paper/refs.bib"
REPORT = "paper/refcheck.json"
UA = "ResearchLedger/1.0 (local reference check)"
_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.S)


# ---------------------------------------------------------------- bibtex
def parse_bib(text: str) -> list[dict]:
    """Entries as {type, key, fields, start, end} (start/end are offsets in text)."""
    out = []
    for m in _ENTRY.finditer(text):
        if m.group(1).lower() in {"comment", "string", "preamble"}:
            continue
        depth, i = 1, text.index("{", m.start()) + 1
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i - 1]
        out.append({"type": m.group(1).lower(), "key": m.group(2), "fields": _fields(body),
                    "start": m.start(), "end": i})
    return out


def _fields(body: str) -> dict[str, str]:
    fields, i = {}, 0
    for m in re.finditer(r"(\w+)\s*=\s*", body):
        if m.start() < i:
            continue
        j = m.end()
        if j >= len(body):
            break
        if body[j] == "{":
            depth, k = 1, j + 1
            while k < len(body) and depth:
                depth += {"{": 1, "}": -1}.get(body[k], 0)
                k += 1
            val, i = body[j + 1:k - 1], k
        elif body[j] == '"':
            k = body.index('"', j + 1) if '"' in body[j + 1:] else len(body)
            val, i = body[j + 1:k], k + 1
        else:
            k = re.search(r"[,\n}]", body[j:])
            k = j + (k.start() if k else len(body) - j)
            val, i = body[j:k], k
        fields[m.group(1).lower()] = re.sub(r"\s+", " ", val).strip()
    return fields


def _norm(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+|[{}\\$]", "", s or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


# ---------------------------------------------------------------- lookups
def _http_get(url: str, timeout: float = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310  (fixed https/http API hosts)
        return r.read().decode("utf-8", "replace")


def fetcher() -> Callable[[str], str]:
    """The network fetch used by the API (tests replace this to stay offline)."""
    return _http_get


def arxiv_id(fields: dict) -> str | None:
    cands = [fields.get("eprint", ""), fields.get("arxiv", ""), fields.get("url", ""), fields.get("doi", "")]
    for c in cands:
        m = re.search(r"arxiv[.:/ ]*(?:abs/)?(\d{4}\.\d{4,5})(?:v\d+)?", c, re.I) or \
            re.fullmatch(r"(\d{4}\.\d{4,5})(?:v\d+)?", c.strip())
        if m:
            return m.group(1)
    return None


def lookup_crossref(doi: str, fetch: Callable[[str], str]) -> dict | None:
    try:
        data = json.loads(fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")))["message"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}  # reachable, but the DOI does not exist
        raise
    authors = " and ".join(f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                           for a in data.get("author", []) if a.get("family"))
    year = ((data.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    return {"title": (data.get("title") or [""])[0], "author": authors, "year": str(year) if year else "",
            "journal": (data.get("container-title") or [""])[0], "source": "crossref"}


def lookup_arxiv(aid: str, fetch: Callable[[str], str]) -> dict | None:
    xml = fetch("http://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    if entry is None or entry.find("a:title", ns) is None or "Error" in (entry.findtext("a:title", "", ns) or ""):
        return {}
    authors = " and ".join(n.findtext("a:name", "", ns) for n in entry.findall("a:author", ns))
    pub = entry.findtext("a:published", "", ns)
    return {"title": re.sub(r"\s+", " ", entry.findtext("a:title", "", ns)).strip(), "author": authors,
            "year": pub[:4], "journal": "arXiv", "source": "arxiv"}


def check_entry(e: dict, fetch: Callable[[str], str]) -> dict:
    f = e["fields"]
    res = {"key": e["key"], "status": "not_checked", "source": None, "title_match": None, "filled": {}, "note": ""}
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", f.get("doi", "")).strip()
    aid = arxiv_id(f)
    if not doi and not aid:
        res["status"], res["note"] = "no_identifier", "no DOI or arXiv id to check against"
        return res
    found, unreachable = None, False
    for kind, ident in (("crossref", doi), ("arxiv", aid)):
        if not ident or (kind == "crossref" and doi.lower().startswith("10.48550/arxiv")):
            continue
        try:
            found = lookup_crossref(ident, fetch) if kind == "crossref" else lookup_arxiv(ident, fetch)
        except Exception as exc:  # network down, timeout, bad XML: degrade gracefully
            unreachable, res["note"] = True, f"{kind} unreachable: {type(exc).__name__}"
            continue
        if found:
            break
    if not found:
        if unreachable:
            return res
        res["status"], res["note"] = "not_found", "the identifier was not found at Crossref/arXiv"
        return res
    sim = title_similarity(f.get("title", ""), found["title"]) if f.get("title") else 0.0
    res.update(source=found["source"], title_match=round(sim, 2))
    res["status"] = "verified" if sim >= 0.8 else "title_mismatch"
    if res["status"] == "title_mismatch":
        res["note"] = f"title in the bib differs from the registry: {found['title'][:140]}"
        return res  # never write fields from a record that may be a different paper
    for field in ("author", "year", "journal"):
        if not f.get(field) and found.get(field):
            res["filled"][field] = found[field]
    return res


def check_file(root: Path, fetch: Callable[[str], str] = _http_get, apply: bool = True) -> dict:
    bib = root / BIB
    if not bib.is_file():
        raise ValueError(f"{BIB} is missing")
    text = bib.read_text(encoding="utf-8")
    entries = parse_bib(text)
    results = [check_entry(e, fetch) for e in entries]
    if apply and any(r["filled"] for r in results):
        orig = bib.with_name("refs.bib.orig")
        if not orig.exists():
            orig.write_text(text, encoding="utf-8")
        for e, r in sorted(zip(entries, results), key=lambda t: -t[0]["end"]):
            if r["filled"]:
                add = "".join(f",\n  {k} = {{{v}}}" for k, v in r["filled"].items())
                end = e["end"] - 1  # the entry's closing brace
                text = text[:end].rstrip().rstrip(",") + add + "\n" + text[end:]
        bib.write_text(text, encoding="utf-8")
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    report = {"checked_at": now(), "total": len(results), "counts": counts, "entries": results}
    (root / REPORT).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_report(root: Path) -> dict | None:
    p = root / REPORT
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
