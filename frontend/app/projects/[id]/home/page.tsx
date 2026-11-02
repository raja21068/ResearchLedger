"use client";

// Paper overview: everything about one paper on one page — where it stands, what needs you, what is working,
// its loops, documents and results — with one click to every place where work happens.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project, WorkspaceFile } from "@/lib/types";
import type { PaperView } from "@/lib/paper";
import type { LoopSummary } from "@/lib/loops";
import { STATUS_STYLE } from "@/lib/loops";
import { btn2, Card, ErrorBox, timeAgo } from "@/components/ui";

interface InboxItem { kind: string; project_id: string; stage?: string; summary?: string | null; error?: string | null;
  loop_id?: string; conversation_id?: string; paper?: string; status?: string }
interface Inbox { approve: InboxItem[]; retry: InboxItem[]; running: InboxItem[] }

const STAGE_TONE: Record<string, string> = {
  approved: "bg-[#e3f3e8] text-[#1d6b3a]", needs_review: "bg-[#fdf3dc] text-[#7a5300]", running: "bg-[#e8effc] text-[#24508f]",
  failed: "bg-[#fbe7e5] text-[#8a1f17]", incomplete: "bg-[#fbe7e5] text-[#8a1f17]", ready: "bg-white text-ink", locked: "bg-[#f1efe9] text-faint",
};
const STAGE_WORD: Record<string, string> = {
  approved: "done", needs_review: "check it", running: "working", failed: "failed", incomplete: "incomplete", ready: "next", locked: "later",
};

