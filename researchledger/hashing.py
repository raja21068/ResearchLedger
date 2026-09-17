"""SHA-256 helpers for artifact integrity checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    """SHA-256 of a file, or of a directory tree — for a directory, the hash
    covers every file's relative path and content hash, sorted, so it's
    order-independent and detects added/removed/changed files alike. Used
    for input-dataset hashing (`researchledger run --data <path>`), where a
    dataset may be one file or a whole directory.
    """
    path = Path(path)
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file_path.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(sha256_file(file_path).encode("ascii"))
    return digest.hexdigest()
