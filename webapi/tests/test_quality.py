"""Submission gate: placeholders, citations, numbers traced to results, figures, page budget, example-paper match."""
import io
import json

from webapi.app import quality

TEX = r"""\documentclass{article}
\begin{document}
\begin{abstract}We reach 81.2\% accuracy, significantly better than 77.4.\end{abstract}
This is the first novel method \cite{a,b,zz}. Value \PFVAL{x}.
\begin{table}\begin{tabular}{ll}Ours & 0.812 \\ Base & 0.774 \\ Other & 0.700 \\\end{tabular}\end{table}
\includegraphics[width=0.5\linewidth]{fig/plot}
\includegraphics{fig/missing}
\bibliography{refs}
\end{document}
"""
BIB = "@article{a, title={Paper A}, doi={10.1/a}}\n@article{b, title={Paper B}}\n@article{c, title={Paper C}}\n"


def _ws(tmp_path):
    (tmp_path / "paper" / "fig").mkdir(parents=True)
    (tmp_path / "paper" / "main.tex").write_text(TEX, encoding="utf-8")
    (tmp_path / "paper" / "refs.bib").write_text(BIB, encoding="utf-8")
    from PIL import Image
    Image.new("RGB", (600, 400), "white").save(tmp_path / "paper" / "fig" / "plot.png")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "r.json").write_text(json.dumps({"ours": 0.8123, "base": {"acc": 0.7741}}), encoding="utf-8")
    return tmp_path


def test_gate_checks(tmp_path):
    root = _ws(tmp_path)
    r = quality.gate(root, "paper/main.tex", target_pages=10, target_refs=4)
    by = {c["id"]: c for c in r["checks"]}
    assert not r["ready"]
    assert by["compile"]["status"] == "fail"
    assert by["placeholders"]["status"] == "fail" and by["placeholders"]["items"][0]["match"].startswith("\\PFVAL")
    assert by["bib"]["status"] == "fail" and by["bib"]["items"] == [{"match": "zz"}]
    assert by["refcount"]["status"] == "warn"                       # 3 cited, target 4 (>= 75%)
    assert by["numbers"]["status"] == "warn"
    assert set(quality.trace_numbers(TEX, root / "results")["untraced_set"]) == {"0.700"}
    assert by["figures"]["status"] == "fail" and "1 missing" in by["figures"]["detail"]
    assert by["claims"]["status"] == "warn"                         # 'significantly' with no test anywhere
    assert (root / "quality" / "main.json").is_file()


def test_numbers_traced_with_rounding_and_percent():
    vals = [0.8123, 77.41]
    assert quality.traced("81.2", vals) and quality.traced("0.81", vals) and quality.traced("77.4", vals)
    assert not quality.traced("79.9", vals)


def test_reference_lookup_flags_wrong_title(tmp_path):
    root = _ws(tmp_path)

    def fetch(url):
        return json.dumps({"message": {"title": ["Something else entirely"], "issued": {"date-parts": [[2024]]}}})
    r = quality.gate(root, "paper/main.tex", online=True, fetch=fetch, write=False)
    ref = next(c for c in r["checks"] if c["id"] == "refverify")
    assert ref["status"] == "fail" and "1 not found or wrong title" in ref["detail"]


def test_example_paper_profile(tmp_path):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(12):
        w.add_blank_page(width=600, height=800)
    buf = io.BytesIO()
    w.write(buf)
    root = _ws(tmp_path)
    (root / "example.pdf").write_bytes(buf.getvalue())
    r = quality.gate(root, "paper/main.tex", example_pdf="example.pdf", write=False)
    style = next(c for c in r["checks"] if c["id"] == "style")
    assert r["example"]["pages"] == 12 and style["status"] in {"pass", "warn"}
