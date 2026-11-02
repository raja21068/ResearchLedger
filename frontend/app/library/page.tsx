"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project, WorkspaceFile } from "@/lib/types";
import { Card, Empty, ErrorBox, PageHeader } from "@/components/ui";

const GROUPS: [string, (f: WorkspaceFile) => boolean][] = [
  ["Documents (PDF / Word)", (f) => f.kind === "pdf" || f.kind === "docx"],
  ["Manuscript sources", (f) => /\.(tex|md|bib)$/i.test(f.path)],
  ["Data & results", (f) => /\.(csv|tsv|json|xlsx)$/i.test(f.path)],
  ["Images", (f) => f.kind === "image"],
  ["Other", () => true],
];

export default function Library() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [files, setFiles] = useState<WorkspaceFile[] | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Project[]>("/projects").then((ps) => { setProjects(ps); setProjectId(ps[0]?.id ?? ""); }).catch(setError);
  }, []);
  useEffect(() => {
    if (projectId) api<WorkspaceFile[]>(`/projects/${projectId}/files`).then(setFiles).catch(setError);
  }, [projectId]);

  const shown = (files ?? []).filter((f) => f.path.toLowerCase().includes(q.toLowerCase()));
  const used = new Set<string>();
  const grouped = GROUPS.map(([label, test]) => {
    const items = shown.filter((f) => !used.has(f.path) && test(f));
    items.forEach((f) => used.add(f.path));
    return [label, items] as const;
  }).filter(([, items]) => items.length);

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title="My Library" sub="Every file in your project workspaces: uploads and everything the agents produced." />
      <ErrorBox error={error} />
      {projects && !projects.length && <Empty title="No projects yet"><Link className="text-accent underline" href="/projects?new=1">Create a project</Link></Empty>}
      {projects && projects.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <select aria-label="Project" value={projectId} onChange={(e) => setProjectId(e.target.value)}
            className="min-h-10 rounded-lg border border-line bg-white px-2 text-sm">
            {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
          <input aria-label="Search files" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search files"
            className="min-h-10 min-w-[220px] flex-1 rounded-lg border border-line bg-white px-3 text-sm" />
        </div>
      )}
      {files && !files.length && <Empty title="This project has no files yet" />}
      <div className="grid gap-4">
        {grouped.map(([label, items]) => (
          <Card key={label} className="p-5">
            <h2 className="mb-2 font-semibold">{label} <span className="text-faint">({items.length})</span></h2>
            <ul className="divide-y divide-[#e6eaee]">
              {items.map((f) => (
                <li key={f.path} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <Link href={`/view/${projectId}?path=${encodeURIComponent(f.path)}`} target="_blank" className="font-mono text-accent">{f.path}</Link>
                  <span className="text-xs text-faint">{(f.size / 1024).toFixed(1)} KB · {new Date(f.modified * 1000).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </main>
  );
}
