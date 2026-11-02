"use client";

// Deleted files of one project. Their content is still kept (every version), so each can be viewed or brought back.

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, post, versionUrl } from "@/lib/api";
import { btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Deleted { path: string; current_version: number; deleted_at: string; last_size: number | null; last_saved_at: string | null }

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function TrashPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [rows, setRows] = useState<Deleted[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api<Deleted[]>(`/projects/${id}/files/trash`).then(setRows).catch(setError);
  }, [id]);
  useEffect(load, [load]);

  async function bringBack(r: Deleted) {
    setBusy(r.path); setError(null); setDone(null);
    try {
      await post(`/projects/${id}/files/restore`, { path: r.path, version: r.current_version });
      setDone(r.path);
      load();
    } catch (e) { setError(e); } finally { setBusy(null); }
  }

  return (
    <main className="mx-auto max-w-[900px] px-4 py-7 sm:px-8">
      <div className="mb-1 text-sm text-faint"><Link href={`/projects/${id}/home`} className="hover:text-ink">← Back to the project</Link></div>
      <PageHeader title="Trash" sub="Files that were deleted from this project. Nothing here is gone: bring a file back, or view its last version."
        actions={<button className={btn2} onClick={load}>Refresh</button>} />
      <ErrorBox error={error} />
      {done && (
        <p className="mb-3 rounded-lg border border-[#b8e0d2] bg-[#effaf6] px-3 py-2 text-sm">
          Restored <Link className="text-accent underline" href={`/view/${id}?path=${encodeURIComponent(done)}`}>{done}</Link>.
        </p>
      )}
      {!rows && !error && <p className="rl-pulse text-sm text-faint">Loading…</p>}
      {rows && rows.length === 0 && <Card className="p-5 text-sm text-muted">The trash is empty.</Card>}
      {rows && rows.length > 0 && (
        <Card className="divide-y divide-line">
          {rows.map((r) => (
            <div key={r.path} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-sm">{r.path}</div>
                <div className="text-xs text-faint">Deleted {when(r.deleted_at)} · last saved as version {r.current_version}</div>
              </div>
              <a className={btn2} href={versionUrl(id, r.path, r.current_version)} target="_blank" rel="noreferrer">View</a>
              <button className={btn2} disabled={busy !== null} onClick={() => bringBack(r)}>
                {busy === r.path ? "Restoring…" : "Bring back"}
              </button>
            </div>
          ))}
        </Card>
      )}
    </main>
  );
}
