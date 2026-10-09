import sys

from researchledger.hashing import sha256_file
from researchledger.runner import run_command
from researchledger.workspace import init_workspace


def test_run_records_manifest(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "print('hello world')"])

    assert manifest["status"] == "completed"
    assert manifest["exit_code"] == 0
    assert manifest["run_id"] == "R0001"

    run_dir = ws.runs_dir / manifest["run_id"]
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "command.txt").exists()
    assert "hello world" in (run_dir / "stdout.log").read_text(encoding="utf-8")


def test_run_captures_and_hashes_artifacts(tmp_path):
    ws = init_workspace(tmp_path)
    script = (
        "import os, pathlib\n"
        "p = pathlib.Path(os.environ['RESEARCHLEDGER_ARTIFACTS_DIR']) / 'result.txt'\n"
        "p.write_text('42')\n"
    )
    manifest = run_command(ws, [sys.executable, "-c", script])

    assert manifest["status"] == "completed"
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["path"] == "artifacts/result.txt"

    run_dir = ws.runs_dir / manifest["run_id"]
    artifact_path = run_dir / manifest["artifacts"][0]["path"]
    assert sha256_file(artifact_path) == manifest["artifacts"][0]["sha256"]


def test_run_ids_increment(tmp_path):
    ws = init_workspace(tmp_path)
    first = run_command(ws, [sys.executable, "-c", "pass"])
    second = run_command(ws, [sys.executable, "-c", "pass"])
    assert first["run_id"] == "R0001"
    assert second["run_id"] == "R0002"


def test_run_records_seed_and_targets(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(
        ws, [sys.executable, "-c", "pass"], seed=42, claims=["C001", "C002"], plan="baseline-eval"
    )
    assert manifest["randomness"]["seed"] == 42
    assert manifest["targets"]["claims"] == ["C001", "C002"]
    assert manifest["targets"]["plan"] == "baseline-eval"


def test_run_retries_on_failure(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "import sys; sys.exit(1)"], retries=2)
    assert manifest["status"] == "failed"
    assert len(manifest["attempts"]) == 3
    assert all(a["exit_code"] == 1 for a in manifest["attempts"])