export default function PaperHome() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [paper, setPaper] = useState<PaperView | null | undefined>(undefined);
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [loops, setLoops] = useState<LoopSummary[]>([]);
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    api<Project>(`/projects/${id}`).then((p) => { setProject(p); setTitle((t) => t || p.title); }).catch(setError);
    api<PaperView | null>(`/projects/${id}/paper`).then(setPaper).catch(() => setPaper(null));
    api<Inbox>("/inbox").then(setInbox).catch(() => {});
    api<LoopSummary[]>(`/projects/${id}/loops`).then(setLoops).catch(() => {});
    api<WorkspaceFile[]>(`/projects/${id}/files`).then(setFiles).catch(() => {});
  }, [id]);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);

  async function rename() {
    if (!title.trim()) return;
    try { setProject(await api<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ title: title.trim() }) })); setEditing(false); }
    catch (e) { setError(e); }
  }

  const mine = (xs?: InboxItem[]) => (xs ?? []).filter((x) => x.project_id === id);
  const decisions = [...mine(inbox?.approve), ...mine(inbox?.retry)];
  const working = mine(inbox?.running);
  const link = (x: InboxItem) => x.loop_id ? `/projects/${id}/loops/${x.loop_id}`
    : x.conversation_id ? `/projects/${id}?conv=${x.conversation_id}` : `/projects/${id}/paper`;
  const docs = files.filter((f) => /\.(pdf|tex|docx)$/i.test(f.path) && !/^(loops|_inputs|control|memory|data|code)\//.test(f.path))
    .sort((a, b) => b.modified - a.modified).slice(0, 8);
  const results = paper?.results ?? paper?.collected;

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-7 sm:px-8">
      <ErrorBox error={error} />
      <div className="mb-1 text-sm text-faint"><Link href="/projects" className="hover:text-ink">Papers</Link></div>
      {editing ? (
        <form onSubmit={(e) => { e.preventDefault(); rename(); }} className="flex flex-wrap gap-2">
          <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} aria-label="Paper name"
            className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 font-serif text-2xl" />
          <button className={btn2}>Save</button>
          <button type="button" className={btn2} onClick={() => { setEditing(false); setTitle(project?.title ?? ""); }}>Cancel</button>
        </form>
      ) : (
        <h1 className="flex flex-wrap items-baseline gap-3 font-serif text-[28px] font-medium">
          {project?.title ?? "…"}
          <button onClick={() => setEditing(true)} className="font-sans text-sm text-accent underline">Rename</button>
        </h1>
      )}
      {paper && <p className="mt-1 text-sm text-muted">{paper.type_label} · {paper.venue_label}</p>}

      {/* Where it stands */}
      <Card className="mt-5 p-5">
        <h2 className="mb-3 text-sm font-semibold">Where it stands</h2>
        {paper === undefined ? <p className="text-sm text-faint">Loading…</p> : paper ? (
          <ol className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-8">
            {paper.stages.map((s) => (
              <li key={s.id}>
                <Link href={`/projects/${id}/paper#${s.id}`} title={s.purpose}
                  className={`block rounded-lg border border-line px-2 py-1.5 text-center text-xs ${STAGE_TONE[s.status] ?? ""}`}>
                  <span className="block truncate font-medium">{s.title}</span>
                  <span className="block opacity-80">{STAGE_WORD[s.status] ?? s.status}</span>
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted">No writing plan yet. <Link className="text-accent underline" href={`/projects/${id}/paper`}>Start the paper stages</Link> when you are ready to write — or just chat with the agent.</p>
        )}
        {results && <p className="mt-3 text-sm text-muted">Results measured: <b className="text-ink">{results.measured}</b> of {results.slots}</p>}
      </Card>

      {/* What needs you */}
      <Card className={`mt-4 p-5 ${decisions.length ? "border-[#f0d9a8]" : ""}`}>
        <h2 className="mb-2 text-sm font-semibold">{decisions.length ? `Needs you (${decisions.length})` : "Nothing needs you right now"}</h2>
        <ul className="space-y-2">
          {decisions.map((d, i) => (
            <li key={i} className="flex flex-wrap items-start gap-2 text-sm">
              <span className="min-w-0 flex-1"><b>{d.stage}</b>{(d.summary || d.error) && <span className="block truncate text-muted">{d.error ?? d.summary}</span>}</span>
              <Link className={btn2} href={link(d)}>Open</Link>
            </li>
          ))}
        </ul>
        {working.length > 0 && (
          <div className="mt-3 border-t border-line pt-3 text-sm">
            {working.map((w, i) => <Link key={i} href={link(w)} className="flex items-center gap-2 py-0.5 hover:underline">
              <span className="rl-pulse h-2 w-2 rounded-full bg-[#3b6fd8]" />{w.stage}</Link>)}
          </div>
        )}
      </Card>

      {/* Do something */}
      <div className="mt-4 flex flex-wrap gap-2">
        <Link className={btn2} href={`/projects/${id}`}>Chat with the agent</Link>
        <Link className={btn2} href={`/projects/${id}/paper`}>Writing stages</Link>
        <Link className={btn2} href={`/loops?project=${id}`}>Review and fix / improve idea</Link>
        <Link className={btn2} href={`/loops?project=${id}&type=experiment`}>Run experiments</Link>
        <Link className={btn2} href={`/projects/${id}/lab`}>Experiment records</Link>
        <Link className={btn2} href={`/projects/${id}/evidence`}>Evidence</Link>
        <Link className={btn2} href={`/projects/${id}/library`}>Paper library</Link>
        <Link className={btn2} href={`/quality?project=${id}`}>Submission check</Link>
        <Link className={btn2} href={`/trash/${id}`}>Trash</Link>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-2 text-sm font-semibold">Loops</h2>
          {loops.length === 0 && <p className="text-sm text-faint">None yet.</p>}
          <ul className="space-y-1.5 text-sm">
            {loops.slice(0, 6).map((l) => (
              <li key={l.id}><Link href={`/projects/${id}/loops/${l.id}`} className="flex items-center gap-2 hover:underline">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_STYLE[l.status][1]}`}>{STATUS_STYLE[l.status][0]}</span>
                <span className="min-w-0 flex-1 truncate">{l.label}</span>
                <span className="text-xs text-faint">{timeAgo(l.created_at)}</span></Link></li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <h2 className="mb-2 text-sm font-semibold">Documents</h2>
          {docs.length === 0 && <p className="text-sm text-faint">No manuscript yet.</p>}
          <ul className="space-y-1 text-sm">
            {docs.map((f) => (
              <li key={f.path}><Link target="_blank" href={`/view/${id}?path=${encodeURIComponent(f.path)}`} className="flex gap-2 hover:underline">
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{f.path}</span>
                <span className="text-xs text-faint">{timeAgo(new Date(f.modified * 1000).toISOString())}</span></Link></li>
            ))}
          </ul>
        </Card>
      </div>
    </main>
  );
}
