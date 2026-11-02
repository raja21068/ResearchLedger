"""Reference checking: offline, with a fake fetch; network failure degrades to not_checked."""
import json
import urllib.error
from pathlib import Path

from webapi.app import refcheck

BIB = """@article{good,
  title = {Attention Is All You Need},
  doi = {10.1000/good}
}
@misc{ax,
  title = {Some arXiv Paper},
  author = {A. Author},
  eprint = {2401.01234},
  year = {2024}
}
@article{wrong,
  title = {Completely different title about cats},
  doi = {10.1000/other}
}
@article{missing,
  title = {Ghost Paper},
  doi = {10.1000/ghost}
}
@book{noid, title = {No identifier here}}
"""

ARXIV = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Some arXiv Paper</title>
<published>2024-01-03T00:00:00Z</published><author><name>A. Author</name></author></entry></feed>"""


def fake(url):
    if "10.1000/good" in url:
        return json.dumps({"message": {"title": ["Attention is all you need"], "issued": {"date-parts": [[2017]]},
                                       "author": [{"family": "Vaswani", "given": "A."}], "container-title": ["NeurIPS"]}})
    if "10.1000/other" in url:
        return json.dumps({"message": {"title": ["Dogs"], "issued": {"date-parts": [[1999]]}}})
    if "10.1000/ghost" in url:
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)
    if "arxiv" in url:
        return ARXIV
    raise AssertionError(url)


def _root(tmp_path, text=BIB):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "refs.bib").write_text(text, encoding="utf-8")
    return tmp_path


def test_parse_bib():
    es = refcheck.parse_bib(BIB)
    assert [e["key"] for e in es] == ["good", "ax", "wrong", "missing", "noid"]
    assert es[1]["fields"]["eprint"] == "2401.01234"


def test_check_statuses_and_fill_missing_fields_only(tmp_path):
    root = _root(tmp_path)
    rep = refcheck.check_file(root, fake)
    st = {e["key"]: e for e in rep["entries"]}
    assert st["good"]["status"] == "verified" and st["good"]["filled"] == {
        "author": "Vaswani, A.", "year": "2017", "journal": "NeurIPS"}
    assert st["ax"]["status"] == "verified" and st["ax"]["filled"] == {"journal": "arXiv"}  # author/year kept
    assert st["wrong"]["status"] == "title_mismatch" and st["wrong"]["filled"] == {}
    assert st["missing"]["status"] == "not_found"
    assert st["noid"]["status"] == "no_identifier"
    new = (root / "paper" / "refs.bib").read_text(encoding="utf-8")
    assert "Vaswani" in new and "Dogs" not in new
    assert (root / "paper" / "refs.bib.orig").read_text(encoding="utf-8") == BIB  # original kept
    assert [e["key"] for e in refcheck.parse_bib(new)] == ["good", "ax", "wrong", "missing", "noid"]
    assert refcheck.load_report(root)["counts"]["verified"] == 2


def test_network_failure_is_not_checked_and_bib_untouched(tmp_path):
    def down(url):
        raise OSError("no network")
    root = _root(tmp_path)
    rep = refcheck.check_file(root, down)
    st = {e["key"]: e["status"] for e in rep["entries"]}
    assert st["good"] == "not_checked" and st["ax"] == "not_checked" and st["noid"] == "no_identifier"
    assert (root / "paper" / "refs.bib").read_text(encoding="utf-8") == BIB


def test_api_endpoints(monkeypatch):
    from webapi.tests.test_api import H, client
    import os
    p = client.post("/api/v1/projects", json={"title": "refs"}, headers=H).json()
    assert client.post(f"/api/v1/projects/{p['id']}/paper/check-references", headers=H).status_code == 400
    ws = Path(os.environ["RL_WEB_DATA"]) / "projects" / p["id"] / "workspace"
    _root(ws)
    monkeypatch.setattr(refcheck, "fetcher", lambda: fake)
    r = client.post(f"/api/v1/projects/{p['id']}/paper/check-references", headers=H).json()
    assert r["total"] == 5
    assert client.get(f"/api/v1/projects/{p['id']}/paper/references").json()["total"] == 5
