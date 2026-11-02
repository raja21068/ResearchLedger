"""Automatic, verified database backups and a read-only integrity check (docs/STORAGE_DATABASE_ARCHITECTURE.md §7).

- A backup is a consistent SQLite online copy in `webapi_data/backups/`, checked with `PRAGMA integrity_check` and
  hashed. File contents need no copy here: they live in the read-only object store and the database records them.
- The server makes one on start-up when the newest is older than a day, then once a day; the last KEEP are kept.
- `audit()` re-hashes stored file versions and compares the database with the disk. It only reports; it never
  deletes or repairs anything. "ok" means the database and every checked stored version are intact; files changed
  or deleted since the last save are listed but are not errors (the next sync saves them).
"""
from __future__ import annotations

import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import versions, workspace
from .config import settings
from .db import Store, new_id, now

KEEP = 14
DAY = 24 * 3600


def backups_dir() -> Path:
    return settings.data_dir / "backups"


def create(store: Store, reason: str = "manual") -> dict:
    """Copy the live database while it is in use, verify the copy, record it, and drop the oldest beyond KEEP."""
    d = backups_dir()
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = d / f"researchledger-{stamp}.sqlite3"
    tmp = dest.with_suffix(".part")
    src = sqlite3.connect(store.path, timeout=30)
    try:
        out = sqlite3.connect(tmp)
        with out:
            src.backup(out)
        out.close()
    finally:
        src.close()
    check = sqlite3.connect(tmp)
    try:
        ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()
    if not ok:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("the backup copy failed its integrity check; the live database was not changed")
    os.replace(tmp, dest)
    row = {"id": new_id("bak"), "created_at": now(), "path": dest.name, "db_sha256": workspace.sha256(dest),
           "objects": store.one("SELECT COUNT(*) n FROM blobs")["n"], "verified_at": now(), "reason": reason}
    store.exec("INSERT INTO backups(id, created_at, path, db_sha256, objects, verified_at, reason) "
               "VALUES (:id,:created_at,:path,:db_sha256,:objects,:verified_at,:reason)", row)
    for old in store.all("SELECT id, path FROM backups ORDER BY created_at DESC")[KEEP:]:
        (d / old["path"]).unlink(missing_ok=True)
        store.exec("DELETE FROM backups WHERE id=?", (old["id"],))
    return row


def listing(store: Store) -> list[dict]:
    rows = store.all("SELECT * FROM backups ORDER BY created_at DESC")
    for r in rows:
        p = backups_dir() / r["path"]
        r["present"] = p.is_file()
        r["size"] = p.stat().st_size if r["present"] else None
    return rows


def due(store: Store) -> bool:
    last = store.one("SELECT created_at FROM backups ORDER BY created_at DESC LIMIT 1")
    if not last:
        return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"]) > timedelta(seconds=DAY)


def start_daily(store: Store) -> None:
    """Background thread: back up now if due, then check once an hour."""
    def loop():
        while True:
            try:
                if due(store):
                    create(store, "automatic")
            except Exception as exc:  # noqa: BLE001 — a failed backup must not stop the server; it is logged
                store.log_activity(None, "backup_failed", str(exc)[:500])
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True, name="daily-backup").start()


def audit(store: Store, project_id: str | None = None, sample: int | None = 200) -> dict:
    """Re-hash stored versions (a random sample, or all with sample=None) and compare database and disk."""
    where, args = ("WHERE f.project_id=?", (project_id,)) if project_id else ("", ())
    rows = store.all(f"SELECT DISTINCT v.sha256 FROM file_versions v JOIN files f ON f.id=v.file_id {where}", args)
    hashes = [r["sha256"] for r in rows]
    checked = hashes if sample is None or len(hashes) <= sample else random.sample(hashes, sample)
    damaged = []
    for h in checked:
        p = versions.object_path(h)
        if not p.is_file() or workspace.sha256(p) != h:
            damaged.append(h)
    for h in checked:
        if h not in damaged:
            store.exec("UPDATE blobs SET verified_at=? WHERE sha256=?", (now(), h))
    missing_files, unsaved = [], []
    files = store.all(f"SELECT f.project_id, f.path, f.mtime, f.size FROM files f {where} "
                      f"{'AND' if where else 'WHERE'} f.deleted_at IS NULL", args)
    for f in files:
        p = settings.projects_dir / f["project_id"] / "workspace" / f["path"]
        if not p.is_file():
            missing_files.append(f"{f['project_id']}/{f['path']}")
        elif (p.stat().st_mtime, p.stat().st_size) != (f["mtime"], f["size"]):
            unsaved.append(f"{f['project_id']}/{f['path']}")
    known = {r["sha256"] for r in store.all("SELECT sha256 FROM blobs")}
    orphans = 0
    if versions.objects_dir().is_dir() and not project_id:
        orphans = sum(1 for p in versions.objects_dir().glob("*/*") if p.name not in known and not p.name.startswith("."))
    integrity = store.one("PRAGMA integrity_check")
    db_ok = list(integrity.values())[0] == "ok"
    return {"checked_versions": len(checked), "total_versions": len(hashes), "damaged": damaged,
            "deleted_since_last_save": missing_files, "changed_since_last_save": unsaved, "orphan_objects": orphans,
            "database_ok": db_ok, "ok": db_ok and not damaged, "checked_at": now()}
