"""Manuscript trace: numbers in tables and the abstract are matched to measured results, runs and ledger evidence;
backing depends on the user's review; invented numbers and placeholders are surfaced."""
from webapi.tests.test_api import H, client
from webapi.tests.test_lab import _run_paper_experiment

TEX = r"""\documentclass{article}
\begin{document}
\begin{abstract}
Our method reaches 7.0 accuracy, and a second figure of 42.5 percent.
\end{abstract}
\section{Results}
\begin{table}\begin{tabular}{ll} Method & Acc \\ Ours & 7.0 \\ Baseline & TBD \\ Other & 13.37 \end{tabular}\end{table}
Pending: [RESULT: runtime]. See \cite{a,b}.
\end{document}
"""


def _trace(pid, path="paper/main.tex"):
    return client.get(f"/api/v1/projects/{pid}/manuscript/trace", params={"path": path}).json()


def _write(root):
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "main.tex").write_text(TEX, encoding="utf-8")


def test_numbers_are_traced_to_slot_run_and_evidence_and_backing_follows_review():
    pid, root, rid = _run_paper_experiment()          # acc_main = 7
    _write(root)
    t = _trace(pid)
    by = {n["value"]: n for n in t["numbers"]}
    seven = by["7.0"]
    assert seven["slot"] == "acc_main" and seven["file"] == "results/acc_main.json" and seven["run"] == rid
    assert seven["evidence"]["status"] == "observed" and seven["backing"] == "recorded"
    assert by["42.5"]["backing"] == "untraced" and by["13.37"]["backing"] == "untraced"
    assert t["counts"]["untraced"] == 2 and any("match no measured result" in n and "thresholds" in n for n in t["notes"])
    assert any("None of the reported numbers is backed" in n for n in t["notes"])
    # the user reviews the evidence: the same number is now backed
    eid = seven["evidence"]["id"]
    assert client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H,
                       json={"status": "checked", "reason": "Read the log and the script."}).status_code == 200
    t2 = _trace(pid)
    assert next(n for n in t2["numbers"] if n["value"] == "7.0")["backing"] == "backed"
    assert t2["counts"]["backed"] >= 1 and not any("None of the reported" in n for n in t2["notes"])


def test_placeholders_sources_and_unused_results_are_listed():
    pid, root, rid = _run_paper_experiment()
    _write(root)
    (root / "results" / "acc_other.json").write_text('{"slot_id": "acc_other", "value": 3.5}', encoding="utf-8")
    t = _trace(pid)
    texts = " ".join(p["text"] for p in t["placeholders"])
    assert "TBD" in texts and "[RESULT: runtime]" in texts
    assert t["sources"] == 2 and "Results" in t["sections"] and t["tables"] == 1
    assert "acc_other" in t["unused_slots"] and "acc_main" not in t["unused_slots"]
    row = next(r for r in t["slots"] if r["slot"] == "acc_other")
    assert row["evidence"] is None and row["used"] is False


def test_a_result_file_without_a_recorded_run_is_only_measured():
    pid, root, rid = _run_paper_experiment()
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "main.tex").write_text(TEX.replace("13.37", "3.5"), encoding="utf-8")
    (root / "results" / "acc_other.json").write_text('{"slot_id": "acc_other", "value": 3.5}', encoding="utf-8")
    n = next(x for x in _trace(pid)["numbers"] if x["value"] == "3.5")
    assert n["slot"] == "acc_other" and n["backing"] == "measured" and n["evidence"] is None


def test_only_tex_files_inside_the_project_are_traced():
    pid, root, rid = _run_paper_experiment()
    r = client.get(f"/api/v1/projects/{pid}/manuscript/trace", params={"path": "code/jobs.json"})
    assert r.status_code == 400 and ".tex" in r.text
    assert client.get(f"/api/v1/projects/{pid}/manuscript/trace", params={"path": "../x.tex"}).status_code in {400, 404}
