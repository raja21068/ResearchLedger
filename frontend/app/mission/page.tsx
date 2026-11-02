"use client";

// Mission control: every task in one place — what is running (and its last word and heartbeat), what is queued
// and what it waits for, what was interrupted or failed, what needs your decision, and each paper's stage pipeline.
// Only real controls are shown: tasks can be cancelled, not paused.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn2, Card, ErrorBox, PageHeader, timeAgo } from "@/components/ui";

interface Job { id: string; state: string; seconds?: number; command?: string }
interface Task {
  id: string; label: string; project_id: string; project: string; state: string; agent: boolean;
  created_at: string; started_at: string | null; finished_at: string | null; elapsed_s: number | null; error: string | null;
  link: string; last: { ts: string; text: string } | null; can_cancel: boolean; waiting_for?: string; waiting_s?: number;
  heartbeat_s?: number; jobs?: Job[];
}
interface Mission {
  worker: { executor: string; worker_connected: boolean; worker_state: string; queued: number; last_poll_seconds_ago: number | null };
  needs_you: { count: number; items: { project: string; stage: string; paper?: string; kind: string }[] };
  tasks: Record<"running" | "queued" | "interrupted" | "failed" | "completed" | "cancelled", Task[]>;
  pipelines: { project_id: string; project: string; topic: string | null; stages: { id: string; title: string; status: string }[] }[];
  counts: Record<string, number>; recent_hours: number;
}

const STAGE_TONE: Record<string, string> = {
  approved: "border-[#b8e0d2] bg-[#effaf6] text-[#14532d]", running: "border-accent bg-white text-ink",
  needs_review: "border-[#f0dfb0] bg-[#fffaf0] text-[#7a4b06]", failed: "border-[#f0c4c4] bg-[#fdf1f1] text-[#7f1d1d]",
  incomplete: "border-[#f0c4c4] bg-[#fdf1f1] text-[#7f1d1d]", ready: "border-line bg-white text-muted", locked: "border-line bg-[#f6f5f1] text-faint",
};
const STAGE_WORD: Record<string, string> = { approved: "done", running: "working", needs_review: "needs you", failed: "failed",
  incomplete: "incomplete", ready: "ready", locked: "waiting" };

