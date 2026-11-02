"use client";

// Approvals: every decision the user has to make, across all projects, one click each.
// Approving a paper stage lets Autopilot start the next one by itself.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { BridgeBanner } from "@/components/BridgeStatus";
import { Markdown } from "@/components/Markdown";
import { btn, btn2, Empty, ErrorBox, PageHeader } from "@/components/ui";

interface Item {
  kind: "paper_stage" | "plan" | "manual_start" | "run" | "loop" | "memory"; project_id: string; project: string; paper: string;
  stage: string; stage_id?: string; step?: string; summary?: string | null; outputs?: string[]; next?: string | null;
  autopilot?: boolean; conversation_id?: string; steps?: string[]; blocked?: boolean; status?: string; error?: string | null;
  run_id?: string; loop_id?: string; loop_state?: "finished" | "paused"; loop_type?: string; key?: string; memory_id?: string;
}

function DismissButton({ item, onDone }: { item: Item; onDone: () => void }) {
  if (!item.key) return null;
  return (
    <button className="ml-auto text-xs text-faint hover:text-ink" title="Hide this. It comes back if anything about it changes."
      onClick={() => post("/inbox/dismiss", { key: item.key }).then(onDone).catch(() => {})}>Dismiss</button>
  );
}
interface Inbox { approve: Item[]; retry: Item[]; running: Item[]; counts: { approve: number; retry: number; running: number } }

