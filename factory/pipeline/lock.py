"""One active controller per workspace: portable exclusive-create run lock."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def exclusive_run(project):
    project = Path(project).resolve()
    path = project / "control" / "run.lock"
    if path.parent.is_symlink() or not path.parent.resolve().is_relative_to(project):
        raise ValueError("control directory must stay inside the project workspace")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"another run may be active: {path}; verify before removing a stale lock") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)
