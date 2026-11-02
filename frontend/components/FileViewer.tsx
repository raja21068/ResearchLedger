"use client";

// Renders one workspace file: PDF in the browser's own viewer, Word via the
// server's mammoth HTML conversion (in a script-less sandboxed iframe), Markdown
// rendered, LaTeX/text as source. Also offers the export actions for that file.

import { useCallback, useEffect, useState } from "react";
import { api, fileUrl, post, ApiError } from "@/lib/api";
import { FileCompare } from "./FileCompare";
import { FileHistory } from "./FileHistory";
import { Markdown } from "./Markdown";
import { btn2, ErrorBox } from "./ui";

interface Preview { kind: string; size: number; sha256: string; html?: string; text?: string | null; warnings?: string[] }

const DOCX_FRAME_CSS = `body{font-family:"Times New Roman",Georgia,serif;font-size:12pt;line-height:1.5;color:#111;
max-width:780px;margin:32px auto;padding:48px 56px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.12)}
html{background:#e9ecef}h1{font-size:15pt}h1.doc-title{font-size:20pt;text-align:center}
.doc-subtitle{text-align:center;color:#444}h2{font-size:13pt}h3{font-size:12pt}
table{border-collapse:collapse}td,th{border:1px solid #999;padding:4px 8px}img{max-width:100%}`;

export function kindOf(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "docx") return "docx";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return "image";
  if (ext === "md") return "markdown";
  return "text";
}

