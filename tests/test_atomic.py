import json
import threading

from researchledger.atomic import atomic_write_json, atomic_write_text, file_lock


def test_atomic_write_text_creates_file(tmp_path):
    path = tmp_path / "data.txt"
    atomic_write_text(path, "hello")
    assert path.read_text(encoding="utf-8") == "hello"


def test_atomic_write_leaves_no_temp_files_behind(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"a": 1})
    leftovers = [p for p in tmp_path.iterdir() if p.name != "data.json"]
    assert leftovers == []


def test_atomic_write_replaces_existing_file(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"a": 1})
    atomic_write_json(path, {"a": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}


def test_file_lock_serializes_concurrent_increments(tmp_path):
    target = tmp_path / "counter.lock_target"
    counter = {"value": 0}
    errors = []

    def bump():
        try:
            with file_lock(target):
                current = counter["value"]
                counter["value"] = current + 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=bump) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert counter["value"] == 20
