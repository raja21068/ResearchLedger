"""Step 1B — programmatic source/reference verification for ingested papers.

Uses Semantic Scholar and Crossref when identifiers/metadata are available. The
stage is deliberately conservative: network failure produces UNVERIFIED, never
VERIFIED. It does not fabricate venue-quality metrics.
"""
from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import load_config, load_json, save_json, save_markdown, log, print_banner

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def _norm_title(title: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower()).split())


def title_similarity(a: str, b: str) -> float:
    a, b = _norm_title(a), _norm_title(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _get(url: str, *, params=None, timeout=15):
    import requests
    headers = {"User-Agent": "IdeaDiscoveryV5/5.0 (research metadata verification)"}
    return requests.get(url, params=params, headers=headers, timeout=timeout)


def semantic_scholar_lookup(paper: dict) -> dict:
    doi = (paper.get("doi") or "").strip()
    title = paper.get("title", "")
    year = paper.get("year")
    try:
        if doi and DOI_RE.match(doi):
            r = _get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                     params={"fields": "title,year,venue,authors,externalIds,url,paperId"})
            if r.status_code == 200:
                item = r.json()
                sim = title_similarity(title, item.get("title", ""))
                y = item.get("year")
                year_ok = not year or not y or abs(int(year) - int(y)) <= 1
                return {"found": True, "mode": "doi", "similarity": round(sim, 3), "year_ok": year_ok, "record": item}
            if r.status_code == 429:
                time.sleep(1.5)
        r = _get("https://api.semanticscholar.org/graph/v1/paper/search",
                 params={"query": title, "limit": 5, "fields": "title,year,venue,authors,externalIds,url,paperId"})
        if r.status_code != 200:
            return {"found": False, "error": f"HTTP {r.status_code}"}
        candidates = r.json().get("data", [])
        best = max(candidates, key=lambda x: title_similarity(title, x.get("title", "")), default=None)
        if not best:
            return {"found": False}
        sim = title_similarity(title, best.get("title", ""))
        y = best.get("year")
        year_ok = not year or not y or abs(int(year) - int(y)) <= 1
        return {"found": sim >= 0.70 and year_ok, "mode": "title", "similarity": round(sim, 3), "year_ok": year_ok, "record": best}
    except Exception as exc:
        return {"found": False, "error": str(exc)}


def crossref_lookup(doi: str, title: str) -> dict:
    doi = (doi or "").strip()
    if not doi or not DOI_RE.match(doi):
        return {"found": False, "reason": "no_valid_doi"}
    try:
        r = _get(f"https://api.crossref.org/works/{doi}")
        if r.status_code != 200:
            return {"found": False, "error": f"HTTP {r.status_code}"}
        msg = r.json().get("message", {})
        titles = msg.get("title") or []
        matched_title = titles[0] if titles else ""
        sim = title_similarity(title, matched_title)
        return {"found": True, "similarity": round(sim, 3), "record": {
            "title": matched_title,
            "publisher": msg.get("publisher"),
            "container_title": (msg.get("container-title") or [None])[0],
            "type": msg.get("type"),
            "URL": msg.get("URL"),
        }}
    except Exception as exc:
        return {"found": False, "error": str(exc)}


