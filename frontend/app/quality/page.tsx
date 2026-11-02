"use client";

// Quality Check: the submission gate on any .tex — placeholders, citations, numbers traced to results,
// figures, page budget, claim language, and the match with an example paper. Computed by the server.

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { useProject } from "@/lib/useProject";
import type { WorkspaceFile } from "@/lib/types";
import { btn, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Check { id: string; label: string; status: "pass" | "warn" | "fail" | "info"; detail: string;
  items: { line?: number; match: string; text?: string }[] }
interface Report { tex: string; checked_at: string; ready: boolean; counts: Record<string, number>; checks: Check[];
  profile: Record<string, unknown>; example: Record<string, number> | null; note: string }

const TONE: Record<Check["status"], string> = {
  pass: "bg-[#e3f3e8] text-[#1d6b3a]", warn: "bg-[#fdf3dc] text-[#7a5300]", fail: "bg-[#fbe7e5] text-[#8a1f17]", info: "bg-[#eeeeee] text-[#555]",
};

export default function QualityPage() {
  const { projects, projectId, setProjectId, error: pErr } = useProject();
  const [files, setFiles] = useState<string[]>([]);
  const [pdfs, setPdfs] = useState<string[]>([]);
  const [tex, setTex] = useState("");
  const [example, setExample] = useState("");
  const [pages, setPages] = useState("");
  const [refs, setRefs] = useState("40");
  const [online, setOnline] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!projectId) return;
    api<WorkspaceFile[]>(`/projects/${projectId}/files`).then((fs) => {
      const t = fs.map((f) => f.path).filter((p) => p.endsWith(".tex"));
      setFiles(t); setPdfs(fs.map((f) => f.path).filter((p) => p.endsWith(".pdf")));
      const pick = t.find((p) => p === tex) ?? t[0] ?? "";
      setTex(pick); setReport(null);
      if (pick) api<Report>(`/projects/${projectId}/quality?tex=${encodeURIComponent(pick)}`).then(setReport).catch(() => {});
    }).catch(setError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function uploadExample(f: File) {
    const fd = new FormData(); fd.append("file", f);
    const r = await api<{ path: string }>(`/projects/${projectId}/files?folder=uploads`, { method: "POST", body: fd });
    setPdfs((p) => [...new Set([...p, r.path])]); setExample(r.path);
  }

  async function run() {
    setBusy(true); setError(null);
    try {
      setReport(await post<Report>(`/projects/${projectId}/quality`, {
        tex, example_pdf: example || null, online, target_pages: pages ? Number(pages) : null, target_refs: refs ? Number(refs) : null }));
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8">
      <PageHeader title="Quality Check"
        sub="Is it ready to submit? Checks placeholders, references, numbers, figures, page count and wording." />
      <ErrorBox error={error || pErr} />

      <Card className="mb-6 p-6">
        <div className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium">Project
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal">
                {projects?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm font-medium">Manuscript (.tex)
              <select value={tex} onChange={(e) => setTex(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal">
                {files.length === 0 && <option value="">No .tex in this project</option>}
                {files.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
          </div>
          <div className="grid gap-1 text-sm font-medium">Example paper to match (optional)
            <div className="flex flex-wrap gap-2">
              <select value={example} onChange={(e) => setExample(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 font-normal">
                <option value="">None</option>
                {pdfs.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-line bg-white px-4 text-sm font-medium hover:border-[#8796a5]">
                Upload PDF
                <input type="file" accept=".pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadExample(f).catch(setError); }} />
              </label>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="grid gap-1 text-sm font-medium">Page limit
              <input type="number" min={1} value={pages} onChange={(e) => setPages(e.target.value)} placeholder="e.g. 12" className="rounded-lg border border-line px-3 py-2 font-normal" />
            </label>
            <label className="grid gap-1 text-sm font-medium">References (at least)
              <input type="number" min={0} value={refs} onChange={(e) => setRefs(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal" />
            </label>
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={online} onChange={(e) => setOnline(e.target.checked)} /> Look every reference up at Crossref/arXiv (slower)</label>
          </div>
          <div><button className={btn} disabled={busy || !tex} onClick={run}>{busy ? "Checking…" : "Run quality check"}</button></div>
        </div>
      </Card>

      {report && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${report.ready ? TONE.pass : TONE.fail}`}>
              {report.ready ? "No failing check" : `${report.counts.fail} failing check(s)`}</span>
            <span className="text-sm text-muted">{report.counts.warn} warning(s) · {report.tex} · {new Date(report.checked_at).toLocaleString()}</span>
            <Link className="ml-auto text-sm text-accent underline" href={`/loops?project=${projectId}`}>Fix with "Review and fix"</Link>
          </div>
          <div className="space-y-3">
            {report.checks.map((c) => (
              <Card key={c.id} className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase ${TONE[c.status]}`}>{c.status}</span>
                  <span className="font-semibold">{c.label}</span>
                  <span className="text-sm text-muted">{c.detail}</span>
                </div>
                {c.items.length > 0 && (
                  <ul className="mt-2 max-h-48 space-y-0.5 overflow-auto text-xs">
                    {c.items.map((it, i) => (
                      <li key={i} className="font-mono">{it.line ? <span className="text-faint">L{it.line} </span> : null}<b>{it.match}</b>{it.text ? <span className="text-muted"> — {it.text}</span> : null}</li>
                    ))}
                  </ul>
                )}
              </Card>
            ))}
          </div>
          {report.example && (
            <Card className="mt-4 p-4 text-sm">
              <b>Manuscript vs example:</b>{" "}
              {(["pages", "words", "figures", "tables", "references_approx"] as const).map((k) =>
                <span key={k} className="mr-3">{k.replace("_approx", "")}: {String(report.profile[k] ?? "—")} / {report.example![k]}</span>)}
            </Card>
          )}
          <p className="mt-4 text-xs text-faint">{report.note}</p>
        </>
      )}
    </main>
  );
}
