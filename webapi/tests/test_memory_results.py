"""Research Memory, Analyze tools and Results endpoint."""
import time

from webapi.tests.test_api import H, client


def _project():
    return client.post("/api/v1/projects", json={"title": "Memory project"}, headers=H).json()


def _wait(run_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] in {"succeeded", "failed", "cancelled"}:
            return r
        time.sleep(0.2)
    raise AssertionError("run did not finish")


def test_memory_edit_and_run_log_append():
    p = _project()
    m = client.get(f"/api/v1/projects/{p['id']}/memory").json()
    assert m["exists"] is False and "Research question" in m["text"]
    put = client.put(f"/api/v1/projects/{p['id']}/memory", json={"text": "# Research memory\n\nQ: does X work?\n"},
                     headers=H)
    assert put.status_code == 200 and put.json()["exists"]
    c = client.post(f"/api/v1/projects/{p['id']}/conversations", json={}, headers=H).json()
    run = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "Draft"}, headers=H).json()
    _wait(run["id"])
    text = client.get(f"/api/v1/projects/{p['id']}/memory").json()["text"]
    assert "Q: does X work?" in text and run["id"] in text and "manuscript/main.md" in text
    # The memory file is not reported as a run artifact.
    paths = [a["path"] for a in client.get(f"/api/v1/runs/{run['id']}").json()["artifacts"]]
    assert "memory/research_memory.md" not in paths


def test_memory_put_requires_client_header():
    p = _project()
    assert client.put(f"/api/v1/projects/{p['id']}/memory", json={"text": "x"}).status_code == 403


def test_analyze_tools_exist_and_code_generation_prompt():
    ids = {w["id"] for w in client.get("/api/v1/workflows", params={"section": "analyze"}).json()}
    assert {"code_generation", "data_analysis", "experiments_s4"} <= ids
    p = _project()
    r = client.post(f"/api/v1/projects/{p['id']}/workflows/code_generation",
                    json={"values": {"task": "Train a baseline"}}, headers=H).json()
    run = _wait(r["run_id"])
    assert run["status"] == "succeeded"
    prompt = client.get(f"/api/v1/conversations/{r['conversation_id']}").json()["runs"][0]["prompt"]
    assert "code/README.md" in prompt and "do not claim it ran" in prompt


def test_results_lists_result_files_only():
    p = _project()
    client.post(f"/api/v1/projects/{p['id']}/files", headers=H, params={"folder": "results"},
                files={"file": ("metrics.csv", b"a,b\n1,2\n", "text/csv")})
    client.post(f"/api/v1/projects/{p['id']}/files", headers=H,
                files={"file": ("notes.md", b"# n\n", "text/markdown")})
    res = client.get(f"/api/v1/projects/{p['id']}/results").json()
    assert [f["path"] for f in res["files"]] == ["results/metrics.csv"] and res["measured"] is None
