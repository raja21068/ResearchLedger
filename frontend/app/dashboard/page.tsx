"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SECTION_LABEL, type ProgressStep, type Project, type Run, type RunStatus, type Workflow } from "@/lib/types";
import { btn, Card, Empty, ErrorBox, PageHeader, RunBadge, timeAgo } from "@/components/ui";

interface Dashboard {
  counts: { projects: number; runs: number; running: number; artifacts: number; reviews: number };
  recent_projects: Project[];
  recent_runs: (Run & { project_title: string })[];
}

const DOT: Record<ProgressStep["state"], string> = {
  done: "bg-accent", running: "rl-pulse bg-[#3b6fd8]", not_started: "bg-[#c9d2da]",
};
const STATE_LABEL: Record<ProgressStep["state"], string> = { done: "Done", running: "Running", not_started: "Not started" };

export default function Dashboard() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [tools, setTools] = useState<Workflow[]>([]);
  const [projectId, setProjectId] = useState("");
  const [progress, setProgress] = useState<ProgressStep[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Dashboard>("/dashboard").then((x) => { setD(x); setProjectId(x.recent_projects[0]?.id ?? ""); }).catch(setError);
    api<Workflow[]>("/workflows").then(setTools).catch(() => {});
  }, []);
  useEffect(() => {
    if (projectId) api<ProgressStep[]>(`/projects/${projectId}/progress`).then(setProgress).catch(setError);
  }, [projectId]);

  const tiles: [string, number | undefined, string][] = [
    ["Projects", d?.counts.projects, "Research workspaces"],
    ["Agent runs", d?.counts.runs, d?.counts.running ? `${d.counts.running} running now` : "Execution history"],
    ["Evidence", d?.counts.artifacts, "Files produced by runs, hashed"],
    ["Reviews", d?.counts.reviews, "Peer-review runs"],
  ];
  const firstTool = (ids: string[]) => tools.find((t) => ids.includes(t.id))?.id ?? ids[0];

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title="Research overview" sub="Your research projects, workflows and scientific evidence. Every number comes from stored records."
        actions={<Link className={btn} href="/projects?new=1">New project</Link>} />
      <ErrorBox error={error} />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map(([label, n, hint]) => (
          <Card key={label} className="p-4">
            <div className="text-sm font-semibold">{label}</div>
            <div className="my-1.5 font-mono text-3xl">{n ?? "—"}</div>
            <div className="text-sm text-faint">{hint}</div>
          </Card>
        ))}
      </div>

      <Card className="mb-6 p-5">
        <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Active research workflow</h2>
          {d && d.recent_projects.length > 0 && (
            <select aria-label="Project" value={projectId} onChange={(e) => setProjectId(e.target.value)}
              className="min-h-9 rounded-lg border border-line bg-white px-2 text-sm">
              {d.recent_projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          )}
        </div>
        <p className="mb-3 text-sm text-muted">A project progresses through connected stages. A stage shows Done only when its output file exists.</p>
        {d && !d.recent_projects.length && <Empty title="No projects yet">Create a project, or open any tool below and press Generate.</Empty>}
        <ol className="divide-y divide-[#e6eaee]">
          {progress?.map((s) => (
            <li key={s.step}>
              <Link href={`/tools/${firstTool(s.workflows)}?project=${projectId}`}
                className="flex items-center gap-3 py-3 hover:text-accent">
                <span className="rounded-md bg-[#eef1f4] px-2 py-0.5 font-mono text-xs">{s.step}</span>
                <span className="flex-1 font-medium">{s.title}
                  {s.evidence.length > 0 && <span className="ml-2 font-mono text-xs text-faint">{s.evidence[0]}</span>}</span>
                <span className="text-xs text-faint">{STATE_LABEL[s.state]}</span>
                <span aria-hidden="true" className={`h-3 w-3 rounded-full ${DOT[s.state]}`} />
              </Link>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="mb-3 text-lg font-semibold">Tools</h2>
          {(Object.keys(SECTION_LABEL) as Workflow["section"][]).map((s) => (
            <div key={s} className="mb-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">{SECTION_LABEL[s]}</div>
              <div className="flex flex-wrap gap-2">
                {tools.filter((t) => t.section === s).map((t) => (
                  <Link key={t.id} href={`/tools/${t.id}`} className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-accent">{t.name}</Link>
                ))}
              </div>
            </div>
          ))}
        </Card>
        <Card className="p-5">
          <h2 className="mb-1 text-lg font-semibold">Agent activity</h2>
          <p className="mb-2 text-sm text-muted">Live and completed runs. Failed runs need your attention.</p>
          {d && !d.recent_runs.length && <Empty title="No runs yet">Open a tool and press Generate.</Empty>}
          <ul className="divide-y divide-[#e6eaee]">
            {d?.recent_runs.map((r) => (
              <li key={r.id}><Link href={`/projects/${r.project_id}?conv=${r.conversation_id}`} className="flex items-start justify-between gap-3 py-3 hover:text-accent">
                <span className="min-w-0"><span className="block truncate text-sm font-medium">{r.prompt.split("\n")[0]}</span>
                  <span className="block truncate text-xs text-faint">{r.project_title} · {timeAgo(r.created_at)}</span>
                  {r.error && <span className="block truncate text-xs text-[#7f1d1d]">{r.error}</span>}</span>
                <RunBadge status={r.status as RunStatus} />
              </Link></li>
            ))}
          </ul>
        </Card>
      </div>
    </main>
  );
}
