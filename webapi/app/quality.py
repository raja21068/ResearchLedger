"""Submission gate: deterministic checks on a LaTeX manuscript, computed by the server, not judged by a model.

Built from what went wrong in the user's own papers (docs/QUALITY_PLAYBOOK.md): numbers that could not be traced
to any run, placeholders left in, citations that do not exist, figures that look like slides, papers far longer
than the target venue, and a style/length that did not match the example paper the user asked for.

    report = gate(root, "paper/main.tex", target_pages=12, target_refs=40, example_pdf="uploads/example.pdf")

Each check has status pass / warn / fail / info. `ready` means no check failed; it is not a publication verdict.
The report is written to quality/<stem>.json.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Callable

from . import refcheck
from .db import now

PLACEHOLDER = re.compile(r"\\PFVAL\{[^}]*\}|\\PFFIG\{[^}]*\}|\\pending\b|\\todo\b|\bTBD\b|\bTODO\b|\[CITATION NEEDED\]|"
                         r"\[RESULT[^\]]*\]|\bPLACEHOLDER\b|Placeholder (?:figure|table)|\?\?\?|XX\.X")
OVERCLAIM = re.compile(r"\b(the first|first to|novel|state-of-the-art|state of the art|SOTA|outperforms all|"
                       r"significantly|guarantees?|proves?|unprecedented|groundbreaking|revolutionary)\b", re.I)
STATS = re.compile(r"p\s*[<=>]\s*0?\.\d|confidence interval|\b95\s*\\?%|\bCI\b|\\pm|bootstrap|Wilcoxon|t-test|"
                   r"Clopper|standard deviation|\bstd\b", re.I)
_CITE = re.compile(r"\\(?:cite|citep|citet|citeauthor|parencite|textcite|autocite|citealp)\*?(?:\[[^\]]*\])*\{([^}]*)\}")
_NUM = re.compile(r"(?<![\w.\\{])(-?\d{1,6}\.\d+|\d{1,3}(?:\.\d+)?(?=\s*\\?%))")
RASTER = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}
VECTOR = {".pdf", ".eps", ".svg", ".ps"}


# ---------------------------------------------------------------- LaTeX helpers
def strip_comments(tex: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", tex)


def body(tex: str) -> str:
    m = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|$)", tex, re.S)
    return m.group(1) if m else tex


def words(tex: str) -> int:
    t = body(strip_comments(tex))
    t = re.sub(r"\\begin\{(table|tabular|figure|equation|align)\*?\}.*?\\end\{\1\*?\}", " ", t, flags=re.S)
    t = re.sub(r"\$[^$]*\$", " ", t)
    t = re.sub(r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?", " ", t)
    return len(re.findall(r"[A-Za-z][A-Za-z'-]+", t))


def cite_keys(tex: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _CITE.finditer(strip_comments(tex)):
        for k in m.group(1).split(","):
            if k.strip():
                seen.setdefault(k.strip(), None)
    return list(seen)


def bib_files(tex_path: Path, tex: str) -> list[Path]:
    out = []
    for group in re.findall(r"\\(?:bibliography|addbibresource)\{([^}]*)\}", strip_comments(tex)):
        for n in group.split(","):
            n = n.strip()
            p = tex_path.parent / (n if n.endswith(".bib") else n + ".bib")
            if p.is_file():
                out.append(p)
    return out


def bib_entries(tex_path: Path, tex: str) -> list[dict] | None:
    files = bib_files(tex_path, tex)
    if not files:
        return None
    entries = []
    for p in files:
        entries += refcheck.parse_bib(p.read_text(encoding="utf-8", errors="replace"))
    return entries


def lines_matching(tex: str, pattern: re.Pattern, limit: int = 40) -> list[dict]:
    out = []
    for i, line in enumerate(tex.splitlines(), 1):
        if line.lstrip().startswith("%"):
            continue
        for m in pattern.finditer(strip_comments(line)):
            out.append({"line": i, "match": m.group(0), "text": line.strip()[:160]})
            if len(out) >= limit:
                return out
    return out


# ---------------------------------------------------------------- numbers -> results/*.json
def result_values(results_dir: Path) -> list[float]:
    vals: list[float] = []

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)) and math.isfinite(x):
            vals.append(float(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for p in sorted(results_dir.rglob("*.json")) if results_dir.is_dir() else []:
        try:
            walk(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return vals


def reported_numbers(tex: str) -> list[dict]:
    """Decimal numbers and percentages inside tables and the abstract (where results live)."""
    t = strip_comments(tex)
    spans = [(m.start(), m.end(), "table") for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", t, re.S)]
    spans += [(m.start(), m.end(), "abstract") for m in re.finditer(r"\\begin\{abstract\}.*?\\end\{abstract\}", t, re.S)]
    out = []
    for a, b, where in spans:
        chunk = t[a:b]
        chunk = re.sub(r"\\(?:label|ref|cite\w*|includegraphics|caption)\*?(\[[^\]]*\])?\{[^}]*\}", " ", chunk) \
            if where == "abstract" else re.sub(r"\\(?:label|ref|cite\w*|includegraphics)\*?(\[[^\]]*\])?\{[^}]*\}", " ", chunk)
        chunk = re.sub(r"\\(?:hspace|vspace|arraystretch|setlength|resizebox|scalebox)\*?\{[^}]*\}(\{[^}]*\})?", " ", chunk)
        chunk = re.sub(r"\[[0-9.]+(pt|em|cm|mm|in|ex)\]|[0-9.]+\s*\\(?:linewidth|textwidth|columnwidth)", " ", chunk)
        for m in _NUM.finditer(chunk):
            out.append({"value": m.group(1), "where": where, "context": chunk[max(0, m.start() - 50):m.end() + 20].replace("\n", " ")})
    return out


def traced(value: str, vals: list[float]) -> bool:
    x = float(value)
    d = len(value.split(".")[1]) if "." in value else 0
    tol = 0.5 * 10 ** (-d) + 1e-9
    return any(abs(v - x) <= tol or abs(v * 100 - x) <= tol or abs(v / 100 - x) <= tol for v in vals)


def trace_numbers(tex: str, results_dir: Path) -> dict:
    vals = result_values(results_dir)
    nums = reported_numbers(tex)
    untraced = [n for n in nums if not traced(n["value"], vals)] if vals else nums
    return {"results_values": len(vals), "reported": len(nums), "untraced": untraced[:60],
            "untraced_count": len(untraced), "untraced_set": sorted({n["value"] for n in untraced})}


# ---------------------------------------------------------------- PDFs
def pdf_pages(path: Path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def pdf_profile(path: Path) -> dict | None:
    """Pages, words, figures, tables and (approximate) references of an example paper."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return None
    head, refs = text, ""
    m = list(re.finditer(r"\n\s*(References|REFERENCES|Bibliography)\s*\n", text))
    if m:
        head, refs = text[:m[-1].start()], text[m[-1].end():]
    figs = {n for n in re.findall(r"\b(?:Fig\.|Figure)\s*(\d+)", head)}
    tabs = {n for n in re.findall(r"\b(?:Table|TABLE)\s*([0-9]+|[IVX]+)\b", head)}
    nref = len(re.findall(r"^\s*\[\d+\]", refs, re.M)) or len(re.findall(r"\((?:19|20)\d{2}[a-z]?\)|\b(?:19|20)\d{2}[a-z]?\.\s", refs))
    return {"pages": len(reader.pages), "words": len(re.findall(r"[A-Za-z][A-Za-z'-]+", head)), "figures": len(figs),
            "tables": len(tabs), "references_approx": nref}


