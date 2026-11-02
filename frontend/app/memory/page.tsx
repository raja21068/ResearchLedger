"use client";

// Research memory. Tab 1 "Memories": what earlier work found (failed directions, decisions, experiment results,
// strategies, literature), each with sources and history; agents read the active ones before every task; nothing is
// edited in place — a correction replaces a memory and the old version stays visible. Tab 2 "Project notes": the
// hand-written memory/research_memory.md.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { MemoryNotes } from "@/components/MemoryNotes";
import { btn, btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Memory {
  id: string; project_id: string | null; project: string | null; domain: string; title: string; content: string;
  status: string; origin: string; tags: string[]; supersedes: string | null; conflict_with: string | null;
  created_at: string; updated_at: string; sources?: number;
}
interface Detail extends Memory {
  evidence: { kind: string; ref: string; quote: string | null }[];
  history: { ts: string; actor: string; action: string }[];
  superseded_by: string | null;
}
interface Project { id: string; title: string }

const DOMAINS: [string, string][] = [["", "All"], ["failure", "Failures"], ["decision", "Decisions"],
  ["experiment", "Experiments"], ["strategy", "Strategies"], ["literature", "Literature"]];
const STATUS: [string, string][] = [["active", "Active"], ["proposed", "Proposed"], ["needs_review", "Possible conflict"],
  ["superseded", "Replaced"], ["rejected", "Rejected"], ["", "Everything"]];
const TONE: Record<string, string> = {
  failure: "bg-[#fbe4e4] text-[#7f1d1d]", decision: "bg-[#e6eefb] text-[#1e3a8a]", experiment: "bg-[#dff3e4] text-[#14532d]",
  strategy: "bg-[#f3ecdf] text-[#7a3a06]", literature: "bg-[#ece7f6] text-[#4c1d95]",
};
const ORIGIN: Record<string, string> = { system: "recorded automatically", user: "added by you", agent: "proposed by an agent" };

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function SourceLink({ kind, refText, projectId }: { kind: string; refText: string; projectId: string | null }) {
  const href = kind === "doi" ? `https://doi.org/${refText}` : kind === "arxiv" ? `https://arxiv.org/abs/${refText}`
    : kind === "url" && /^https?:\/\//.test(refText) ? refText
    : kind === "file" && projectId ? `/view/${projectId}?path=${encodeURIComponent(refText)}` : null;
  const label = <><span className="text-faint">{kind}:</span> <span className="font-mono text-xs">{refText}</span></>;
  return href ? <a className="text-accent underline" href={href} target="_blank" rel="noreferrer">{label}</a> : <span>{label}</span>;
}

function parseSources(text: string) {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    if (/^10\.\d{4,}\//.test(l)) return { kind: "doi", ref: l };
    if (/^\d{4}\.\d{4,5}(v\d+)?$/.test(l)) return { kind: "arxiv", ref: l };
    if (/^https?:\/\//.test(l)) return { kind: "url", ref: l };
    return { kind: "file", ref: l };
  });
}

function Memories() {
  const params = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState(params.get("project") ?? "");
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState("active");
  const [rows, setRows] = useState<Memory[] | null>(null);
  const [open, setOpen] = useState<Detail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ domain: "decision", title: "", content: "", sources: "", all: false });

  useEffect(() => { api<Project[]>("/projects").then(setProjects).catch(() => {}); }, []);

  const load = useCallback(() => {
    setError(null);
    const s = new URLSearchParams({ q, limit: "200" });
    if (project) s.set("project_id", project);
    if (domain) s.set("domain", domain);
    if (status) s.set("status", status);
    api<Memory[]>(`/memory?${s}`).then(setRows).catch(setError);
  }, [q, project, domain, status]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const show = useCallback((id: string) => {
    setEditing(false);
    api<Detail>(`/memory/${id}`).then(setOpen).catch(setError);
  }, []);
  useEffect(() => { const id = params.get("item"); if (id) show(id); }, [params, show]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); load(); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memories…" aria-label="Search memories"
          className="min-h-10 w-full rounded-lg border border-line px-3 text-sm sm:w-72" />
        <select aria-label="Project" className="min-h-10 rounded-lg border border-line px-2 text-sm" value={project} onChange={(e) => setProject(e.target.value)}>
          <option value="">All projects</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <select aria-label="Status" className="min-h-10 rounded-lg border border-line px-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <button className={`${btn2} ml-auto`} onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add a memory"}</button>
      </div>
      <div className="mb-4 flex flex-wrap gap-1">
        {DOMAINS.map(([v, l]) => (
          <button key={v} onClick={() => setDomain(v)} aria-pressed={domain === v}
            className={`rounded-full border px-3 py-1 text-sm ${domain === v ? "border-accent bg-accent text-white" : "border-line bg-white"}`}>{l}</button>
        ))}
      </div>
      <ErrorBox error={error} />

      {adding && (
        <Card className="mb-5 space-y-3 p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">Project
              <select className="mt-1 block w-full rounded-lg border border-line px-2 py-2" value={project} onChange={(e) => setProject(e.target.value)}>
                <option value="">Choose a project…</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </label>
            <label className="text-sm">Kind
              <select className="mt-1 block w-full rounded-lg border border-line px-2 py-2" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}>
                {DOMAINS.slice(1).map(([v, l]) => <option key={v} value={v}>{l.replace(/s$/, "")}</option>)}
              </select>
            </label>
            <label className="flex items-end gap-2 text-sm"><input type="checkbox" checked={form.all} onChange={(e) => setForm({ ...form, all: e.target.checked })} /> Useful for all projects</label>
          </div>
          <input className="w-full rounded-lg border border-line px-3 py-2 text-sm" placeholder="Title, e.g. Why we use scaffold splits"
            value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} aria-label="Title" />
          <textarea rows={4} className="w-full rounded-lg border border-line px-3 py-2 text-sm" placeholder="What should be remembered, and why"
            value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} aria-label="What to remember" />
          <textarea rows={2} className="w-full rounded-lg border border-line px-3 py-2 font-mono text-xs" placeholder="Sources, one per line: a DOI, an arXiv id, a URL, or a file path in the project"
            value={form.sources} onChange={(e) => setForm({ ...form, sources: e.target.value })} aria-label="Sources" />
          <button className={btn} disabled={busy || !project || !form.title.trim() || !form.content.trim()} onClick={() => act(async () => {
            await post(`/projects/${project}/memory`, { domain: form.domain, title: form.title, content: form.content,
              sources: parseSources(form.sources), all_projects: form.all });
            setForm({ domain: form.domain, title: "", content: "", sources: "", all: false }); setAdding(false);
          })}>Save memory</button>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          {!rows && !error && <p className="rl-pulse text-sm text-faint">Loading…</p>}
          {rows && rows.length === 0 && <Card className="p-5 text-sm text-muted">Nothing here yet. Finished idea rounds and experiments are recorded automatically; you can also add a memory yourself.</Card>}
          {rows?.map((m) => (
            <button key={m.id} onClick={() => show(m.id)}
              className={`block w-full rounded-xl border bg-white p-4 text-left hover:border-accent ${open?.id === m.id ? "border-accent" : "border-line"}`}>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={`rounded-full px-2 py-0.5 font-semibold ${TONE[m.domain]}`}>{m.domain}</span>
                {m.status !== "active" && <span className="rounded-full bg-[#f4f5f7] px-2 py-0.5 text-faint">{STATUS.find(([v]) => v === m.status)?.[1] ?? m.status}</span>}
                <span className="text-faint">{m.project ?? "All projects"} · {when(m.updated_at)} · {m.sources ?? 0} source(s)</span>
              </div>
              <div className="mt-1 font-semibold">{m.title}</div>
              <div className="mt-0.5 line-clamp-2 text-sm text-muted">{m.content}</div>
            </button>
          ))}
        </div>

        <div>
          {open ? (
            <Card className="sticky top-4 space-y-3 p-5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={`rounded-full px-2 py-0.5 font-semibold ${TONE[open.domain]}`}>{open.domain}</span>
                <span className="text-faint">{STATUS.find(([v]) => v === open.status)?.[1] ?? open.status} · {ORIGIN[open.origin] ?? open.origin}</span>
                <button className="ml-auto text-faint hover:text-ink" onClick={() => setOpen(null)} aria-label="Close">✕</button>
              </div>
              <h2 className="text-lg font-semibold">{open.title}</h2>
              <p className="whitespace-pre-wrap text-sm">{open.content}</p>
              {open.conflict_with && <p className="text-sm text-[#7a3a06]">May conflict with <button className="underline" onClick={() => show(open.conflict_with!)}>another memory</button>.</p>}
              {open.supersedes && <p className="text-sm text-faint">Replaces <button className="underline" onClick={() => show(open.supersedes!)}>an earlier version</button>.</p>}
              {open.superseded_by && <p className="text-sm text-faint">Replaced by <button className="underline" onClick={() => show(open.superseded_by!)}>a newer version</button>.</p>}
              <div>
                <div className="text-sm font-semibold">Sources</div>
                {open.evidence.length === 0 ? <p className="text-sm text-faint">No source recorded.</p> : (
                  <ul className="mt-1 space-y-1 text-sm">{open.evidence.map((e, i) => (
                    <li key={i}><SourceLink kind={e.kind} refText={e.ref} projectId={open.project_id} />{e.quote && <div className="text-xs text-faint">“{e.quote}”</div>}</li>
                  ))}</ul>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {["proposed", "needs_review"].includes(open.status) && (
                  <>
                    <button className={btn} disabled={busy} onClick={() => act(async () => { await post(`/memory/${open.id}/decision`, { approve: true }); show(open.id); })}>Remember this</button>
                    <button className={btn2} disabled={busy} onClick={() => act(async () => { await post(`/memory/${open.id}/decision`, { approve: false }); show(open.id); })}>Reject</button>
                  </>
                )}
                {["active", "needs_review", "proposed"].includes(open.status) && (
                  <button className={btn2} onClick={() => { setEditing(!editing); setDraft(open.content); }}>{editing ? "Cancel" : "Correct"}</button>
                )}
              </div>
              {editing && (
                <div className="space-y-2">
                  <textarea rows={5} className="w-full rounded-lg border border-line px-3 py-2 text-sm" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Corrected memory" />
                  <p className="text-xs text-faint">Saving creates a new version; this one is kept and marked as replaced.</p>
                  <button className={btn} disabled={busy || !draft.trim()} onClick={() => act(async () => {
                    const n = await post<Detail>(`/memory/${open.id}/correct`, { content: draft }); setEditing(false); show(n.id);
                  })}>Save correction</button>
                </div>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer text-faint">History ({open.history.length})</summary>
                <ul className="mt-1 space-y-0.5 text-xs text-faint">{open.history.map((h, i) => <li key={i}>{when(h.ts)} · {h.actor} · {h.action}</li>)}</ul>
              </details>
              {open.project_id && <Link className="text-sm text-accent underline" href={`/projects/${open.project_id}/home`}>Open the project</Link>}
            </Card>
          ) : (
            <Card className="p-5 text-sm text-muted">Pick a memory to see its sources and history.</Card>
          )}
        </div>
      </div>
    </div>
  );
}

function MemoryInner() {
  const [tab, setTab] = useState<"memories" | "notes">("memories");
  return (
    <main className="mx-auto max-w-[1200px] px-4 py-7 sm:px-8">
      <PageHeader title="Memory"
        sub="What earlier work found, with its sources. Agents read the active memories before every task; failed directions are recorded automatically so they are not repeated." />
      <div className="mb-5 flex gap-1 border-b border-line" role="tablist">
        {([["memories", "Memories"], ["notes", "Project notes"]] as const).map(([v, l]) => (
          <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === v ? "border-accent font-semibold" : "border-transparent text-muted"}`}>{l}</button>
        ))}
      </div>
      {tab === "memories" ? <Memories /> : <MemoryNotes />}
    </main>
  );
}

export default function MemoryPage() {
  return <Suspense><MemoryInner /></Suspense>;
}