export default function InboxPage() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => { api<Inbox>("/inbox").then(setInbox).catch(setError); }, []);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  return (
    <main className="mx-auto max-w-[900px] px-4 py-8 sm:px-8">
      <PageHeader title="Decisions" sub="What is waiting for you. Approve and the work continues; dismiss what you don't need." />
      <ErrorBox error={error} />
      {inbox && inbox.counts.approve + inbox.counts.retry + inbox.counts.running === 0 && (
        <Empty title="Nothing needs you right now">Start something from <Link className="text-accent underline" href="/">New task</Link> or <Link className="text-accent underline" href="/paper">Paper Studio</Link>.</Empty>
      )}

      {inbox && inbox.approve.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-[.1em] text-faint">Needs you · {inbox.approve.length}</h2>
          <div className="space-y-3">{inbox.approve.map((it, i) => <ApproveCard key={i} item={it} onDone={load} />)}</div>
        </section>
      )}
      {inbox && inbox.retry.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-[.1em] text-faint">Did not finish · {inbox.retry.length}</h2>
          <div className="space-y-3">{inbox.retry.map((it, i) => <RetryCard key={i} item={it} onDone={load} />)}</div>
        </section>
      )}
      {inbox && inbox.running.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-[.1em] text-faint">Working now · {inbox.running.length}</h2>
          <div className="mb-3"><BridgeBanner waiting /></div>
          <ul className="divide-y divide-line rounded-xl border border-line bg-white">
            {inbox.running.map((it, i) => (
              <li key={i}>
                <Link href={it.kind === "paper_stage" ? `/projects/${it.project_id}/paper` : it.kind === "loop" ? `/projects/${it.project_id}/loops/${it.loop_id}` : `/projects/${it.project_id}?conv=${it.conversation_id}`}
                  className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-[#f7f5f1]">
                  <span className="rl-pulse h-2.5 w-2.5 flex-none rounded-full bg-[#3b6fd8]" />
                  <span className="min-w-0 flex-1 truncate"><b>{it.stage}</b> · {it.paper}</span>
                  <span className="text-xs text-faint">{it.status === "queued" ? "waiting for the Claude app" : "running"}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function Header({ item }: { item: Item }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <div className="text-xs text-faint">{item.project}{item.step ? ` · step ${item.step}` : ""}</div>
        <div className="text-lg font-semibold">{item.stage}</div>
        {item.paper && item.paper !== item.project && <div className="truncate text-sm text-muted">{item.paper}</div>}
      </div>
      <Link className="text-sm text-accent underline" href={item.kind === "memory" ? `/memory?item=${item.memory_id}` : item.kind === "plan" ? `/projects/${item.project_id}?conv=${item.conversation_id}` : item.kind === "loop" ? `/projects/${item.project_id}/loops/${item.loop_id}` : `/projects/${item.project_id}/paper`}>Open</Link>
    </div>
  );
}

function ApproveCard({ item, onDone }: { item: Item; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [open, setOpen] = useState(false);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); onDone(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  const base = `/projects/${item.project_id}/paper/stages/${item.stage_id}`;

  return (
    <article className="rounded-2xl border border-line bg-white p-5">
      <Header item={item} />
      {item.summary && (
        <div className={`mt-3 overflow-hidden text-sm ${open ? "" : "max-h-40"} relative`}>
          <Markdown text={item.summary} />
          {!open && <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white" />}
        </div>
      )}
      {item.summary && item.summary.length > 300 && (
        <button className="mt-1 text-xs text-accent" onClick={() => setOpen(!open)}>{open ? "Show less" : "Show more"}</button>
      )}
      {item.steps && (
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">{item.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
      )}
      {item.outputs && item.outputs.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {item.outputs.map((o) => (
            <Link key={o} target="_blank" href={`/view/${item.project_id}?path=${encodeURIComponent(o)}`}
              className="rounded-lg border border-line px-2.5 py-1 font-mono text-xs text-accent hover:border-accent">{o}</Link>
          ))}
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {item.kind === "paper_stage" && (
          <>
            <button className={btn} disabled={busy} onClick={() => act(() => post(`${base}/approve`))}>
              {item.next && item.autopilot ? `Approve → start ${item.next}` : "Approve"}
            </button>
            <button className={btn2} onClick={() => setAsking(!asking)}>Ask for changes</button>
          </>
        )}
        {item.kind === "manual_start" && (
          <button className={btn} disabled={busy} onClick={() => act(() => post(`${base}/run`, { notes: "Started from Approvals." }))}>Run experiments on this PC</button>
        )}
        {item.kind === "loop" && item.loop_state === "finished" && (
          <>
            <button className={btn} disabled={busy} onClick={() => act(() => post(`/projects/${item.project_id}/loops/${item.loop_id}/accept`))}>Accept result</button>
            <button className={btn2} disabled={busy} onClick={() => act(() => post(`/projects/${item.project_id}/loops/${item.loop_id}/continue`))}>One more round</button>
          </>
        )}
        {item.kind === "loop" && item.loop_state === "paused" && (
          <button className={btn} disabled={busy} onClick={() => act(() => post(`/projects/${item.project_id}/loops/${item.loop_id}/continue`))}>Continue</button>
        )}
        {item.kind === "memory" && (
          <>
            <button className={btn} disabled={busy} onClick={() => act(() => post(`/memory/${item.memory_id}/decision`, { approve: true }))}>Remember this</button>
            <button className={btn2} disabled={busy} onClick={() => act(() => post(`/memory/${item.memory_id}/decision`, { approve: false }))}>Reject</button>
          </>
        )}
        {item.kind === "plan" && (
          <button className={btn} disabled={busy || item.blocked} onClick={() => act(() => post(`/conversations/${item.conversation_id}/plan/approve`))}>
            Approve plan and run
          </button>
        )}
        <DismissButton item={item} onDone={onDone} />
      </div>
      {asking && (
        <div className="mt-3 space-y-2">
          <textarea rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)} aria-label="What should change"
            placeholder="What should change?" className="w-full rounded-lg border border-line px-3 py-2 text-sm" />
          <button className={btn} disabled={busy || !feedback.trim()} onClick={() => act(() => post(`${base}/run`, { feedback }))}>Redo with my changes</button>
        </div>
      )}
      {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}
    </article>
  );
}

function RetryCard({ item, onDone }: { item: Item; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <article className="rounded-2xl border border-[#ecd0cc] bg-white p-5">
      <Header item={item} />
      <p className="mt-2 whitespace-pre-wrap break-words text-sm text-[#7f1d1d]">{item.error}</p>
      <div className="mt-3 flex items-center gap-2">
        {item.kind === "loop" ? (
          <button className={btn} disabled={busy} onClick={async () => {
            setBusy(true); setError(null);
            try { await post(`/projects/${item.project_id}/loops/${item.loop_id}/retry`); onDone(); }
            catch (e) { setError(e); } finally { setBusy(false); }
          }}>Try again</button>
        ) : item.kind === "paper_stage" ? (
          <button className={btn} disabled={busy} onClick={async () => {
            setBusy(true); setError(null);
            try { await post(`/projects/${item.project_id}/paper/stages/${item.stage_id}/run`, { notes: "Retry from Approvals." }); onDone(); }
            catch (e) { setError(e); } finally { setBusy(false); }
          }}>Try again</button>
        ) : (
          <Link className={btn2} href={`/projects/${item.project_id}?conv=${item.conversation_id}`}>Open the chat</Link>
        )}
        <DismissButton item={item} onDone={onDone} />
      </div>
      {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}
    </article>
  );
}