function dur(s: number | null | undefined) {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function TaskCard({ t, onCancel }: { t: Task; onCancel: (t: Task) => void }) {
  const done = (t.jobs ?? []).filter((j) => j.state === "done" || j.state === "failed").length;
  return (
    <Card className={`p-4 ${t.state === "running" ? "border-accent" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${t.agent ? "bg-[#ece7f6] text-[#4c1d95]" : "bg-[#e6eefb] text-[#1e3a8a]"}`}>{t.agent ? "agent" : "server run"}</span>
        <b className="text-sm">{t.label}</b>
        <span className="ml-auto text-xs text-faint">{t.project}</span>
      </div>
      {t.last && <p className="mt-1 line-clamp-2 text-sm text-muted">{t.last.text}</p>}
      {t.jobs && t.jobs.length > 0 && (
        <div className="mt-2">
          <div className="h-1.5 rounded-full bg-[#e9ecef]"><div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.round((100 * done) / t.jobs.length)}%` }} /></div>
          <div className="mt-1 flex flex-wrap gap-1 text-[11px]">{t.jobs.map((j) => <span key={j.id} className="rounded bg-[#f6f5f1] px-1.5">{j.id}: {j.state}</span>)}</div>
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-faint">
        {t.state === "running" && <span>working for {dur(t.elapsed_s)}</span>}
        {t.state === "queued" && <span>waiting {dur(t.waiting_s)}{t.waiting_for ? ` for ${t.waiting_for}` : ""}</span>}
        {t.heartbeat_s != null && <span className={t.heartbeat_s > 600 ? "text-[#7a4b06]" : ""}>last heartbeat {dur(t.heartbeat_s)} ago</span>}
        {["completed", "failed", "interrupted", "cancelled"].includes(t.state) && <span>{timeAgo(t.finished_at ?? t.created_at)}{t.elapsed_s != null ? ` · took ${dur(t.elapsed_s)}` : ""}</span>}
      </div>
      {t.error && t.state !== "completed" && (
        <p className="mt-1 text-xs text-[#7f1d1d]">{t.state === "interrupted" ? "The server restarted while this ran. Nothing was retried automatically; start it again from its page." : t.error}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <Link className={btn2} href={t.link}>Open</Link>
        {t.can_cancel && <button className={btn2} onClick={() => onCancel(t)}>Cancel</button>}
      </div>
    </Card>
  );
}

export default function MissionPage() {
  const [m, setM] = useState<Mission | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(() => { api<Mission>("/mission").then((x) => { setM(x); setError(null); }).catch(setError); }, []);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]);

  async function cancel(t: Task) {
    if (!window.confirm(`Cancel “${t.label}” in ${t.project}?`)) return;
    try { await post(`/runs/${t.id}/cancel`); load(); } catch (e) { setError(e); }
  }

  const w = m?.worker;
  const tiles: [string, string, number][] = m ? [
    ["Needs you", "/inbox", m.counts.needs_you], ["Running", "#running", m.counts.running], ["Queued", "#queued", m.counts.queued],
    ["Interrupted", "#problems", m.counts.interrupted], [`Failed (${m.recent_hours}h)`, "#problems", m.counts.failed],
    [`Completed (${m.recent_hours}h)`, "#done", m.counts.completed],
  ] : [];

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-7 sm:px-8">
      <PageHeader title="Mission control" sub="Everything the agents and the server are doing, what waits, and what needs you. Updates every few seconds."
        actions={w && (
          <span className={`rounded-full px-3 py-1 text-sm ${w.worker_connected ? "bg-[#dff3e4] text-[#14532d]" : "bg-[#fbe4e4] text-[#7f1d1d]"}`}>
            {w.executor === "bridge" ? `Claude app worker: ${w.worker_state === "busy" ? "working" : w.worker_connected ? "connected" : "not connected"}` : "Agents run with claude.exe"}
          </span>
        )} />
      <ErrorBox error={error} />
      {w && w.executor === "bridge" && !w.worker_connected && (m?.counts.queued ?? 0) > 0 && (
        <p className="mb-4 rounded-lg border border-[#f0dfb0] bg-[#fffaf0] px-3 py-2 text-sm">Tasks are waiting for the Claude app worker. In the Claude app, open a Code session in this folder and run <span className="font-mono">/rl-worker</span>.</p>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map(([l, href, n]) => (
          <Link key={l} href={href} className="rounded-xl border border-line bg-white p-3 hover:border-accent">
            <div className="text-2xl font-semibold">{n}</div><div className="text-xs text-muted">{l}</div>
          </Link>
        ))}
      </div>

      {m && m.needs_you.count > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 font-semibold">Needs you</h2>
          <Card className="divide-y divide-line">
            {m.needs_you.items.map((x, i) => (
              <Link key={i} href="/inbox" className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm hover:bg-[#f6f5f1]">
                <b>{x.stage}</b><span className="truncate text-muted">{x.paper ?? ""}</span><span className="ml-auto text-xs text-faint">{x.project}</span>
              </Link>
            ))}
          </Card>
        </section>
      )}

      {m && m.pipelines.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 font-semibold">Paper pipelines</h2>
          <div className="space-y-3">
            {m.pipelines.map((p) => (
              <Card key={p.project_id} className="p-4">
                <Link href={`/projects/${p.project_id}/paper`} className="text-sm font-semibold hover:underline">{p.project}</Link>
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  {p.stages.map((s, i) => (
                    <span key={s.id} className="flex items-center gap-1">
                      <span className={`rounded-lg border px-2 py-1 text-xs ${STAGE_TONE[s.status] ?? "border-line"}`} title={s.status}>
                        {s.title} <span className="opacity-70">· {STAGE_WORD[s.status] ?? s.status}</span>
                      </span>
                      {i < p.stages.length - 1 && <span className="text-faint">→</span>}
                    </span>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section id="running" className="mb-6">
        <h2 className="mb-2 font-semibold">Running</h2>
        <div className="grid gap-3 md:grid-cols-2">{m?.tasks.running.map((t) => <TaskCard key={t.id} t={t} onCancel={cancel} />)}</div>
        {m && !m.tasks.running.length && <p className="text-sm text-faint">Nothing is running.</p>}
      </section>

      <section id="queued" className="mb-6">
        <h2 className="mb-2 font-semibold">Queued</h2>
        <div className="grid gap-3 md:grid-cols-2">{m?.tasks.queued.map((t) => <TaskCard key={t.id} t={t} onCancel={cancel} />)}</div>
        {m && !m.tasks.queued.length && <p className="text-sm text-faint">Nothing is waiting.</p>}
      </section>

      <section id="problems" className="mb-6">
        <h2 className="mb-2 font-semibold">Interrupted or failed</h2>
        <div className="grid gap-3 md:grid-cols-2">{m && [...m.tasks.interrupted, ...m.tasks.failed].map((t) => <TaskCard key={t.id} t={t} onCancel={cancel} />)}</div>
        {m && !m.tasks.interrupted.length && !m.tasks.failed.length && <p className="text-sm text-faint">No problems in the last {m.recent_hours} hours.</p>}
      </section>

      <section id="done">
        <button className="mb-2 font-semibold hover:underline" onClick={() => setShowDone(!showDone)}>
          {showDone ? "▾" : "▸"} Completed and cancelled ({(m?.tasks.completed.length ?? 0) + (m?.tasks.cancelled.length ?? 0)})
        </button>
        {showDone && (
          <Card className="divide-y divide-line">
            {m && [...m.tasks.completed, ...m.tasks.cancelled].map((t) => (
              <Link key={t.id} href={t.link} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm hover:bg-[#f6f5f1]">
                <span className={t.state === "completed" ? "text-[#14532d]" : "text-faint"}>{t.state === "completed" ? "✓" : "–"}</span>
                <b>{t.label}</b><span className="text-muted">{t.project}</span>
                <span className="ml-auto text-xs text-faint">{timeAgo(t.finished_at ?? t.created_at)}{t.elapsed_s != null ? ` · ${dur(t.elapsed_s)}` : ""}</span>
              </Link>
            ))}
          </Card>
        )}
      </section>
    </main>
  );
}
