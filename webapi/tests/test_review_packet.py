"""Independent review packet: export contains what an outside reviewer needs; import accepts a table, JSON or CSV,
keeps only concerns whose quote is really in the manuscript as VERIFIED, and the result works with the existing
reviewer-finding memory."""
import csv
import json
import zipfile

from webapi.app import memory_store, review_packet, workspace
from webapi.app.main import store
from webapi.tests.test_api import H, client
from webapi.tests.test_lab import _run_paper_experiment

TEX = r"""\documentclass{article}
\begin{document}
\begin{abstract}Our method reaches 7.0 accuracy.\end{abstract}
\section{Method}We compare against baseline B1 only. The split is random.
\begin{table}\begin{tabular}{ll} Ours & 7.0 \\ Other & 42.5 \end{tabular}\end{table}
\end{document}
"""

REPLY_TABLE = """Here is my review.

| id | severity | location | concern | quote | minimum_fix |
|---|---|---|---|---|---|
| R1 | Major | Method | Only one baseline is used, so the comparison is weak. | We compare against baseline B1 only. | Add at least one stronger baseline. |
| R2 | Minor | Method | A random split can leak near-duplicates. | The split is random. | Use a scaffold split. |
| R3 | Major | Results | The gain is statistically meaningless. | The gain is statistically meaningless across all seeds. | Report confidence intervals. |
"""


def _setup():
    pid, root, rid = _run_paper_experiment()
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "main.tex").write_text(TEX, encoding="utf-8")
    return pid, root


def test_packet_contains_manuscript_evidence_summary_prompt_and_output_contract():
    pid, root = _setup()
    r = client.post(f"/api/v1/projects/{pid}/review/packet", json={"path": "paper/main.tex"}, headers=H)
    assert r.status_code == 201, r.text
    p = r.json()
    with zipfile.ZipFile(root / p["zip"]) as z:
        names = set(z.namelist())
        assert {"REVIEW_PROMPT.md", "evidence_summary.md", "manuscript.tex", "README.txt"} <= names
        prompt = z.read("REVIEW_PROMPT.md").decode("utf-8")
        summary = z.read("evidence_summary.md").decode("utf-8")
    assert "| id | severity | location | concern | quote | minimum_fix |" in prompt and "EXACTLY" in prompt
    assert "Referee Lean v2" in prompt                       # the user's own reviewer discipline is included
    assert "matching no measured result: 1" in summary and "`42.5`" in summary
    assert "Nothing in this folder was sent anywhere" in (root / p["folder"] / "README.txt").read_text(encoding="utf-8")
    assert client.get(f"/api/v1/projects/{pid}/review/external").json()["packets"][0]["name"] == "packet_1"
    p2 = client.post(f"/api/v1/projects/{pid}/review/packet", json={"path": "paper/main.tex"}, headers=H).json()
    assert p2["packet"] == "packet_2"


def test_import_keeps_only_concerns_whose_quote_is_in_the_manuscript():
    pid, root = _setup()
    r = client.post(f"/api/v1/projects/{pid}/review/import", headers=H,
                    json={"path": "paper/main.tex", "text": REPLY_TABLE, "source": "ChatGPT (temporary chat)"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["total"], d["verified"], d["unverified"], d["verified_major"]) == (3, 2, 1, 1)
    by = {c["id"]: c for c in d["concerns"]}
    assert by["R1"]["verification"] == "VERIFIED" and by["R3"]["verification"] == "UNVERIFIED"
    rows = list(csv.DictReader((root / d["file"]).open(encoding="utf-8", newline="")))
    assert rows[0]["reviewer"] == "ChatGPT (temporary chat)" and rows[0]["severity"] == "Major"
    assert "R3" not in d["feedback_for_revise"] and "R1" in d["feedback_for_revise"] and "R2" in d["feedback_for_revise"]
    assert (root / d["folder"] / "raw_reply.md").read_text(encoding="utf-8") == REPLY_TABLE  # the original is kept


def test_json_csv_and_curly_quotes_are_accepted_and_garbage_is_refused_in_plain_words():
    pid, root = _setup()
    js = json.dumps({"concerns": [{"id": "A1", "severity": "critical", "concern": "Weak baseline.",
                                   "quote": "We compare against baseline B1 only.", "minimum_fix": "Add baselines."}]})
    d = client.post(f"/api/v1/projects/{pid}/review/import", headers=H, json={"path": "paper/main.tex", "text": js}).json()
    assert d["verified"] == 1 and d["concerns"][0]["severity"] == "Major" and d["folder"].endswith("external_1")
    cs = 'id,severity,concern,quote,minimum_fix\nC1,Low,"Random split.","The split is “random”.",Scaffold split\n'
    d2 = client.post(f"/api/v1/projects/{pid}/review/import", headers=H, json={"path": "paper/main.tex", "text": cs}).json()
    assert d2["concerns"][0]["severity"] == "Minor" and d2["folder"].endswith("external_2")
    bad = client.post(f"/api/v1/projects/{pid}/review/import", headers=H, json={"path": "paper/main.tex", "text": "Looks great!"})
    assert bad.status_code == 400 and "table of concerns" in bad.text
    notex = client.post(f"/api/v1/projects/{pid}/review/packet", json={"path": "code/jobs.json"}, headers=H)
    assert notex.status_code == 400 and ".tex" in notex.text


def test_parse_reply_handles_escaped_pipes_and_missing_columns():
    rows = review_packet.parse_reply("| id | concern | quote |\n|---|---|---|\n| R1 | Uses a | b test | exact words |\n")
    assert rows == [] or rows[0]["id"] == "R1"
    rows = review_packet.parse_reply("| id | concern | quote |\n|---|---|---|\n| R1 | Pipe a \\| b | exact words |\n")
    assert rows[0]["concern"] == "Pipe a | b" and rows[0]["quote"] == "exact words"
