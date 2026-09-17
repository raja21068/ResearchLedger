"""Transactional writes and advisory locking for canonical ledger files.

Every write a ledger-owned file (manifest.json, index.json, migration
reports) goes through `atomic_write_text`/`atomic_write_json`: write to a
sibling temp file, fsync, then `os.replace` — so a crash mid-write leaves the
original file intact instead of a half-written one. `file_lock` is a small
cross-platform advisory lock for the one place two `researchledger run`
invocations could race: allocating the next run id.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    try:
        with open(tmp_path, "w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, data, *, indent: int = 2) -> None:
    atomic_write_text(Path(path), json.dumps(data, indent=indent) + "\n")


@contextlib.contextmanager
def file_lock(path: Path, *, timeout: float = 10.0, poll_interval: float = 0.05) -> Iterator[None]:
    """A simple, cross-platform exclusive lock backed by O_CREAT|O_EXCL.

    Not a substitute for a real lock manager under heavy contention, but
    sufficient for the run ledger's actual concurrency requirement: don't let
    two `researchledger run` processes allocate the same run id.
    """
    lock_path = Path(str(path) + ".lock")
    deadline = time.monotonic() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            # PermissionError shows up on Windows when a just-deleted lock
            # file is still in the filesystem's pending-delete state —
            # treat it the same as "someone else holds the lock" and retry.
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}") from None
            time.sleep(poll_interval)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        lock_path.unlink(missing_ok=True)