def domain_profile(corpus: dict, configured: str = "auto") -> str:
    if configured and configured != "auto":
        return configured
    cats = []
    for p in corpus.get("papers", []):
        method = p.get("method", {}) if isinstance(p.get("method"), dict) else {}
        cats.append(str(method.get("category", "")).lower())
    ai = {"transformer", "cnn", "rnn", "diffusion", "rl", "gnn", "benchmark", "hybrid"}
    if sum(c in ai for c in cats) >= max(1, len(cats) // 3):
        return "computer_science_ai"
    return "general"


def evidence_grade(paper: dict, profile: str) -> dict:
    """Domain-aware, non-fabricated evidence characterization from extracted metadata."""
    claims = paper.get("claims", []) if isinstance(paper.get("claims"), list) else []
    types = {c.get("evidence_type") for c in claims if isinstance(c, dict)}
    repro = paper.get("reproducibility", {}) if isinstance(paper.get("reproducibility"), dict) else {}
    if profile == "computer_science_ai":
        if "theoretical" in types:
            tier = "A/B: theoretical contribution; inspect proof assumptions"
        elif "ablation" in types and "empirical" in types:
            tier = "A/B: empirical + ablation evidence"
        elif "empirical" in types:
            tier = "B: empirical evidence"
        elif paper.get("method", {}).get("category") == "survey":
            tier = "B/C: synthesis evidence; quality depends on search protocol"
        else:
            tier = "C: evidence type unclear"
    else:
        tier = "B/C: domain-specific appraisal required"
    return {
        "profile": profile,
        "evidence_characterization": tier,
        "code_available": bool(repro.get("code_available")),
        "data_available": bool(repro.get("data_available")),
        "claim_evidence_types": sorted(x for x in types if x),
    }


def verify_paper(paper: dict, profile: str) -> dict:
    doi = paper.get("doi")
    doi_format_valid = bool(doi and DOI_RE.match(str(doi).strip())) if doi else None
    s2 = semantic_scholar_lookup(paper)
    cr = crossref_lookup(str(doi or ""), paper.get("title", ""))

    status = "UNVERIFIED"
    reasons = []
    if s2.get("found") and s2.get("similarity", 0) >= 0.70 and s2.get("year_ok", True):
        status = "S2_VERIFIED"
        reasons.append("Semantic Scholar metadata matched title/year")
    if cr.get("found"):
        if cr.get("similarity", 0) >= 0.70:
            if status == "UNVERIFIED":
                status = "VERIFIED"
            reasons.append("Crossref DOI metadata matched title")
        else:
            status = "DOI_MISMATCH"
            reasons.append("DOI resolves but title metadata does not match")
    elif doi and doi_format_valid is False:
        status = "INVALID_DOI"
        reasons.append("DOI format is invalid")

    if not s2.get("found") and not cr.get("found") and (s2.get("error") or cr.get("error")):
        reasons.append("External verification incomplete due to lookup failure")

    return {
        "paper_id": paper.get("paper_id"),
        "title": paper.get("title"),
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "doi": doi,
        "doi_format_valid": doi_format_valid,
        "verification_status": status,
        "reasons": reasons,
        "semantic_scholar": s2,
        "crossref": cr,
        "evidence_grade": evidence_grade(paper, profile),
    }


def report_markdown(report: dict) -> str:
    lines = ["# Source Verification Report (V5)\n", f"Generated: {report['generated']}\n"]
    s = report["summary"]
    lines += ["## Summary\n", f"- Domain profile: **{report['domain_profile']}**", f"- Papers checked: {s['total']}",
              f"- S2 verified: {s.get('S2_VERIFIED', 0)}", f"- Crossref verified: {s.get('VERIFIED', 0)}",
              f"- Unverified: {s.get('UNVERIFIED', 0)}", f"- DOI mismatches/invalid: {s.get('DOI_MISMATCH', 0) + s.get('INVALID_DOI', 0)}\n"]
    lines.append("## Audit\n")
    lines.append("| Paper | Status | DOI | S2 title match | Evidence characterization |")
    lines.append("|---|---|---|---:|---|")
    for x in report["papers"]:
        lines.append(f"| {x.get('paper_id','')} | {x['verification_status']} | {x.get('doi') or '—'} | {x.get('semantic_scholar',{}).get('similarity','—')} | {x['evidence_grade']['evidence_characterization']} |")
    lines.append("\n> UNVERIFIED means the system could not programmatically confirm the record; it does not mean the paper is fabricated. DOI_MISMATCH requires manual review before relying on the citation.\n")
    return "\n".join(lines)


def run_source_verification(config: dict) -> dict:
    print_banner("STEP 1B: Source Verification")
    out = config["pipeline"]["output_dir"]
    corpus = load_json(f"{out}/paper_corpus.json")
    cfg = config.get("source_verification", {})
    if not cfg.get("enabled", True):
        result = {"generated": datetime.now().isoformat(), "status": "disabled", "papers": [], "summary": {"total": 0}}
        save_json(result, f"{out}/source_verification.json")
        return result
    profile = domain_profile(corpus, cfg.get("domain_profile", "auto"))
    results = []
    for i, paper in enumerate([p for p in corpus.get("papers", []) if "_error" not in p], 1):
        log.info(f"[{i}] Verifying source: {paper.get('paper_id', '?')}")
        results.append(verify_paper(paper, profile))
        if cfg.get("request_delay_seconds", 0):
            time.sleep(float(cfg["request_delay_seconds"]))
    summary = {"total": len(results)}
    for r in results:
        summary[r["verification_status"]] = summary.get(r["verification_status"], 0) + 1
    report = {"generated": datetime.now().isoformat(), "domain_profile": profile, "papers": results, "summary": summary}
    save_json(report, f"{out}/source_verification.json")
    save_markdown(report_markdown(report), f"{out}/source_verification.md")
    return report


if __name__ == "__main__":
    run_source_verification(load_config())