export function FileViewer({ projectId, path, version = 0, fullPage = false, onExported, onRenamed }: {
  projectId: string; path: string; version?: number; fullPage?: boolean;
  onExported?: (newPath: string) => void;
  onRenamed?: (newPath: string) => void;
}) {
  const kind = kindOf(path);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSource, setShowSource] = useState(false);
  const [bust, setBust] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
  const [compareWith, setCompareWith] = useState<number | null>(null);

  useEffect(() => { setCompareWith(null); }, [path]);

  async function rename() {
    const next = window.prompt("New name or folder for this file (inside the project):", path)?.trim();
    if (!next || next === path) return;
    setError(null);
    try {
      const res = await post<{ to: string }>(`/projects/${projectId}/files/rename`, { path, new_path: next });
      if (onRenamed) onRenamed(res.to);
      else if (fullPage) window.location.replace(`/view/${projectId}?path=${encodeURIComponent(res.to)}`);
      else onExported?.(res.to);
    } catch (e) { setError(e); }
  }

  const load = useCallback(async () => {
    setError(null);
    if (kind === "pdf" || kind === "image") { setPreview(null); return; }
    try {
      setPreview(await api<Preview>(`/projects/${projectId}/files/preview?path=${encodeURIComponent(path)}`));
    } catch (e) { setError(e); }
  }, [projectId, path, kind]);

  useEffect(() => { load(); }, [load, version, bust]);

  async function exportTo(to: "pdf" | "docx") {
    setBusy(to); setError(null); setNotice(null);
    try {
      const res = await post<{ path: string; warnings: string[] }>(`/projects/${projectId}/export`, { path, to });
      setNotice(res.warnings.length ? res.warnings.join(" ") : null);
      onExported?.(res.path);
    } catch (e) {
      const d = e instanceof ApiError ? (e.detail as { log_tail?: string }) : null;
      setError(d?.log_tail ? new Error(`LaTeX compilation failed. Log tail:\n${d.log_tail.slice(-1500)}`) : e);
    } finally { setBusy(null); }
  }

  const raw = `${fileUrl(projectId, path)}&v=${version}-${bust}`;
  const height = fullPage ? "h-[calc(100vh-57px)]" : "h-full";
  const name = path.split("/").pop();

  return (
    <div className={`flex min-h-0 flex-col ${height}`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-white px-3 py-2">
        <span className="mr-auto min-w-0 truncate font-mono text-xs text-faint" title={path}>{path}</span>
        {path.endsWith(".tex") && (
          <button className={btn2} disabled={!!busy} onClick={() => exportTo("pdf")}>
            {busy === "pdf" ? "Compiling…" : "Compile PDF"}
          </button>
        )}
        {path.endsWith(".md") && (
          <>
            <button className={btn2} onClick={() => setShowSource(!showSource)}>{showSource ? "Rendered" : "Source"}</button>
            <button className={btn2} disabled={!!busy} onClick={() => exportTo("docx")}>
              {busy === "docx" ? "Exporting…" : "Export Word"}
            </button>
          </>
        )}
        <button className={btn2} onClick={() => setBust((b) => b + 1)} aria-label="Reload file">Reload</button>
        <button className={btn2} onClick={rename}>Rename</button>
        <button className={btn2} aria-pressed={showHistory} onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? "Hide history" : "History"}
        </button>
        {!fullPage && (
          <a className={btn2} href={`/view/${projectId}?path=${encodeURIComponent(path)}`} target="_blank"
            rel="noreferrer">Open in new tab ↗</a>
        )}
        <a className={btn2} href={fileUrl(projectId, path, true)} download={name}>Download</a>
      </div>
      {notice && <div className="border-b border-[#f0d2ac] bg-[#fff8ef] px-3 py-2 text-sm text-[#7a3a06]">{notice}</div>}
      {error ? <div className="whitespace-pre-wrap p-3"><ErrorBox error={error} /></div> : null}

      <div className="flex min-h-0 flex-1">
      <div className="min-h-0 flex-1 overflow-auto bg-[#e9ecef]">
        {compareWith !== null && (
          <FileCompare projectId={projectId} path={path} old={compareWith} onClose={() => setCompareWith(null)} />
        )}
        {compareWith === null && (<>
        {kind === "pdf" && <iframe title={name} src={raw} className="h-full min-h-[480px] w-full border-0 bg-white" />}
        {kind === "image" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={raw} alt={name ?? ""} className="mx-auto my-6 max-w-[95%] bg-white shadow" />
        )}
        {kind === "docx" && preview?.html !== undefined && (
          <div className="flex h-full min-h-[480px] flex-col">
            {preview.warnings && preview.warnings.length > 0 && (
              <details className="border-b border-line bg-white px-3 py-2 text-xs text-faint">
                <summary>{preview.warnings.length} conversion note(s): the preview may differ from Word</summary>
                <ul className="mt-1 list-disc pl-5">{preview.warnings.slice(0, 20).map((w, i) => <li key={i}>{w}</li>)}</ul>
              </details>
            )}
            <iframe title={name} sandbox="" className="w-full flex-1 border-0"
              srcDoc={`<!doctype html><meta charset="utf-8"><style>${DOCX_FRAME_CSS}</style><body>${preview.html}</body>`} />
          </div>
        )}
        {kind === "markdown" && preview?.text != null && (
          showSource
            ? <pre className="m-0 min-h-full whitespace-pre-wrap bg-white p-5 font-mono text-[13px] leading-relaxed">{preview.text}</pre>
            : <div className="mx-auto my-6 max-w-[820px] bg-white p-10 shadow"><Markdown text={preview.text} /></div>
        )}
        {kind === "text" && preview && (
          preview.text != null
            ? <pre className="m-0 min-h-full whitespace-pre-wrap bg-white p-5 font-mono text-[13px] leading-relaxed">{preview.text}</pre>
            : <p className="p-5 text-sm text-muted">{preview.warnings?.join(" ") ?? "No text preview for this file type. Use Download."}</p>
        )}
        {!preview && !error && kind !== "pdf" && kind !== "image" && <p className="rl-pulse p-5 text-sm text-faint">Loading…</p>}
        </>)}
      </div>
      {showHistory && <FileHistory projectId={projectId} path={path} onRestored={() => { setCompareWith(null); setBust((b) => b + 1); }}
        onCompare={(v) => setCompareWith(v)} />}
      </div>
    </div>
  );
}
