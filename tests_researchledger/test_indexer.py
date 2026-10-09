import time

from researchledger.indexer import build_index, write_index
from researchledger.models import Claim
from researchledger.workspace import init_workspace


def _write_claim(ws, cid):
    cl = Claim(
        id=cid, path=ws.claims_dir / f"{cid}.md", schema_version="2.0", name=cid,
        status="hypothesis", body=f"# Claim: {cid}\n\n## Statement\nSomething.\n",
    )
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")


def test_build_index_reflects_claim_counts(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C001")

    index = build_index(ws)
    assert index["counts"]["claims"] == 1
    assert index["claim_status_counts"] == {"hypothesis": 1}
    assert index["schema_version"] == "2.0"


def test_write_index_persists_to_disk(tmp_path):
    ws = init_workspace(tmp_path)
    path = write_index(ws)
    assert path.exists()
    assert path == ws.root / ".researchledger" / "index.json"


def test_index_build_stays_fast_at_moderate_scale(tmp_path):
    ws = init_workspace(tmp_path)
    for i in range(200):
        _write_claim(ws, f"C{i:03d}")

    started = time.monotonic()
    build_index(ws)
    elapsed = time.monotonic() - started
    # Generous smoke bound, not the strict <150ms/10k-record target from the
    # spec — that target is about the *hook's* single-file read, not this
    # full rebuild; see reference/run-ledger.md#the-cached-index.
    assert elapsed < 5.0
