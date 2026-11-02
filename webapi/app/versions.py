"""File versions: every content a workspace file has had is kept, by SHA-256, and can be viewed or restored.

Three parts (docs/STORAGE_DATABASE_ARCHITECTURE.md §2–§5):
- the object store `objects/sha256/ab/<hash>`: immutable copies of file contents, written once (temp file + replace);
- the tables `blobs`, `files`, `file_versions`: which path had which content, when, written by whom (and which run);
- the workspace stays the working copy that people and agents edit.

Agents edit files directly, so versions are captured by `sync()`: it compares the working copy with each file's current
version and records what changed. It runs before an agent task (anything changed outside a tracked run is saved as
`external`) and after it (changes are saved as `agent` with the run id). Uploads and restores record their own versions.
Restoring never removes later versions; it adds a new one.
"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from . import workspace
from .config import settings
from .db import Store, new_id, now

MAX_VERSIONED_BYTES = workspace.SNAPSHOT_HASH_LIMIT  # larger files are not copied into the object store
AUTHORS = {"user", "agent", "server_exec", "restore", "external"}


class VersionError(ValueError):
    pass


def objects_dir() -> Path:
    return settings.data_dir / "objects" / "sha256"


def object_path(digest: str) -> Path:
    return objects_dir() / digest[:2] / digest


def _skip(rel: str, size: int) -> bool:
    return size > MAX_VERSIONED_BYTES or workspace.is_build_output(rel)


def put_blob(store: Store, src: Path, digest: str | None = None) -> str:
    """Copy `src` into the object store (once per content) and return its SHA-256."""
    digest = digest or workspace.sha256(src)
    dest = object_path(digest)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".tmp_")
        os.close(fd)
        try:
            shutil.copyfile(src, tmp)
            if workspace.sha256(Path(tmp)) != digest:  # the file changed while we copied it
                raise VersionError(f"{src.name} changed while it was being saved; try again")
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        os.chmod(dest, stat.S_IREAD)
    store.exec("INSERT OR IGNORE INTO blobs(sha256, size, created_at) VALUES (?,?,?)",
               (digest, dest.stat().st_size, now()))
    return digest


def _file_row(store: Store, project_id: str, rel: str) -> dict | None:
    return store.one("SELECT * FROM files WHERE project_id=? AND path=?", (project_id, rel))


def _current_sha(store: Store, f: dict | None) -> str | None:
    if not f or f["current_version"] is None:
        return None
    v = store.one("SELECT sha256 FROM file_versions WHERE file_id=? AND version=?", (f["id"], f["current_version"]))
    return v["sha256"] if v else None


def record(store: Store, project_id: str, rel: str, author: str, run_id: str | None = None,
           note: str | None = None, digest: str | None = None) -> int | None:
    """Save the working copy of `rel` as a new version if its content differs from the current one.
    Returns the new version number, or None when nothing changed (or the file is not versioned)."""
    if author not in AUTHORS:
        raise VersionError(f"unknown author kind {author!r}")
    p = workspace.project_root(project_id) / rel
    if not p.is_file():
        return None
    st = p.stat()
    if _skip(rel, st.st_size):
        return None
    digest = put_blob(store, p, digest)
    f = _file_row(store, project_id, rel)
    if f and f["deleted_at"] is None and _current_sha(store, f) == digest:
        store.exec("UPDATE files SET mtime=?, size=? WHERE id=?", (st.st_mtime, st.st_size, f["id"]))
        return None
    with store.conn() as c:  # one transaction: the version row and the file's pointer change together
        if not f:
            fid = new_id("fil")
            c.execute("INSERT INTO files(id, project_id, path, current_version, deleted_at, mtime, size) "
                      "VALUES (?,?,?,NULL,NULL,?,?)", (fid, project_id, rel, st.st_mtime, st.st_size))
            version = 1
        else:
            fid = f["id"]
            version = (c.execute("SELECT COALESCE(MAX(version), 0) FROM file_versions WHERE file_id=?",
                                 (fid,)).fetchone()[0]) + 1
        c.execute("INSERT INTO file_versions(file_id, version, sha256, size, author_kind, run_id, note, created_at) "
                  "VALUES (?,?,?,?,?,?,?,?)", (fid, version, digest, st.st_size, author, run_id, note, now()))
        c.execute("UPDATE files SET current_version=?, deleted_at=NULL, mtime=?, size=? WHERE id=?",
                  (version, st.st_mtime, st.st_size, fid))
    return version


def sync(store: Store, project_id: str, author: str, run_id: str | None = None) -> dict:
    """Bring the version history up to date with the working copy: new or changed files get a version, files that
    disappeared are marked deleted (their content stays in the object store). Unchanged files are skipped cheaply
    (same modification time and size as at the last sync)."""
    root = workspace.project_root(project_id)
    known = {f["path"]: f for f in store.all("SELECT * FROM files WHERE project_id=?", (project_id,))}
    seen, saved, deleted = set(), [], []
    for p in workspace._walk(root):
        rel = p.relative_to(root).as_posix()
        seen.add(rel)
        st = p.stat()
        if _skip(rel, st.st_size):
            continue
        f = known.get(rel)
        if f and f["deleted_at"] is None and f["mtime"] == st.st_mtime and f["size"] == st.st_size:
            continue
        try:
            if record(store, project_id, rel, author, run_id) is not None:
                saved.append(rel)
        except VersionError:
            continue  # being written right now; the next sync will catch it
    for rel, f in known.items():
        if rel not in seen and f["deleted_at"] is None:
            store.exec("UPDATE files SET deleted_at=? WHERE id=?", (now(), f["id"]))
            store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
                       (project_id, now(), run_id or author, "file_deleted", rel))
            deleted.append(rel)
    return {"saved": saved, "deleted": deleted}


def history(store: Store, project_id: str, rel: str) -> dict:
    f = _file_row(store, project_id, rel)
    if not f:
        return {"path": rel, "current_version": None, "deleted_at": None, "versions": []}
    rows = store.all("SELECT version, sha256, size, author_kind, run_id, note, created_at FROM file_versions "
                     "WHERE file_id=? ORDER BY version DESC", (f["id"],))
    return {"path": rel, "current_version": f["current_version"], "deleted_at": f["deleted_at"], "versions": rows}


def version_object(store: Store, project_id: str, rel: str, version: int) -> Path:
    f = _file_row(store, project_id, rel)
    v = f and store.one("SELECT sha256 FROM file_versions WHERE file_id=? AND version=?", (f["id"], version))
    if not v:
        raise VersionError("version not found")
    p = object_path(v["sha256"])
    if not p.is_file() or workspace.sha256(p) != v["sha256"]:
        raise VersionError("the stored copy of this version is missing or damaged")
    return p


def restore(store: Store, project_id: str, rel: str, version: int) -> int:
    """Make `version` the current content again, as a NEW version; nothing later is lost."""
    src = version_object(store, project_id, rel, version)
    dest = workspace.project_root(project_id) / rel
    if dest.is_file():  # save unsaved edits first, so the restore can itself be undone
        record(store, project_id, rel, "external", note="saved automatically before a restore")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".restore_")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.chmod(tmp, stat.S_IREAD | stat.S_IWRITE)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    new = record(store, project_id, rel, "restore", note=f"restored version {version}")
    store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (project_id, now(), "user", "file_restored", f"{rel} v{version}"))
    if new is None:  # content equal to the current version: nothing to add
        return _file_row(store, project_id, rel)["current_version"]
    return new


def safe_sync(store: Store, project_id: str, author: str, run_id: str | None = None) -> dict:
    """sync() that never breaks the run it is attached to; a failure is reported, not raised."""
    try:
        return sync(store, project_id, author, run_id)
    except Exception as exc:  # noqa: BLE001 — versioning must not stop research work
        if run_id:
            store.add_event(run_id, "status", {"text": f"File versions were not saved: {exc}"})
        return {"saved": [], "deleted": [], "error": str(exc)}
