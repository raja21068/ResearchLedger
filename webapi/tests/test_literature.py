"""Literature library: identity, duplicates, four separate verification levels, offline adapters, agent-readable file."""
import json
import urllib.error

from webapi.app import literature, refcheck, workspace
from webapi.app.main import store
from webapi.tests.test_api import H, client

OPENALEX = json.dumps({"results": [
    {"id": "https://openalex.org/W1", "title": "Sort and Slice: a better folding", "publication_year": 2024,
     "doi": "https://doi.org/10.1186/S13321-024-00001-0", "authorships": [{"author": {"display_name": "Dablander, M."}}],
     "primary_location": {"landing_page_url": "https://arxiv.org/abs/2403.17954", "source": {"display_name": "J Cheminform"}},
     "open_access": {"oa_url": "https://arxiv.org/pdf/2403.17954"}, "abstract_inverted_index": {"Frequent": [0], "bits": [1]}}]})


def _proj():
    return client.post("/api/v1/projects", json={"title": "Lib"}, headers=H).json()["id"]


def _paper(pid, **kw):
    body = {"title": "A paper", "authors": ["Ng, A."], "year": 2020, **kw}
    return client.post(f"/api/v1/projects/{pid}/library", json=body, headers=H).json()


def test_duplicates_merge_only_on_identity_never_on_similar_titles():
    pid = _proj()
    a = _paper(pid, title="Hash Collisions in Fingerprints", doi="https://doi.org/10.1000/ABC")
    b = _paper(pid, title="Totally different wording", doi="10.1000/abc", venue="J X")       # same DOI -> same paper
    assert b["id"] == a["id"] and b["created"] is False and b["venue"] == "J X" and len(b["sources"]) == 1
    c = _paper(pid, title="Hash Collisions in Fingerprints.", doi="10.9999/other")           # same title, different DOI
    assert c["id"] != a["id"]
    d = _paper(pid, title="Hash collisions in fingerprints", authors=["Zed, Q."], arxiv_id="2511.17078v2")         # similar, no shared id/author-year
    e = _paper(pid, title="Hash collisions in fingerprint", authors=["Zed, Q."], arxiv_id="2511.99999")            # NEAR title: must stay separate
    assert d["id"] not in {a["id"], c["id"]} and e["id"] != d["id"]
    f = _paper(pid, arxiv_id="2511.17078", title="Hash Collisions!!")                         # same arXiv id (version dropped)
    assert f["id"] == d["id"]
    assert len(client.get(f"/api/v1/projects/{pid}/library").json()["papers"]) == 4


def test_title_author_year_is_a_duplicate_and_fills_in_the_missing_identifier():
    pid = _proj()
    a = _paper(pid, title="Spectrum Dependent Learning Curves", authors=["Bordelon, B."], year=2020)
    b = _paper(pid, title="Spectrum dependent learning curves", authors=["Bordelon, Blake"], year=2020, arxiv_id="2002.02561")
    assert b["id"] == a["id"] and b["arxiv_id"] == "2002.02561"


def test_search_adapters_parse_offline_and_flag_papers_already_in_the_library(monkeypatch):
    pid = _proj()
    monkeypatch.setattr(refcheck, "fetcher", lambda: lambda url: OPENALEX)
    hits = client.post(f"/api/v1/projects/{pid}/library/search", json={"source": "openalex", "query": "fingerprint folding"}, headers=H).json()["hits"]
    assert hits[0]["arxiv_id"] == "2403.17954" and hits[0]["doi"].endswith("S13321-024-00001-0") and hits[0]["abstract"] == "Frequent bits"
    assert hits[0]["in_library"] is None
    client.post(f"/api/v1/projects/{pid}/library/import", json={"papers": hits, "source": "openalex"}, headers=H)
    again = client.post(f"/api/v1/projects/{pid}/library/search", json={"source": "openalex", "query": "fingerprint folding"}, headers=H).json()["hits"]
    assert again[0]["in_library"]                                      # already known: a search round will not re-add it
    assert client.post(f"/api/v1/projects/{pid}/library/search", json={"source": "semanticscholar", "query": "x y z"}, headers=H).status_code == 400


