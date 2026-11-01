"use client";

// One research loop: where it is, every round's checked numbers, and the few clicks that are yours
// (steer, continue, stop, retry, accept). Refreshes every 4 s; the server advances the loop by itself.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Loop, LoopRound } from "@/lib/loops";
import { SCORE_KEYS, STATUS_STYLE } from "@/lib/loops";
import { BridgeBanner } from "@/components/BridgeStatus";
import { btn, btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

export default function LoopPage() {
  const { id, loop } = useParams<{ id: string; loop: string }>();
  const [v, setV] = useState<Loop | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const base = `/projects/${id}/loops/${loop}`;
  const load = useCallback(() => { api<Loop>(base).then(setV).catch(setError); }, [base]);
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, [load]);

  async function act(action: string, body?: unknown) {
    setBusy(true); setError(null);
    try { setV(await post<Loop>(`${base}/${action}`, body)); if (action === "steer") setNote(""); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  if (!v) return <main className="px-8 py-8"><ErrorBox error={error} /></main>;

  const [label, cls] = STATUS_STYLE[v.status];
  const view = (p: string) => `/view/${id}?path=${encodeURIComponent(p)}`;
  const scored = v.rounds.filter((r) => v.type === "idea_forge" ? r.metrics.total != null : r.metrics.verified_major != null);

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8">
      <div className="mb-2 text-sm"><Link className="text-accent underline" href={`/loops?project=${id}`}>← Research Loops</Link></div>
      <PageHeader title={v.label} sub={v.goal}
        actions={<span className={`rounded-full px-3 py-1 text-xs font-semibold ${cls}`}>{label}</span>} />
      <ErrorBox error={error} />

      <Card className="mb-6 p-5">
        {v.status === "running" && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <span className="rl-pulse h-2.5 w-2.5 rounded-full bg-[#3b6fd8]" />
              <span>Round <b>{v.round}</b> · {v.rounds.find((r) => r.round === v.round)?.moves.find((m) => m.move === v.move)?.label ?? v.move}</span>
              <Link className="ml-auto text-accent underline" href={`/projects/${id}?conv=${v.conversation_id}`}>Watch the agent</Link>
            </div>
            <BridgeBanner waiting />
          </div>
        )}
        {v.status === "paused" && <p className="text-sm">{v.paused_reason}</p>}
        {(v.status === "finished" || v.status === "stopped" || v.status === "failed") && v.stop_reason && (
          <p className="text-sm"><b>{v.status === "failed" ? "Stopped on a problem" : "Stop rule"}:</b> {v.stop_reason}</p>
        )}
        {v.status === "finished" && v.final_files.length > 0 && (
          <div className="mt-3 text-sm">Best result: round {v.best_round} ·{" "}
            {v.final_files.map((f) => <Link key={f} target="_blank" className="mr-2 font-mono text-xs text-accent underline" href={view(f)}>{f}</Link>)}
          </div>
        )}
        {v.accepted && v.accepted_files && <p className="mt-2 text-sm text-[#1d6b3a]">Accepted → {v.accepted_files.join(", ")}</p>}

        <div className="mt-4 flex flex-wrap gap-2">
          {v.status === "paused" && <button className={btn} disabled={busy} onClick={() => act("continue")}>Continue</button>}
          {v.status === "finished" && !v.accepted && <button className={btn} disabled={busy} onClick={() => act("accept")}>Accept result</button>}
          {(v.status === "finished" || v.status === "stopped") && <button className={btn2} disabled={busy} onClick={() => act("continue")}>One more round</button>}
          {v.status === "failed" && <button className={btn} disabled={busy} onClick={() => act("retry")}>Try again</button>}
          {(v.status === "running" || v.status === "paused" || v.status === "failed") && <button className={btn2} disabled={busy} onClick={() => act("stop")}>Stop</button>}
          <Link className={btn2} target="_blank" href={view(v.report)}>Report</Link>
        </div>

        <div className="mt-4 flex gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} aria-label="Steer the next move"
            placeholder="Steer the next move, e.g. ‘focus on IEEE TDSC 2025–2026 papers’ or ‘do not touch the abstract’"
            className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 text-sm" />
          <button className={btn2} disabled={busy || !note.trim()} onClick={() => act("steer", { text: note })}>Add note</button>
        </div>
        {v.notes.length > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-muted">
            {v.notes.map((n, i) => <li key={i}>• {n.text} <span className="text-faint">({n.used_in ? `used in ${n.used_in}` : "waiting for the next move"})</span></li>)}
          </ul>
        )}
      </Card>

      {scored.length > 0 && <Trajectory v={v} rounds={scored} />}

      {v.needs_experiments && v.needs_experiments.length > 0 && (
        <Card className="mb-6 border-[#f0d9a8] p-5">
          <h2 className="text-sm font-semibold">Experiments the reviewers asked for — your decision</h2>
          <p className="mt-1 text-xs text-muted">The loop never runs or invents these. Editing alone cannot close them; run the ones worth it and put the results in results/*.json.</p>
          <ul className="mt-2 space-y-1 text-sm">
            {v.needs_experiments.map((e) => <li key={e.id}><b>{e.id}</b> (round {e.round}): {e.concern || e.reason}{e.concern && e.reason ? <span className="text-faint"> — {e.reason}</span> : null}</li>)}
          </ul>
        </Card>
      )}

      <div className="space-y-4">
        {[...v.rounds].reverse().map((r) => <RoundCard key={r.round} v={v} r={r} view={view} />)}
      </div>
    </main>
  );
}

function Trajectory({ v, rounds }: { v: Loop; rounds: LoopRound[] }) {
  const idea = v.type === "idea_forge";
  const max = idea ? 100 : Math.max(1, ...rounds.map((r) => r.metrics.verified_major ?? 0));
  const target = idea ? v.params.target_total : 0;
  return (
    <Card className="mb-6 p-5">
      <h2 className="mb-3 text-sm font-semibold">{idea ? "Score per round (/100, Phase 10 rubric — recomputed by the server)" : "Verified major concerns per round"}</h2>
      <div className="flex items-end gap-3" style={{ height: 140 }}>
        {rounds.map((r) => {
          const val = idea ? r.metrics.total ?? 0 : r.metrics.verified_major ?? 0;
          return (
            <div key={r.round} className="flex flex-1 flex-col items-center justify-end gap-1" style={{ height: "100%" }}>
              <span className="text-xs font-semibold">{val}</span>
              <div className={`w-full max-w-[56px] rounded-t ${r.round === v.best_round ? "bg-accent" : "bg-[#b9c3cf]"}`}
                style={{ height: `${Math.max(4, (val / max) * 100)}px` }} />
              <span className="text-[11px] text-faint">R{r.round}</span>
            </div>
          );
        })}
      </div>
      {idea && <p className="mt-2 text-xs text-faint">Pass: ≥ {target}/100, novelty ≥ {v.params.target_novelty}/20, no fatal flaw, ≥ {v.params.min_papers} papers with no wrong reference. Plateau: less than {v.params.plateau_points} points gained over two rounds.</p>}
      {!idea && <p className="mt-2 text-xs text-faint">Stops when a fresh review finds no verified major concern, after a final check following {v.params.max_rounds} fix rounds, or when concerns stop going down.</p>}
    </Card>
  );
}

function RoundCard({ v, r, view }: { v: Loop; r: LoopRound; view: (p: string) => string }) {
  const m = r.metrics;
  return (
    <Card className="p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold">{r.round === 0 ? "Candidates" : `Round ${r.round}`}</h3>
        {r.round === v.best_round && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">best</span>}
        <div className="ml-auto flex flex-wrap gap-1">
          {r.moves.map((mv) => (
            <span key={mv.move} title={mv.error ?? ""} className={`rounded-full border px-2 py-0.5 text-[11px] ${
              mv.status === "done" ? "border-[#bfe0ca] text-[#1d6b3a]" : mv.status === "running" ? "border-[#bcd0f2] text-[#24508f]"
                : mv.status === "rejected" ? "border-[#f0c4bf] text-[#8a1f17]" : "border-line text-faint"}`}>
              {mv.label}{mv.attempt && mv.attempt > 1 ? ` · try ${mv.attempt}` : ""}
            </span>
          ))}
        </div>
      </div>

      {r.evidence && (
        <div className={`mb-3 rounded-lg p-3 text-sm ${r.evidence.ok ? "bg-[#f1f8f3]" : "bg-[#fdf1ef]"}`}>
          <b>Literature evidence:</b> {r.evidence.papers} papers ({r.evidence.recent_2024_plus} from 2024+), {r.evidence.with_identifier} with DOI/arXiv;
          {" "}sample looked up: {r.evidence.verified}/{r.evidence.sampled} verified
          {r.evidence.fabricated_or_wrong > 0 && <>, <b className="text-[#8a1f17]">{r.evidence.fabricated_or_wrong} wrong or invented</b></>}
          {r.evidence.unreachable > 0 && <>, {r.evidence.unreachable} not reachable</>}.
          {r.evidence.problems.map((p, i) => <div key={i} className="text-[#8a1f17]">• {p}</div>)}
        </div>
      )}

      {m.total != null && m.criteria && (
        <div className="mb-3">
          <div className="mb-2 text-sm"><b>{m.total}/100</b>{m.total_corrected && <span className="ml-2 text-xs text-[#7a5300]">(agent claimed {m.claimed_total}; recomputed)</span>}</div>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {v.rubric.map((c) => (
              <div key={c.id} className="flex items-center gap-2 text-xs">
                <span className="w-44 flex-none truncate text-muted">{c.label}</span>
                <div className="h-2 flex-1 rounded bg-[#eceae6]"><div className="h-2 rounded bg-accent" style={{ width: `${((m.criteria![c.id] ?? 0) / c.max) * 100}%` }} /></div>
                <span className="w-10 text-right">{m.criteria![c.id]}/{c.max}</span>
              </div>
            ))}
          </div>
          {m.fatal_flaws && m.fatal_flaws.length > 0 && (
            <div className="mt-3 text-sm"><b className="text-[#8a1f17]">Fatal flaws</b>
              <ul className="list-disc pl-5">{m.fatal_flaws.map((f, i) => <li key={i}>{f}</li>)}</ul></div>
          )}
          {m.verdict && <p className="mt-2 text-sm text-muted">{m.verdict}</p>}
        </div>
      )}

      {m.scores && Object.keys(m.scores).length > 0 && (
        <div className="mb-3 grid gap-1.5 sm:grid-cols-2">
          {SCORE_KEYS.map((k) => {
            const s = m.scores![k]; const t = v.params[`target_${k}`];
            if (s == null) return null;
            return (
              <div key={k} className="flex items-center gap-2 text-xs">
                <span className="w-20 flex-none capitalize text-muted">{k}</span>
                <div className="relative h-2 flex-1 rounded bg-[#eceae6]">
                  <div className={`h-2 rounded ${s >= t ? "bg-[#2f8a55]" : "bg-accent"}`} style={{ width: `${s * 10}%` }} />
                  {t ? <div className="absolute top-[-3px] h-[14px] w-[2px] bg-ink" style={{ left: `${t * 10}%` }} title={`target ${t}`} /> : null}
                </div>
                <span className="w-16 text-right">{s} / {t}</span>
              </div>
            );
          })}
          {m.mean_score != null && <div className="text-xs text-muted">Mean {m.mean_score}</div>}
        </div>
      )}

      {r.plan && (
        <div className="mb-3 text-sm"><b>Triage:</b>{" "}
          {Object.entries(r.plan.triage_counts).filter(([, n]) => n > 0).map(([a, n]) => `${n} ${a.replace("_", " ")}`).join(" · ")}
          <ul className="mt-1 space-y-0.5 text-xs text-muted">
            {r.plan.triage.map((t) => <li key={t.id}><b className="text-ink">{t.id}</b> {t.action.replace("_", " ")}{t.reason ? ` — ${t.reason}` : ""}</li>)}
          </ul>
        </div>
      )}

      {m.concerns && (
        <div className="mb-3">
          <div className="mb-2 text-sm"><b>{m.verified_major}</b> verified major of {m.concerns.length} concerns
            {m.overall != null && <> · reviewer {m.overall}/10</>}
            {(m.downgraded ?? 0) > 0 && <span className="ml-2 text-xs text-[#7a5300]">{m.downgraded} downgraded: quote not in the manuscript</span>}</div>
          <ul className="space-y-1 text-sm">
            {m.concerns.map((c) => (
              <li key={c.id} className="flex gap-2">
                <span className={`w-14 flex-none text-xs font-semibold ${c.verified_major ? "text-[#8a1f17]" : "text-faint"}`}>{c.id}</span>
                <span className="min-w-0 flex-1">{c.concern} <span className="text-xs text-faint">({c.severity}, {c.verification}{c.note ? ` — ${c.note}` : ""})</span></span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.fix && (
        <div className="mb-3 text-sm"><b>Fix:</b> {r.fix.changed_lines} of {r.fix.total_lines} lines changed ({Math.round(r.fix.change_ratio * 100)}%),
          {" "}template {r.fix.template_kept ? "kept" : "changed"}{r.fix.new_citation_keys.length > 0 && <>, new citations: {r.fix.new_citation_keys.join(", ")}</>}.
          {r.fix.warnings?.map((w, i) => <div key={i} className="text-[#7a5300]">• {w}</div>)}
          {r.fix.gate && r.fix.gate.ready != null && (
            <div className="mt-1"><b>Submission gate:</b> {r.fix.gate.ready ? "no failing check" : `${r.fix.gate.counts?.fail ?? 0} failing (open the report on the Quality Check page)`}
              {r.fix.gate.failing?.map((f, i) => <div key={i} className="text-[#8a1f17]">• {f}</div>)}</div>
          )}
        </div>
      )}

      {r.moves.some((mv) => mv.error || mv.last_error) && (
        <div className="mb-3 text-xs text-[#8a1f17]">{r.moves.filter((mv) => mv.error || mv.last_error).map((mv) => (
          <div key={mv.move}>{mv.label}: {mv.error ?? `redone — the server rejected try ${(mv.attempt ?? 2) - 1}: ${mv.last_error}`}</div>
        ))}</div>
      )}

      {r.files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {r.files.map((f) => <Link key={f} target="_blank" href={view(f)} className="rounded-lg border border-line px-2.5 py-1 font-mono text-xs text-accent hover:border-accent">{f.split("/").pop()}</Link>)}
        </div>
      )}
    </Card>
  );
}
