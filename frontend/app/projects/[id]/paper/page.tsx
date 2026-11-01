"use client";

// Paper Studio for one paper: stage rail on the left, the selected stage in the middle
// (what it uses, what it reads, what it produces, run / approve / ask for changes),
// and the agent's live checklist and steps while it works.

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { engineName, STAGE_LABEL, type PaperStage, type PaperView, type RefReport } from "@/lib/paper";
import type { Conversation, RunEvent } from "@/lib/types";
import { BridgeBanner } from "@/components/BridgeStatus";
import { Markdown } from "@/components/Markdown";
import { btn, btn2, ErrorBox } from "@/components/ui";

export default function PaperStudio({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [paper, setPaper] = useState<PaperView | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [notes, setNotes] = useState("");
  const [feedback, setFeedback] = useState("");
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [missing, setMissing] = useState(false);
  const [refs, setRefs] = useState<RefReport | null>(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => { api<RefReport | null>(`/projects/${id}/paper/references`).then(setRefs).catch(() => {}); }, [id]);
  async function checkRefs() {
    setChecking(true); setError(null);
    try { setRefs(await post<RefReport>(`/projects/${id}/paper/check-references`)); } catch (e) { setError(e); }
    finally { setChecking(false); }
  }

  const load = useCallback(async () => {
    try {
      const v = await api<PaperView | null>(`/projects/${id}/paper`);
      if (!v) { setMissing(true); return; }
      setPaper(v);
      setSelected((cur) => cur ?? (v.stages.find((s) => s.status !== "approved") ?? v.stages.at(-1))!.id);
    } catch (e) { setError(e); }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const stage = paper?.stages.find((s) => s.id === selected) ?? null;
  const running = paper?.stages.some((s) => s.status === "running");

  // While anything runs, refresh the stage view and the selected run's events.
  const loadEvents = useCallback(async () => {
    if (!paper || !stage?.run_id) { setEvents([]); return; }
    try {
      const c = await api<Conversation>(`/conversations/${paper.conversation_id}`);
      setEvents(c.runs?.find((r) => r.id === stage.run_id)?.events ?? []);
    } catch { /* keep the last events */ }
  }, [paper, stage?.run_id]);
  useEffect(() => { loadEvents(); }, [loadEvents]);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => { load(); loadEvents(); }, 4000);
    return () => clearInterval(t);
  }, [running, load, loadEvents]);

  async function act(path: string, body?: unknown) {
    setBusy(true); setError(null);
    try { setPaper(await post<PaperView>(`/projects/${id}/paper/${path}`, body)); setNotes(""); setFeedback(""); setAsking(false); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }

  if (missing) {
    return (
      <main className="mx-auto max-w-[700px] px-4 py-10">
        <h1 className="font-serif text-2xl font-semibold">This project has no paper yet</h1>
        <p className="mt-2 text-muted">Start one from <Link className="text-accent underline" href="/paper">Paper Studio</Link>.</p>
      </main>
    );
  }
  if (!paper) return <main className="p-8"><ErrorBox error={error} />{!error && <p className="rl-pulse text-faint">Loading…</p>}</main>;

  const todos = [...events].reverse().find((e) => e.kind === "todos")?.payload.items as { content: string; status: string }[] | undefined;
  const steps = events.filter((e) => e.kind === "tool_use");
  const reply = [...events].reverse().find((e) => e.kind === "assistant_text");
  const errors = events.filter((e) => e.kind === "error");

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-8">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm text-faint"><Link href="/paper" className="hover:text-ink">Paper Studio</Link> / {paper.type_label} · {paper.venue_label}</div>
          <h1 className="mt-1 font-serif text-2xl font-semibold">{paper.topic || "Untitled paper"}</h1>
        </div>
        <Link className={btn2} href={`/projects/${id}?conv=${paper.conversation_id}`}>Open the chat for this paper</Link>
      </div>

      <div className="flex flex-col gap-6 md:flex-row">
        {/* Stage rail */}
        <ol className="flex-none space-y-1 md:w-64">
          {paper.stages.map((s, i) => (
            <li key={s.id}>
              <button onClick={() => setSelected(s.id)} aria-current={s.id === selected}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left ${s.id === selected ? "bg-white shadow-sm ring-1 ring-line" : "hover:bg-[#ecebe6]"}`}>
                <StepDot status={s.status} n={i + 1} />
                <span className="min-w-0">
                  <span className={`block text-sm font-medium ${s.status === "locked" ? "text-faint" : ""}`}>{s.title}</span>
                  <span className="block text-xs text-faint">{STAGE_LABEL[s.status][0]}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>

        {/* Selected stage */}
        {stage && (
          <section className="min-w-0 flex-1 space-y-4">
            <div className="rounded-2xl border border-line bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-xl font-semibold">{stage.title}</h2>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STAGE_LABEL[stage.status][1]}`}>{STAGE_LABEL[stage.status][0]}</span>
              </div>
              <p className="mt-1 text-muted">{stage.purpose}</p>

              <div className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
                <FileGroup title="Uses your engines" items={stage.engines.map((e, i) => ({ label: engineName(e), ok: stage.engines_present[i], title: e }))} />
                <FileGroup title="Reads" items={stage.reads.map((r) => ({ label: r }))} empty="Nothing (first stage)" />
                <div>
                  <div className="mb-1 font-semibold">Produces</div>
                  <ul className="space-y-1">
                    {stage.outputs_found.map((o) => (
                      <li key={o.path} className="flex items-center gap-2">
                        <span className={o.exists ? "text-accent" : "text-faint"}>{o.exists ? "✓" : "○"}</span>
                        {o.exists
                          ? <Link className="truncate font-mono text-xs text-accent underline" target="_blank" href={`/view/${id}?path=${encodeURIComponent(o.path)}`}>{o.path}</Link>
                          : <span className="truncate font-mono text-xs text-muted">{o.path}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {["literature", "search"].includes(stage.id) && stage.outputs_found.some((o) => o.path === "paper/refs.bib" && o.exists) && (
                <div className="mt-4 rounded-lg bg-[#f6f5f1] p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <b>Reference check (Crossref, arXiv)</b>
                    <button className={btn2} disabled={checking} onClick={checkRefs}>{checking ? "Checking…" : refs ? "Check again" : "Check references"}</button>
                  </div>
                  {refs && (
                    <>
                      <p className="mt-1 text-muted">
                        {refs.total} entries: {Object.entries(refs.counts).map(([k, n]) => `${n} ${k.replace(/_/g, " ")}`).join(", ")}.
                        Missing author, year or venue fields were filled only from a matching record; the original is kept as refs.bib.orig.
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {refs.entries.filter((e) => e.status !== "verified").map((e) => (
                          <li key={e.key} className="text-xs text-[#7f1d1d]"><span className="font-mono">{e.key}</span> · {e.status.replace(/_/g, " ")}{e.note ? ` · ${e.note}` : ""}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {!refs && <p className="mt-1 text-faint">Looks up each DOI or arXiv id. If the network is down, entries are marked not checked.</p>}
                </div>
              )}

              {stage.id === "experiments" && paper.results && (
                <div className="mt-4 rounded-lg bg-[#f6f5f1] p-3 text-sm">
                  <b>{paper.results.measured} of {paper.results.slots}</b> result slots have a measured file in <span className="font-mono text-xs">results/</span>.
                  {" "}Unmeasured slots stay <span className="font-mono text-xs">TBD</span> and show as placeholders in the paper.
                  {paper.collected?.issues?.map((m) => <div key={m} className="mt-1 text-[#7f1d1d]">⚠ {m}</div>)}
                  <p className="mt-1 text-faint">The experimental log is filled from these files when you approve this stage.</p>
                </div>
              )}

              {stage.status === "locked" && <p className="mt-4 text-sm text-faint">Approve the previous stage to unlock this one.</p>}

              {["ready", "failed", "incomplete"].includes(stage.status) && (
                <div className="mt-5 space-y-2">
                  <label className="block text-sm font-medium" htmlFor="notes">Notes for the agent (optional)</label>
                  <textarea id="notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
                    placeholder="e.g. focus on insurance claims; use only open datasets"
                    className="w-full rounded-lg border border-line px-3 py-2 text-sm" />
                  <button className={btn} disabled={busy} onClick={() => act(`stages/${stage.id}/run`, { notes })}>
                    {stage.status === "ready" ? `Run ${stage.title}` : `Run ${stage.title} again`}
                  </button>
                </div>
              )}

              {stage.status === "needs_review" && (
                <div className="mt-5 space-y-3">
                  <p className="text-sm">Check the files above. Approve to unlock the next stage, or ask for changes.</p>
                  <div className="flex flex-wrap gap-2">
                    <button className={btn} disabled={busy} onClick={() => act(`stages/${stage.id}/approve`)}>Approve {stage.title}</button>
                    <button className={btn2} onClick={() => setAsking(!asking)}>Ask for changes</button>
                  </div>
                  {asking && (
                    <div className="space-y-2">
                      <textarea rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)} aria-label="Changes you want"
                        placeholder="What should change?" className="w-full rounded-lg border border-line px-3 py-2 text-sm" />
                      <button className={btn} disabled={busy || !feedback.trim()} onClick={() => act(`stages/${stage.id}/run`, { feedback })}>Revise {stage.title}</button>
                    </div>
                  )}
                </div>
              )}
              {stage.status === "approved" && <p className="mt-4 text-sm text-accent">Approved. You can still re-run it from the chat; later stages would then need approval again.</p>}
              {stage.status === "approved" && (
                <button className={`${btn2} mt-2`} onClick={() => act(`stages/${stage.id}/run`, { notes: "Re-run requested by the user." })}>Run again</button>
              )}
              {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}
            </div>

            {stage.status === "running" && <BridgeBanner waiting />}

            {stage.run_id && (
              <div className="rounded-2xl border border-line bg-white p-5 text-sm">
                <div className="mb-2 font-semibold">Latest run</div>
                {todos && (
                  <ul className="mb-3 space-y-1">
                    {todos.map((t, i) => (
                      <li key={i} className={t.status === "completed" ? "text-faint line-through" : t.status === "in_progress" ? "font-medium" : "text-muted"}>
                        {t.status === "completed" ? "✓" : t.status === "in_progress" ? "▸" : "○"} {t.content}
                      </li>
                    ))}
                  </ul>
                )}
                {steps.length > 0 && <p className="text-faint">{steps.length} steps · last: {String(steps.at(-1)!.payload.target ?? steps.at(-1)!.payload.name)}</p>}
                {errors.map((e) => <div key={e.id} className="mt-2"><ErrorBox error={String(e.payload.text)} /></div>)}
                {reply && stage.status !== "running" && <div className="mt-3 border-t border-line pt-3"><Markdown text={String(reply.payload.text)} /></div>}
                {stage.status === "running" && !steps.length && <p className="rl-pulse text-faint">Working…</p>}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function StepDot({ status, n }: { status: PaperStage["status"]; n: number }) {
  const cls = status === "approved" ? "bg-accent text-white" : status === "running" ? "rl-pulse bg-[#3b6fd8] text-white"
    : status === "needs_review" ? "bg-[#f2b66d] text-white" : status === "failed" || status === "incomplete" ? "bg-[#b91c1c] text-white"
    : status === "ready" ? "bg-white ring-2 ring-accent text-accent" : "bg-[#e6e4de] text-[#8a8780]";
  return <span className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-semibold ${cls}`}>{status === "approved" ? "✓" : n}</span>;
}

function FileGroup({ title, items, empty }: { title: string; items: { label: string; ok?: boolean; title?: string }[]; empty?: string }) {
  return (
    <div>
      <div className="mb-1 font-semibold">{title}</div>
      {items.length === 0 && <p className="text-faint">{empty ?? "—"}</p>}
      <ul className="space-y-1">
        {items.map((it) => (
          <li key={it.label} title={it.title} className="truncate text-xs text-muted">
            {it.ok === false ? <span className="text-[#b91c1c]">missing · </span> : null}{it.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
