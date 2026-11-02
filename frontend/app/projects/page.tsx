"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Project } from "@/lib/types";
import { btn, btn2, Card, Empty, ErrorBox, PageHeader, timeAgo } from "@/components/ui";

function ProjectsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [kind, setKind] = useState<"paper" | "quick">(params.get("kind") === "quick" ? "quick" : "paper");
  const [creating, setCreating] = useState(params.get("new") === "1");
  const [form, setForm] = useState({ title: "", domain: "", description: "" });
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<Project[]>(`/projects?status=${showArchived ? "archived" : "active"}&kind=${kind}`).then(setProjects).catch(setError);
  }, [showArchived, kind]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError(null);
    try {
      const p = await post<Project>("/projects", form);
      router.push(`/projects/${p.id}`);
    } catch (err) { setError(err); setSaving(false); }
  }

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title={kind === "paper" ? "Papers" : "Quick jobs"}
        sub={kind === "paper" ? "Long projects that grow into a paper: stages, loops, checks and results in one place."
          : "One-off jobs — a review, a reference check, a score. Open one and choose Keep as a paper to move it to Papers."}
        actions={<>
          <div role="radiogroup" aria-label="Kind" className="flex rounded-lg bg-[#ecebe6] p-0.5 text-sm">
            {(["paper", "quick"] as const).map((k) => (
              <button key={k} role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
                className={`rounded-md px-3 py-1 ${kind === k ? "bg-white font-medium shadow-sm" : "text-muted"}`}>{k === "paper" ? "Papers" : "Quick jobs"}</button>
            ))}
          </div>
          <button className={btn2} onClick={() => setShowArchived(!showArchived)}>{showArchived ? "Show active" : "Show archived"}</button>
          <button className={btn} onClick={() => setCreating(true)}>New paper</button>
        </>} />
      <ErrorBox error={error} />

      {creating && (
        <Card className="mb-6 p-5">
          <form onSubmit={create} className="grid gap-4">
            <h2 className="text-lg font-semibold">New paper</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1 text-sm font-medium">Title
                <input required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="min-h-10 rounded-lg border border-line px-3 font-normal" placeholder="e.g. Brain tumour MRI robustness" />
              </label>
              <label className="grid gap-1 text-sm font-medium">Research domain
                <input maxLength={200} value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}
                  className="min-h-10 rounded-lg border border-line px-3 font-normal" placeholder="e.g. Medical imaging" />
              </label>
            </div>
            <label className="grid gap-1 text-sm font-medium">Description
              <textarea maxLength={4000} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="rounded-lg border border-line px-3 py-2 font-normal" placeholder="Research question, scope, target venue…" />
            </label>
            <div className="flex gap-2">
              <button className={btn} disabled={saving}>{saving ? "Creating…" : "Create and open"}</button>
              <button type="button" className={btn2} onClick={() => setCreating(false)}>Cancel</button>
            </div>
          </form>
        </Card>
      )}

      {projects && !projects.length && !creating && (
        <Empty title={showArchived ? "Nothing archived" : kind === "paper" ? "No papers yet" : "No quick jobs yet"}>
          {!showArchived && kind === "paper" && <button className="text-accent underline" onClick={() => setCreating(true)}>Start a paper</button>}
          {!showArchived && kind === "quick" && <Link className="text-accent underline" href="/">Start a quick job</Link>}
        </Empty>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects?.map((p) => (
          <Link key={p.id} href={`/projects/${p.id}`} className="rounded-xl border border-line bg-white p-4 hover:border-accent">
            <div className="font-semibold">{p.title}</div>
            {p.domain && <div className="mt-0.5 text-sm text-accent">{p.domain}</div>}
            <p className="mt-2 line-clamp-3 text-sm text-muted">{p.description || "No description."}</p>
            <div className="mt-3 text-xs text-faint">Updated {timeAgo(p.updated_at)} · <span className="font-mono">{p.id}</span></div>
          </Link>
        ))}
      </div>
    </main>
  );
}

export default function Projects() {
  return <Suspense><ProjectsInner /></Suspense>;
}