def tex_profile(tex: str, pages: int | None) -> dict:
    t = strip_comments(tex)
    return {"pages": pages, "words": words(tex), "figures": len(re.findall(r"\\begin\{figure\*?\}", t)),
            "tables": len(re.findall(r"\\begin\{table\*?\}", t)), "references_approx": len(cite_keys(tex)),
            "sections": re.findall(r"\\section\*?\{([^}]*)\}", t)}


# ---------------------------------------------------------------- figures
def figure_files(tex_path: Path, tex: str) -> list[dict]:
    t = strip_comments(tex)
    paths = [p.strip() for p in re.findall(r"\\graphicspath\{((?:\{[^}]*\})+)\}", t) for p in re.findall(r"\{([^}]*)\}", p)]
    out = []
    for name in re.findall(r"\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]*)\}", t):
        found = None
        for base in [tex_path.parent] + [tex_path.parent / g for g in paths]:
            cand = base / name
            for c in [cand] + [cand.with_name(cand.name + e) for e in (".pdf", ".png", ".jpg", ".eps")]:
                if c.is_file():
                    found = c
                    break
            if found:
                break
        item = {"name": name, "exists": bool(found), "kind": None, "pixels": None}
        if found:
            ext = found.suffix.lower()
            item["kind"] = "vector" if ext in VECTOR else "raster" if ext in RASTER else ext
            if ext in RASTER:
                try:
                    from PIL import Image
                    with Image.open(found) as im:
                        item["pixels"] = list(im.size)
                except Exception:
                    pass
        out.append(item)
    return out