def test_verification_levels_are_separate_and_a_wrong_title_is_not_a_match(monkeypatch):
    pid = _proj()
    good = _paper(pid, title="Sort and Slice", doi="10.1000/good", year=2024)
    wrong = _paper(pid, title="Quantum chromodynamics lecture notes", doi="10.1000/wrong", year=2024)
    ghost = _paper(pid, title="Does not exist anywhere", doi="10.1000/ghost")

    def fetch(url):
        if "10.1000%2Fghost" in url or "10.1000/ghost" in url:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        if "10.1000/wrong" in url:
            return json.dumps({"message": {"title": ["Sort and Slice"], "issued": {"date-parts": [[2024]]}, "container-title": ["J"]}})
        return json.dumps({"message": {"title": ["Sort and Slice"], "issued": {"date-parts": [[2024]]}, "container-title": ["J"]}})
    monkeypatch.setattr(refcheck, "fetcher", lambda: fetch)
    g = client.post(f"/api/v1/projects/{pid}/library/{good['id']}/verify", headers=H).json()
    w = client.post(f"/api/v1/projects/{pid}/library/{wrong['id']}/verify", headers=H).json()
    x = client.post(f"/api/v1/projects/{pid}/library/{ghost['id']}/verify", headers=H).json()
    assert (g["exists_level"], g["metadata_level"]) == ("yes", "yes")
    assert (w["exists_level"], w["metadata_level"]) == ("yes", "no")      # the DOI exists, but it is a different paper
    assert x["exists_level"] == "no"
    assert g["supports_level"] == w["supports_level"] == "unreviewed"      # no machine check ever sets this


def test_an_unreachable_registry_is_unknown_not_false(monkeypatch):
    pid = _proj()
    p = _paper(pid, title="Some paper", doi="10.1000/q")

    def down(url):
        raise TimeoutError("offline")
    monkeypatch.setattr(refcheck, "fetcher", lambda: down)
    r = client.post(f"/api/v1/projects/{pid}/library/{p['id']}/verify", headers=H).json()
    assert r["exists_level"] == "unchecked" and "unreachable" in r["check_note"]


def test_only_a_person_can_mark_a_paper_as_supporting_a_statement_and_needs_a_reason():
    pid = _proj()
    p = _paper(pid, title="Some paper", doi="10.1000/q2")
    bad = client.post(f"/api/v1/projects/{pid}/library/{p['id']}/supports", json={"level": "supported", "note": "ok"}, headers=H)
    assert bad.status_code == 400
    ok = client.post(f"/api/v1/projects/{pid}/library/{p['id']}/supports", headers=H,
                     json={"level": "supported", "note": "Section 4 reports the same exponent for tree models."}).json()
    assert ok["supports_level"] == "supported" and ok["supports_at"]


def test_import_from_competitors_csv_and_bib_then_the_agent_file_lists_levels():
    pid = _proj()
    root = workspace.project_root(pid)
    (root / "loops").mkdir()
    (root / "loops" / "competitors.csv").write_text(
        "id,title,year,venue,doi,arxiv,url\nc1,Sort & Slice,2024,J Cheminform,,2403.17954,https://arxiv.org/abs/2403.17954\n"
        "c2,Hash Collisions,2025,arXiv,,2511.17078,\nc3,,2025,,,,\n", encoding="utf-8")
    (root / "refs.bib").write_text("@article{ss, title={Sort and Slice}, author={Dablander, M.}, year={2024}, eprint={2403.17954}}\n"
                                   "@article{new, title={Brand New}, author={Lee, K.}, year={2023}, doi={10.5555/new}}\n", encoding="utf-8")
    r1 = client.post(f"/api/v1/projects/{pid}/library/import", json={"path": "loops/competitors.csv"}, headers=H).json()
    r2 = client.post(f"/api/v1/projects/{pid}/library/import", json={"path": "refs.bib"}, headers=H).json()
    assert r1 == {"created": 2, "merged": 0, "skipped": 1} and r2 == {"created": 1, "merged": 1, "skipped": 0}
    text = (root / "literature" / "library.md").read_text(encoding="utf-8")
    assert "Sort &amp; Slice" not in text and "arXiv:2403.17954" in text and "exists: unchecked" in text and "supported: not reviewed" in text
    assert client.post(f"/api/v1/projects/{pid}/library/import", json={"path": "../x.csv"}, headers=H).status_code == 400


def test_a_projects_library_is_not_visible_from_another_project():
    a, b = _proj(), _proj()
    p = _paper(a, title="Private paper", doi="10.1000/p")
    assert client.get(f"/api/v1/projects/{b}/library").json()["papers"] == []
    assert client.post(f"/api/v1/projects/{b}/library/{p['id']}/supports", headers=H,
                       json={"level": "supported", "note": "Read it properly today."}).status_code == 400
