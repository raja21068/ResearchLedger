"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/lib/useProject";
import { Markdown } from "@/components/Markdown";
import { btn, btn2, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";

export default function MemoryPage() {
  const { projects, projectId, setProjectId, error: loadError } = useProject();
  const [text, setText] = useState("");
  const [saved, setSaved] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api<{ text: string }>(`/projects/${projectId}/memory`).then((m) => { setText(m.text); setSaved(m.text); })
      .catch(setError);
  }, [projectId]);

  async function save() {
    setBusy(true); setError(null);
    try {
      const m = await api<{ text: string }>(`/projects/${projectId}/memory`,
        { method: "PUT", body: JSON.stringify({ text }) });
      setText(m.text); setSaved(m.text); setEditing(false);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-7 sm:px-8">
      <PageHeader title="Research Memory"
        sub="Shared context for every agent in the project: your research question and decisions, plus a log the server appends after each run. Agents read it before they work."
        actions={projectId && (editing
          ? <><button className={btn2} onClick={() => { setText(saved); setEditing(false); }}>Cancel</button>
              <button className={btn} onClick={save} disabled={busy || text === saved}>{busy ? "Saving…" : "Save"}</button></>
          : <button className={btn} onClick={() => setEditing(true)}>Edit</button>)} />
      <ErrorBox error={loadError || error} />
      {projects && !projects.length && <Empty title="No projects yet"><Link className="text-accent underline" href="/projects?new=1">Create a project</Link></Empty>}
      {projects && projects.length > 0 && (
        <select aria-label="Project" value={projectId} onChange={(e) => { setProjectId(e.target.value); setEditing(false); }}
          className="mb-4 min-h-10 rounded-lg border border-line bg-white px-2 text-sm">
          {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
      )}
      {projectId && (
        <Card className="p-6">
          {editing
            ? <textarea aria-label="Research memory" value={text} onChange={(e) => setText(e.target.value)}
                className="min-h-[60vh] w-full rounded-lg border border-line p-3 font-mono text-sm" />
            : <Markdown text={text} />}
          <p className="mt-4 text-xs text-faint">Stored in the project at <span className="font-mono">memory/research_memory.md</span>.</p>
        </Card>
      )}
    </main>
  );
}