# ---------------------------------------------------------------- the gate
def _item(cid, label, status, detail, items=None):
    return {"id": cid, "label": label, "status": status, "detail": detail, "items": items or []}


def gate(root: Path, tex_rel: str, target_pages: int | None = None, target_refs: int | None = 40,
         example_pdf: str | None = None, online: bool = False, fetch: Callable[[str], str] | None = None,
         results_dir: str = "results", write: bool = True) -> dict:
    tex_path = (root / tex_rel).resolve()
    tex = tex_path.read_text(encoding="utf-8", errors="replace")
    pdf = tex_path.with_suffix(".pdf")
    pages = pdf_pages(pdf) if pdf.is_file() else None
    checks = []

    # 1. compiled and current
    if not pdf.is_file():
        checks.append(_item("compile", "Compiled PDF", "fail", f"{pdf.name} does not exist — compile the manuscript"))
    elif pdf.stat().st_mtime + 1 < tex_path.stat().st_mtime:
        checks.append(_item("compile", "Compiled PDF", "warn", f"{pdf.name} is older than the .tex — recompile"))
    else:
        checks.append(_item("compile", "Compiled PDF", "pass", f"{pdf.name}, {pages} pages"))

    # 2. page budget
    if target_pages:
        if pages is None:
            checks.append(_item("pages", "Page budget", "warn", "page count unknown (no PDF)"))
        else:
            st = "pass" if pages <= target_pages else "warn" if pages <= target_pages + 1 else "fail"
            checks.append(_item("pages", "Page budget", st, f"{pages} pages (target ≤ {target_pages}); move extra "
                                "material to the supplement" if st != "pass" else f"{pages} pages (target ≤ {target_pages})"))

    # 3. placeholders
    ph = lines_matching(tex, PLACEHOLDER, 60)
    checks.append(_item("placeholders", "No placeholders left", "fail" if ph else "pass",
                        f"{len(ph)} placeholder(s) still in the manuscript" if ph else "none", ph))

    # 4. citations
    cited = cite_keys(tex)
    entries = bib_entries(tex_path, tex)
    if entries is None and not re.search(r"\\begin\{thebibliography\}", tex):
        checks.append(_item("bib", "Bibliography", "fail", "no .bib file found next to the manuscript and no thebibliography"))
    elif entries is not None:
        keys = {e["key"] for e in entries}
        missing = [k for k in cited if k not in keys]
        uncited = sorted(keys - set(cited))
        st = "fail" if missing else "pass"
        checks.append(_item("bib", "Every citation is in the bibliography", st,
                            f"{len(missing)} cited key(s) missing from the .bib" if missing else
                            f"all {len(cited)} cited keys resolve ({len(uncited)} uncited .bib entries)",
                            [{"match": k} for k in missing]))
    if target_refs:
        n = len(cited)
        st = "pass" if n >= target_refs else "warn" if n >= 0.75 * target_refs else "fail"
        checks.append(_item("refcount", "Reference count", st, f"{n} cited references (target ≥ {target_refs})"))
    if online and entries:
        fetch = fetch or refcheck.fetcher()
        used = [e for e in entries if e["key"] in set(cited)]
        res = [refcheck.check_entry(e, fetch) for e in used]
        bad = [r for r in res if r["status"] in {"not_found", "title_mismatch"}]
        noid = [r for r in res if r["status"] == "no_identifier"]
        st = "fail" if bad else "warn" if noid else "pass"
        checks.append(_item("refverify", "References exist (Crossref/arXiv)", st,
                            f"{sum(r['status'] == 'verified' for r in res)} verified, {len(bad)} not found or wrong title, "
                            f"{len(noid)} without DOI/arXiv id, {sum(r['status'] == 'not_checked' for r in res)} unreachable",
                            [{"match": r["key"], "text": f"{r['status']}: {r['note']}"} for r in bad + noid][:60]))

    # 5. numbers traceable to results/*.json
    tr = trace_numbers(tex, root / results_dir)
    if tr["reported"] == 0:
        checks.append(_item("numbers", "Numbers trace to results", "info", "no decimal numbers in tables or abstract"))
    elif tr["results_values"] == 0:
        checks.append(_item("numbers", "Numbers trace to results", "warn",
                            f"{tr['reported']} numbers in tables/abstract but no {results_dir}/*.json to trace them to",
                            [{"match": n["value"], "text": n["context"]} for n in tr["untraced"][:30]]))
    else:
        st = "pass" if tr["untraced_count"] == 0 else "warn"
        checks.append(_item("numbers", "Numbers trace to results", st,
                            f"{tr['reported'] - tr['untraced_count']} of {tr['reported']} numbers found in {results_dir}/*.json",
                            [{"match": n["value"], "text": n["context"]} for n in tr["untraced"][:30]]))

    # 6. figures
    figs = figure_files(tex_path, tex)
    missing_f = [f for f in figs if not f["exists"]]
    low = [f for f in figs if f["kind"] == "raster" and f["pixels"] and max(f["pixels"]) < 1500]
    raster = [f for f in figs if f["kind"] == "raster"]
    st = "fail" if missing_f else "warn" if low else "pass"
    checks.append(_item("figures", "Figures", st,
                        f"{len(figs)} figures: {len(figs) - len(raster) - len(missing_f)} vector, {len(raster)} raster"
                        + (f", {len(low)} below 1500 px (blurry in print)" if low else "")
                        + (f", {len(missing_f)} missing" if missing_f else ""),
                        [{"match": f["name"], "text": "missing" if not f["exists"] else f"raster {f['pixels']}"}
                         for f in missing_f + low]))

    # 7. claim calibration
    over = lines_matching(tex, OVERCLAIM, 40)
    no_stats = not STATS.search(strip_comments(tex))
    sig = [o for o in over if o["match"].lower() == "significantly"]
    st = "warn" if (sig and no_stats) or len(over) > 15 else "info"
    checks.append(_item("claims", "Claim language", st,
                        f"{len(over)} strong claim word(s)" + ("; 'significantly' is used but no test, interval or ± "
                                                              "appears in the paper" if sig and no_stats else ""), over))

    # 8. example paper: style and length
    profile = tex_profile(tex, pages)
    example = None
    if example_pdf:
        ex = (root / example_pdf)
        example = pdf_profile(ex) if ex.is_file() else None
        if not example:
            checks.append(_item("style", "Matches the example paper", "warn", f"could not read {example_pdf}"))
        else:
            dev = []
            for k in ("pages", "words", "figures", "tables", "references_approx"):
                a, b = profile.get(k), example.get(k)
                if a is None or not b:
                    continue
                if abs(a - b) / b > 0.2:
                    dev.append({"match": k, "text": f"manuscript {a} vs example {b} ({'+' if a > b else ''}{round((a - b) / b * 100)}%)"})
            checks.append(_item("style", "Matches the example paper (±20%)", "warn" if dev else "pass",
                                f"{len(dev)} measure(s) differ by more than 20%" if dev else "length, figures, tables and "
                                "references within 20% of the example", dev))

    report = {"tex": tex_rel, "checked_at": now(), "ready": not any(c["status"] == "fail" for c in checks),
              "counts": {s: sum(c["status"] == s for c in checks) for s in ("pass", "warn", "fail", "info")},
              "checks": checks, "profile": profile, "example": example,
              "targets": {"pages": target_pages, "refs": target_refs, "example_pdf": example_pdf},
              "note": "Automated checks only. Passing them does not certify scientific validity or acceptance."}
    if write:
        out = root / "quality" / f"{Path(tex_rel).stem}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load(root: Path, tex_rel: str) -> dict | None:
    p = root / "quality" / f"{Path(tex_rel).stem}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
