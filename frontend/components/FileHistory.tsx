"use client";

// Every saved version of one file, newest first. View opens a read-only copy; Restore makes it current again
// as a new version, so nothing is ever lost (the server keeps every version by its SHA-256).

import { useCallback, useEffect, useState } from "react";
import { api, post, versionUrl } from "@/lib/api";
import { btn2, ErrorBox } from "./ui";

interface Version {
  version: number; sha256: string; size: number; author_kind: string; run_id: string | null;
  note: string | null; created_at: string;
}
interface History { path: string; current_version: number | null; deleted_at: string | null; versions: Version[] }

const WHO: Record<string, string> = {
  user: "You", agent: "Agent", server_exec: "Experiment run", restore: "Restored", external: "Saved edit",
};

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function size(n: number) {
  return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

export function FileHistory({ projectId, path, onRestored }: {
  projectId: string; path: string; onRestored: () => void;
}) {
  const [hist, setHist] = useState<History | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try { setHist(await api<History>(`/projects/${projectId}/files/history?path=${encodeURIComponent(path)}`)); }
    catch (e) { setError(e); }
  }, [projectId, path]);

  useEffect(() => { load(); }, [load]);

  async function restore(v: number) {
    if (!window.confirm(`Make version ${v} the current file? The current content stays in the history.`)) return;
    setBusy(v); setError(null);
    try {
      await post(`/projects/${projectId}/files/restore`, { path, version: v });
      await load();
      onRestored();
    } catch (e) { setError(e); } finally { setBusy(null); }
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-line bg-white">
      <div className="border-b border-line px-3 py-2 text-sm font-semibold">History</div>
      {error ? <div className="p-3"><ErrorBox error={error} /></div> : null}
      {!hist && !error && <p className="rl-pulse p-3 text-sm text-faint">Loading…</p>}
      {hist && hist.versions.length === 0 && (
        <p className="p-3 text-sm text-muted">No saved versions yet. A version is saved whenever you upload this file
          or an agent or experiment changes it.</p>
      )}
      <ol className="min-h-0 flex-1 overflow-auto">
        {hist?.versions.map((v) => {
          const current = v.version === hist.current_version && !hist.deleted_at;
          return (
            <li key={v.version} className="border-b border-line px-3 py-2 text-sm">
              <div className="flex items-baseline gap-2">
                <span className="font-semibold">v{v.version}</span>
                <span className="text-muted">
                  {v.version === 1 && v.author_kind === "external" ? "First saved copy" : WHO[v.author_kind] ?? v.author_kind}
                </span>
                {current && <span className="ml-auto rounded-full bg-[#d4eee9] px-2 text-xs text-[#07423d]">current</span>}
              </div>
              <div className="text-xs text-faint">{when(v.created_at)} · {size(v.size)}</div>
              {v.note && <div className="text-xs text-faint">{v.note}</div>}
              <div className="mt-1 flex gap-2">
                <a className={btn2} href={versionUrl(projectId, path, v.version)} target="_blank" rel="noreferrer">View</a>
                {!current && (
                  <button className={btn2} disabled={busy !== null} onClick={() => restore(v.version)}>
                    {busy === v.version ? "Restoring…" : "Restore"}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