def test_run_stops_retrying_once_successful(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"], retries=5)
    assert manifest["status"] == "completed"
    assert len(manifest["attempts"]) == 1


def test_run_timeout(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
    assert manifest["status"] == "timeout"
    assert manifest["attempts"][-1]["timed_out"] is True


def test_run_records_environment_digest_and_hardware(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"])
    assert manifest["environment_digest"].startswith("sha256:")
    assert len(manifest["environment_digest"]) == len("sha256:") + 64
    assert "cpu_count" in manifest["hardware"]


def test_run_env_allowlist_captures_only_named_vars(tmp_path, monkeypatch):
    ws = init_workspace(tmp_path)
    monkeypatch.setenv("RL_TEST_ALLOWED", "visible")
    monkeypatch.setenv("RL_TEST_SECRET", "should-not-appear")
    manifest = run_command(ws, [sys.executable, "-c", "pass"], env_allowlist=["RL_TEST_ALLOWED"])
    assert manifest["env_vars"] == {"RL_TEST_ALLOWED": "visible"}


def test_run_direct_metrics_json_is_picked_up(tmp_path):
    ws = init_workspace(tmp_path)
    script = (
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': 0.91}))\n"
    )
    manifest = run_command(ws, [sys.executable, "-c", script])
    assert manifest["metrics"] == "metrics.json"


def test_first_run_has_no_previous_hash(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"])
    assert manifest["previous_run_hash"] is None


def test_second_run_chains_to_the_first(tmp_path):
    ws = init_workspace(tmp_path)
    first = run_command(ws, [sys.executable, "-c", "pass"])
    second = run_command(ws, [sys.executable, "-c", "pass"])

    first_manifest_path = ws.runs_dir / first["run_id"] / "manifest.json"
    assert second["previous_run_hash"] == "sha256:" + sha256_file(first_manifest_path)


def test_data_flag_hashes_a_single_file(tmp_path):
    ws = init_workspace(tmp_path)
    dataset = tmp_path / "data.csv"
    dataset.write_text("a,b\n1,2\n", encoding="utf-8")

    manifest = run_command(ws, [sys.executable, "-c", "pass"], data=[str(dataset)])

    assert manifest["inputs"] == [{"path": str(dataset), "sha256": sha256_file(dataset)}]


def test_data_flag_hashes_a_directory_order_independently(tmp_path):
    from researchledger.hashing import sha256_path

    ws = init_workspace(tmp_path)
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "a.txt").write_text("a", encoding="utf-8")
    (dataset_dir / "b.txt").write_text("b", encoding="utf-8")

    manifest = run_command(ws, [sys.executable, "-c", "pass"], data=[str(dataset_dir)])
    assert manifest["inputs"][0]["sha256"] == sha256_path(dataset_dir)


def test_data_flag_rejects_a_missing_path_before_allocating_a_run(tmp_path):
    ws = init_workspace(tmp_path)
    try:
        run_command(ws, [sys.executable, "-c", "pass"], data=[str(tmp_path / "nope.csv")])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert not any(ws.runs_dir.iterdir())  # no run id was burned on the failed validation


def test_concurrent_runs_never_collide_on_run_id(tmp_path):
    import concurrent.futures

    ws = init_workspace(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        manifests = list(pool.map(lambda _: run_command(ws, [sys.executable, "-c", "pass"]), range(5)))
    run_ids = [m["run_id"] for m in manifests]
    assert len(run_ids) == len(set(run_ids)) == 5


def test_concurrent_runs_produce_a_valid_chain(tmp_path):
    """Regression test for a confirmed bug: computing previous_run_hash
    right after id allocation (before execution) let concurrent runs read
    each other's not-yet-written manifests, producing a chain that
    validate() then reported as tampered even though nothing was. Sealing
    (computing previous_run_hash + writing manifest.json) must happen
    entirely under the lock, after execution, not before it."""
    import concurrent.futures

    from researchledger.validator import validate

    ws = init_workspace(tmp_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        manifests = list(pool.map(lambda _: run_command(ws, [sys.executable, "-c", "pass"]), range(8)))
    assert len({m["run_id"] for m in manifests}) == 8

    result = validate(ws)
    assert result.errors == []
    assert result.metrics["chain_integrity"] == 100.0


def test_run_records_metrics_sha256(tmp_path):
    ws = init_workspace(tmp_path)
    script = (
        "import os, json, pathlib\n"
        "run_dir = pathlib.Path(os.environ['RESEARCHLEDGER_RUN_DIR'])\n"
        "(run_dir / 'metrics.json').write_text(json.dumps({'accuracy': 0.9}))\n"
    )
    manifest = run_command(ws, [sys.executable, "-c", script])
    metrics_path = ws.runs_dir / manifest["run_id"] / manifest["metrics"]
    assert manifest["metrics_sha256"] == sha256_file(metrics_path)


def test_run_without_metrics_records_null_metrics_sha256(tmp_path):
    ws = init_workspace(tmp_path)
    manifest = run_command(ws, [sys.executable, "-c", "pass"])
    assert manifest["metrics"] is None
    assert manifest["metrics_sha256"] is None


def test_seal_reconstructs_deterministically_around_a_preexisting_branch(tmp_path):
    """If two runs already (illegitimately) claim the same predecessor —
    e.g. left behind by a crash under an older design — sealing a new run
    must still succeed, picking one tail deterministically rather than
    raising. `validate` separately reports the pre-existing branch; the new
    run's own link must not itself be part of the reported break."""
    import json

    from researchledger.validator import validate

    ws = init_workspace(tmp_path)
    first = run_command(ws, [sys.executable, "-c", "pass"])
    second = run_command(ws, [sys.executable, "-c", "pass"])

    # Force a branch: rewrite `second` to claim the same predecessor as `first`.
    first_manifest_path = ws.runs_dir / first["run_id"] / "manifest.json"
    first_hash = "sha256:" + sha256_file(first_manifest_path)
    genesis_hash = json.loads(first_manifest_path.read_text(encoding="utf-8"))["previous_run_hash"]
    second_manifest_path = ws.runs_dir / second["run_id"] / "manifest.json"
    second_manifest = json.loads(second_manifest_path.read_text(encoding="utf-8"))
    second_manifest["previous_run_hash"] = genesis_hash
    second_manifest_path.write_text(json.dumps(second_manifest), encoding="utf-8")

    third = run_command(ws, [sys.executable, "-c", "pass"])  # must not raise

    result = validate(ws)
    branch_errors = [i for i in result.errors if "chain branch detected" in i.message]
    assert len(branch_errors) == 1
    # The new run's own link must be internally consistent (points at
    # exactly one of the two branch tips, whichever _seal_run picked).
    assert third["previous_run_hash"] in (first_hash, "sha256:" + sha256_file(second_manifest_path))
