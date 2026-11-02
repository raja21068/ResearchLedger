"""Project workspace files: safe path resolution, listing, snapshots and previews."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import subprocess
from pathlib import Path

from .config import settings

HIDDEN_DIRS = {".git", ".claude", "__pycache__", "node_modules", ".venv"}
LATEX_JUNK = {".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".bcf", ".fls", ".fdb_latexmk",
              ".synctex.gz", ".run.xml", ".lof", ".lot", ".nav", ".snm"}
TEXT_EXT = {".md", ".txt", ".tex", ".bib", ".json", ".csv", ".tsv", ".py", ".yaml", ".yml",
            ".r", ".m", ".sh", ".toml", ".cfg", ".ini", ".html", ".xml", ".sty", ".cls", ".bst"}
UPLOAD_EXT = TEXT_EXT | {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                         ".xlsx", ".zip", ".ipynb", ".pptx"}
MAX_LIST = 2000

mimetypes.add_type("text/markdown", ".md")
mimetypes.add_type("application/x-tex", ".tex")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")


class PathError(ValueError):
    pass


ZIP_SKIP = {"__MACOSX", ".git", "node_modules", "__pycache__", ".DS_Store", ".venv"}


def unzip_into(zip_path: Path, dest: Path, max_files: int = 400, max_bytes: int = 300 * 1024 * 1024) -> list[Path]:
    """Unpack an uploaded zip safely: regular files with relative names only, known file types, size limits.

    All or nothing: the limits are checked before anything is written, everything is unpacked into a temporary
    folder first, and only a complete extraction is moved into `dest`. A damaged zip leaves `dest` untouched."""
    import shutil
    import tempfile
    import zipfile
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise PathError("that zip file could not be opened") from exc
    with z:
        accepted, total = [], 0
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p]
            if (info.is_dir() or not parts or name.startswith("/") or ".." in parts or ":" in parts[0]
                    or any(p in ZIP_SKIP for p in parts) or (info.external_attr >> 16) & 0o170000 == 0o120000
                    or Path(parts[-1]).suffix.lower() not in UPLOAD_EXT - {".zip"}):
                continue
            total += info.file_size
            if len(accepted) >= max_files or total > max_bytes:
                raise PathError(f"the zip is too large (limit {max_files} files / {max_bytes // 2**20} MB)")
            accepted.append((info, parts))
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".unzip_", dir=dest.parent))
        try:
            for info, parts in accepted:
                target = staging.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        except (zipfile.BadZipFile, OSError, EOFError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise PathError("the zip file is damaged; nothing was unpacked") from exc
    out = []
    try:
        for _, parts in accepted:
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging.joinpath(*parts), target)
            out.append(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return out


def project_root(project_id: str) -> Path:
    root = settings.projects_dir / project_id / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve(project_id: str, rel: str) -> Path:
    """Resolve a user-supplied relative path, refusing anything outside the workspace."""
    if not rel or rel.startswith(("/", "\\")) or ":" in rel or "\x00" in rel:
        raise PathError("path must be relative to the project workspace")
    root = project_root(project_id)
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise PathError("path escapes the project workspace")
    return target


def file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
        return "image"
    if ext == ".md":
        return "markdown"
    if ext in TEXT_EXT:
        return "text"
    return "binary"


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in HIDDEN_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            yield Path(dirpath) / name


def is_build_output(path: str | Path) -> bool:
    """LaTeX auxiliary files: kept on disk and hashed, but not shown as documents."""
    p = Path(path)
    return p.suffix in LATEX_JUNK or "".join(p.suffixes[-2:]) in LATEX_JUNK


def list_files(project_id: str, include_build: bool = False) -> list[dict]:
    root = project_root(project_id)
    out = []
    for p in _walk(root):
        if not include_build and is_build_output(p):
            continue
        st = p.stat()
        out.append({"path": p.relative_to(root).as_posix(), "size": st.st_size,
                    "modified": st.st_mtime, "kind": file_kind(p)})
        if len(out) >= MAX_LIST:
            break
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


SNAPSHOT_HASH_LIMIT = 64 * 1024 * 1024  # larger files are compared by time and size only


def snapshot(project_id: str) -> dict[str, tuple[float, int, str]]:
    """path -> (mtime, size, sha256); the hash makes change detection content-based, not timestamp-based."""
    root = project_root(project_id)
    out = {}
    for p in _walk(root):
        st = p.stat()
        out[p.relative_to(root).as_posix()] = (st.st_mtime, st.st_size,
                                               sha256(p) if st.st_size <= SNAPSHOT_HASH_LIMIT else "")
    return out


def diff_snapshot(project_id: str, before: dict) -> list[tuple[str, str]]:
    """created / modified (content differs) / deleted, between `before` and now."""
    root = project_root(project_id)
    changes, alive = [], set()
    for p in _walk(root):
        rel = p.relative_to(root).as_posix()
        alive.add(rel)
        if rel not in before:
            changes.append((rel, "created"))
            continue
        mtime, size, digest = before[rel]
        st = p.stat()
        if (st.st_mtime, st.st_size) == (mtime, size):
            continue  # untouched
        if not digest or st.st_size != size or sha256(p) != digest:
            changes.append((rel, "modified"))
    changes += [(rel, "deleted") for rel in before if rel not in alive]
    return sorted(changes)


def changed_since(project_id: str, since: float) -> list[str]:
    """Workspace files modified after `since` (epoch seconds); restart-safe artifact detection."""
    root = project_root(project_id)
    return sorted(p.relative_to(root).as_posix() for p in _walk(root) if p.stat().st_mtime >= since)


def docx_to_html(path: Path) -> dict:
    import mammoth  # optional dependency; reported by the caller when missing
    with path.open("rb") as f:
        result = mammoth.convert_to_html(f, style_map="p[style-name='Title'] => h1.doc-title:fresh\n"
                                                      "p[style-name='Subtitle'] => p.doc-subtitle:fresh")
    return {"html": result.value, "warnings": [m.message for m in result.messages]}


# --- Exports ---------------------------------------------------------------

def markdown_to_docx(src: Path, dest: Path) -> list[str]:
    """Deterministic Markdown → DOCX for headings, paragraphs, lists, bold/italic and code.

    Tables, equations and figures are not converted; warnings say so instead of
    silently dropping them.
    """
    import re
    from docx import Document

    doc = Document()
    warnings: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def add_runs(par, text):
        for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                par.add_run(part[2:-2]).bold = True
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                par.add_run(part[1:-1]).italic = True
            elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                r = par.add_run(part[1:-1]); r.font.name = "Consolas"
            elif part:
                par.add_run(part)

    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("```"):
            if in_code:
                p = doc.add_paragraph()
                r = p.add_run("\n".join(code_lines)); r.font.name = "Consolas"
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            # "#" is the document title; "##" and deeper map to Heading 1–4.
            doc.add_heading(m.group(2).strip(), level=min(len(m.group(1)) - 1, 4))
        elif re.match(r"^\s*[-*+]\s+", line):
            add_runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*+]\s+", "", line))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            add_runs(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+[.)]\s+", "", line))
        elif line.strip().startswith("|"):
            if "tables" not in warnings:
                warnings.append("tables")
            doc.add_paragraph(line)
        elif "$$" in line or "\\(" in line:
            if "equations" not in warnings:
                warnings.append("equations")
            doc.add_paragraph(line)
        elif line.strip():
            add_runs(doc.add_paragraph(), line.strip())
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dest)
    return [f"Markdown {w} were copied as plain text, not converted." for w in warnings]


def latex_to_pdf(src: Path, timeout: int = 240) -> dict:
    """Compile with pdflatex (+bibtex when a .bib is referenced). Shell escape stays off."""
    import shutil
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        raise RuntimeError("pdflatex is not installed on the server")
    base = ["-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "-file-line-error"]
    log = []

    def run(cmd):
        done = subprocess.run(cmd, cwd=src.parent, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, shell=False)
        log.append(done.stdout[-4000:])
        return done.returncode

    code = run([pdflatex, *base, src.name])
    text = src.read_text(encoding="utf-8", errors="replace")
    if code == 0 and ("\\bibliography{" in text or "\\addbibresource" in text):
        tool = shutil.which("biber") if "\\addbibresource" in text else shutil.which("bibtex")
        if tool:
            run([tool, src.stem])
        run([pdflatex, *base, src.name])
    if code == 0:
        code = run([pdflatex, *base, src.name])
    pdf = src.with_suffix(".pdf")
    return {"ok": code == 0 and pdf.is_file(), "pdf": pdf, "log_tail": "\n".join(log)[-6000:]}
