"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Card, Empty, ErrorBox, PageHeader, RunBadge } from "@/components/ui";

export default function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { api<Run[]>(`/runs${status ? `?status=${status}` : ""}`).then(setRuns).catch(setError); }, [status]);

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title="Agent runs" sub="Every Claude Code run, with its state, timing and any error. Runs persist across page refreshes and server restarts." />
      <ErrorBox error={error} />
      <label className="mb-4 inline-flex items-center gap-2 text-sm">Status
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="min-h-10 rounded-lg border border-line bg-white px-2">
          <option value="">All</option>{["running", "succeeded", "failed", "cancelled"].map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      {runs && !runs.length && <Empty title="No runs recorded" />}
      {runs && runs.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs uppercase tracking-wider text-faint">
              {["Run", "Project", "Prompt", "Status", "Started", "Duration", "Error"].map((h) => <th key={h} className="px-3 py-2.5 font-semibold">{h}</th>)}
            </tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.id} className="border-b border-[#e6eaee] align-top">
                <td className="px-3 py-2.5 font-mono text-xs">{r.id}</td>
                <td className="px-3 py-2.5"><Link className="text-accent" href={`/projects/${r.project_id}`}>{r.project_title}</Link></td>
                <td className="max-w-[320px] truncate px-3 py-2.5" title={r.prompt}>{r.prompt}</td>
                <td className="px-3 py-2.5"><RunBadge status={r.status} /></td>
                <td className="whitespace-nowrap px-3 py-2.5 text-faint">{r.started_at ? new Date(r.started_at).toLocaleString() : "—"}</td>
                <td className="px-3 py-2.5 text-faint">{r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)} s` : "—"}</td>
                <td className="max-w-[260px] truncate px-3 py-2.5 text-[#7f1d1d]" title={r.error ?? ""}>{r.error ?? ""}</td>
              </tr>))}
            </tbody>
          </table>
        </Card>
      )}
    </main>
  );
}
