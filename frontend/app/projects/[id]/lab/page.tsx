"use client";

// Experiment laboratory: the project's experiments as a tree, every recorded run with what it started from
// (code, data, Python packages), a live view of runs in progress, side-by-side comparison of two runs, and
// "Repeat" to re-run a run's exact commands as a new record (the project's results are left as they were).

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { api, eventsUrl, post } from "@/lib/api";
import { btn, btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Node { id: string; kind: "loop" | "paper" | "source"; title: string; status: string | null; parent: string | null;
  verdicts?: Record<string, string>; label?: string }
interface RunSummary { run_id: string; experiment: string | null; repeat_of: string | null; finished_at: string | null;
  file: string; legacy: boolean; runner: string | null; ok: boolean; values: Record<string, unknown>;
  jobs: { id: string; command: string; exit_code: number | null; seconds: number; ok: boolean }[];
  code_sha256: string | null; data_sha256: string | null; python: string | null }
interface Lab { experiments: Node[]; runs: RunSummary[]; active: { id: string; kind: string; status: string; created_at: string }[] }
interface Compare { a: string; b: string; same_values: boolean; code_same: boolean | null; data_same: boolean | null;
  slots: { slot: string; a: unknown; b: unknown; same: boolean; diff?: number; rel_diff?: number | null }[];
  changed_files: { code: string[]; data: string[] }; environment: { python: (string | null)[]; packages: { name: string; a: string | null; b: string | null }[] };
  fingerprints_missing: boolean }
interface Receipt { receipt?: { environment?: { python?: string; platform?: string; packages?: Record<string, string | null>; interpreter?: string };
  code?: { tree_sha256: string | null; count: number }; data?: { tree_sha256: string | null; count: number } };
  jobs: { id: string; command: string; exit_code: number | null; seconds: number; ok: boolean; log_tail?: string; timed_out?: boolean;
    slots: Record<string, { ok: boolean; value?: unknown; error?: string }> }[] }

const VERDICT: Record<string, string> = { supported: "bg-[#dff3e4] text-[#14532d]", not_supported: "bg-[#fbe4e4] text-[#7f1d1d]",
  inconclusive: "bg-[#f4f5f7] text-[#3a4552]" };

function when(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
const short = (h: string | null | undefined) => (h ? h.slice(0, 10) : "—");

// ------------------------------------------------------------ live view of a run in progress
interface Ev { id: number; ts: string; kind: string; payload: Record<string, unknown> }

function LiveRun({ runId, onDone }: { runId: string; onDone: () => void }) {
  const [events, setEvents] = useState<Ev[]>([]);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    const es = new EventSource(eventsUrl(runId, 0));
    const on = (ev: MessageEvent) => { const e: Ev = JSON.parse(ev.data); setEvents((s) => (s.some((x) => x.id === e.id) ? s : [...s, e])); };
    for (const k of ["status", "job", "done", "error"]) es.addEventListener(k, on as EventListener);
    es.addEventListener("end", () => { es.close(); done.current(); });
    return () => es.close();
  }, [runId]);
  const jobs = new Map<string, { state: string; command?: string; seconds?: number; exit_code?: number | null }>();
  for (const e of events.filter((x) => x.kind === "job")) {
    const p = e.payload as { id: string; state: string; command?: string; seconds?: number; exit_code?: number | null };
    jobs.set(p.id, { ...jobs.get(p.id), ...p });
  }
  const list = [...jobs.entries()];
  const finished = list.filter(([, j]) => j.state === "done" || j.state === "failed").length;
  const pct = list.length ? Math.round((100 * finished) / list.length) : 0;
  const tone: Record<string, string> = { done: "border-[#b8e0d2] bg-[#effaf6]", failed: "border-[#f0c4c4] bg-[#fdf1f1]",
    running: "border-accent bg-white", queued: "border-[#f0dfb0] bg-[#fffaf0]" };
  return (
    <Card className="mb-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Running now · {runId}</h2>
        <span className="text-sm text-muted">{finished}/{list.length} jobs · {pct}%</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-[#e9ecef]"><div className="h-2 rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} /></div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ol className="space-y-2">
          {list.map(([id, j]) => (
            <li key={id} className={`rounded-lg border px-3 py-2 text-sm ${tone[j.state] ?? "border-line"}`}>
              <div className="flex items-center justify-between gap-2"><b>{id}</b>
                <span className="text-xs">{j.state}{j.seconds != null ? ` · ${j.seconds}s` : ""}{j.exit_code != null && j.state !== "done" ? ` · exit ${j.exit_code}` : ""}</span></div>
              {j.command && <div className="truncate font-mono text-xs text-faint">{j.command}</div>}
              {j.state === "running" && <div className="mt-1 h-1 rounded-full bg-[#e9ecef]"><div className="rl-pulse h-1 w-1/2 rounded-full bg-accent" /></div>}
            </li>
          ))}
          {!list.length && <li className="rl-pulse text-sm text-faint">Starting…</li>}
        </ol>
        <div className="max-h-72 overflow-auto rounded-lg bg-[#f6f5f1] p-3 font-mono text-xs">
          {events.filter((e) => e.kind === "status" || e.kind === "error").map((e) => (
            <div key={e.id}><span className="text-faint">{new Date(e.ts).toLocaleTimeString()}</span> {String(e.payload.text ?? "")}</div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------ page
export default function LabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [lab, setLab] = useState<Lab | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [sel, setSel] = useState<string>("");           // experiment filter ("" = all)
  const [pick, setPick] = useState<string[]>([]);        // runs chosen for comparison
  const [cmp, setCmp] = useState<Compare | null>(null);
  const [open, setOpen] = useState<{ id: string; r: Receipt } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { api<Lab>(`/projects/${id}/lab`).then(setLab).catch(setError); }, [id]);
  useEffect(load, [load]);

  async function compare() {
    setError(null); setCmp(null);
    try { setCmp(await api<Compare>(`/projects/${id}/lab/compare?a=${encodeURIComponent(pick[0])}&b=${encodeURIComponent(pick[1])}`)); }
    catch (e) { setError(e); }
  }
  async function showRun(runId: string) {
    setError(null);
    try { setOpen({ id: runId, r: await api<Receipt>(`/projects/${id}/lab/runs/${encodeURIComponent(runId)}`) }); } catch (e) { setError(e); }
  }
  async function repeat(runId: string) {
    if (!window.confirm("Run the same commands again on this computer, with no sandbox? It is recorded as a new run; your project's results are left as they are.")) return;
    setBusy(true); setError(null);
    try { await post(`/projects/${id}/lab/runs/${encodeURIComponent(runId)}/repeat`); load(); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  const nodes = lab?.experiments ?? [];
  const children = (pid: string | null) => nodes.filter((n) => (n.parent ?? null) === pid || (pid === null && n.parent && !nodes.some((m) => m.id === n.parent)));
  const runs = (lab?.runs ?? []).filter((r) => !sel || r.experiment === sel);
  const count = (eid: string) => (lab?.runs ?? []).filter((r) => r.experiment === eid).length;

  function Tree({ parent, depth }: { parent: string | null; depth: number }) {
    return (
      <>
        {children(parent).map((n) => (
          <div key={n.id}>
            <button onClick={() => setSel(sel === n.id ? "" : n.id)} style={{ paddingLeft: 8 + depth * 16 }}
              className={`block w-full rounded-lg py-2 pr-2 text-left text-sm hover:bg-[#f6f5f1] ${sel === n.id ? "bg-[#f6f5f1] font-semibold" : ""}`}>
              {depth > 0 && <span className="text-faint">└ </span>}
              {n.kind === "source" ? <span className="text-faint">{n.label}: </span> : null}{n.title}
              <div className="mt-0.5 flex flex-wrap gap-1 text-xs font-normal">
                {n.kind !== "source" && <span className="text-faint">{count(n.id)} run(s){n.status ? ` · ${n.status}` : ""}</span>}
                {Object.entries(n.verdicts ?? {}).map(([k, v]) => <span key={k} className={`rounded-full px-1.5 ${VERDICT[v] ?? ""}`}>{k}: {v.replace("_", " ")}</span>)}
              </div>
            </button>
            <Tree parent={n.id} depth={depth + 1} />
          </div>
        ))}
      </>
    );
  }

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-7 sm:px-8">
      <div className="mb-1 text-sm text-faint"><Link href={`/projects/${id}/home`} className="hover:text-ink">← Back to the project</Link></div>
      <PageHeader title="Experiments" sub="Every recorded run, what it started from (code, data, Python packages), and how runs compare. Repeat a run to check it reproduces."
        actions={<button className={btn2} onClick={load}>Refresh</button>} />
      <ErrorBox error={error} />

      {lab?.active.map((a) => <LiveRun key={a.id} runId={a.id} onDone={load} />)}

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="h-fit p-2">
          <button onClick={() => setSel("")} className={`block w-full rounded-lg px-2 py-2 text-left text-sm ${sel === "" ? "bg-[#f6f5f1] font-semibold" : ""}`}>All runs ({lab?.runs.length ?? 0})</button>
          <Tree parent={null} depth={0} />
          {lab && nodes.length === 0 && <p className="p-2 text-sm text-faint">No experiments yet. Start one from the Run experiments step or a paper's Run experiments stage.</p>}
        </Card>

        <div className="space-y-3">
          {pick.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-[#f6f5f1] px-3 py-2 text-sm">
              <span>{pick.length} of 2 runs chosen for comparison.</span>
              <button className={btn} disabled={pick.length !== 2} onClick={compare}>Compare</button>
              <button className={btn2} onClick={() => { setPick([]); setCmp(null); }}>Clear</button>
            </div>
          )}

          {cmp && (
            <Card className="p-5 text-sm">
              <div className="flex items-center justify-between"><h2 className="font-semibold">{cmp.a} → {cmp.b}</h2>
                <button className="text-faint" onClick={() => setCmp(null)} aria-label="Close comparison">✕</button></div>
              <p className="mt-1">
                {cmp.same_values ? "Same measured values." : "Measured values differ."}{" "}
                {cmp.fingerprints_missing ? "One run predates fingerprints, so code and data cannot be compared."
                  : <>Code {cmp.code_same ? "identical" : "changed"}; data {cmp.data_same ? "identical" : "changed"}.</>}
              </p>
              <table className="mt-3 w-full text-left">
                <thead><tr className="text-xs text-faint"><th>Result</th><th>First</th><th>Second</th><th>Difference</th></tr></thead>
                <tbody>{cmp.slots.map((s) => (
                  <tr key={s.slot} className={s.same ? "" : "bg-[#fff8ef]"}><td className="font-mono text-xs">{s.slot}</td><td>{String(s.a ?? "—")}</td><td>{String(s.b ?? "—")}</td>
                    <td>{s.same ? "same" : s.diff != null ? `${s.diff > 0 ? "+" : ""}${Number(s.diff.toPrecision(4))}` : "differs"}</td></tr>
                ))}</tbody>
              </table>
              {(cmp.changed_files.code.length > 0 || cmp.changed_files.data.length > 0) && (
                <p className="mt-2 text-xs text-muted">Changed files: <span className="font-mono">{[...cmp.changed_files.code, ...cmp.changed_files.data].join(", ")}</span></p>
              )}
              {cmp.environment.packages.length > 0 && (
                <p className="mt-1 text-xs text-muted">Package versions differ: {cmp.environment.packages.map((p) => `${p.name} ${p.a ?? "?"} → ${p.b ?? "?"}`).join("; ")}</p>
              )}
            </Card>
          )}

          {runs.map((r) => (
            <Card key={r.run_id} className="p-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <input type="checkbox" aria-label={`Compare ${r.run_id}`} checked={pick.includes(r.run_id)}
                  onChange={(e) => setPick(e.target.checked ? [...pick, r.run_id].slice(-2) : pick.filter((x) => x !== r.run_id))} />
                <span className={r.ok ? "text-[#14532d]" : "text-[#7f1d1d]"}>{r.ok ? "✓" : "✕"}</span>
                <b className="font-mono text-xs">{r.run_id}</b>
                {r.repeat_of && <span className="rounded-full bg-[#e6eefb] px-2 text-xs">repeat of {r.repeat_of}</span>}
                {r.legacy && <span className="rounded-full bg-[#f4f5f7] px-2 text-xs text-faint">before fingerprints</span>}
                <span className="ml-auto text-xs text-faint">{when(r.finished_at)}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                {Object.entries(r.values).map(([k, v]) => <span key={k} className="rounded bg-[#f6f5f1] px-2 py-0.5"><span className="font-mono">{k}</span> = {String(v)}</span>)}
                {Object.keys(r.values).length === 0 && <span className="text-faint">no measured results</span>}
              </div>
              <div className="mt-2 text-xs text-faint">
                {r.jobs.length} job(s) · code {short(r.code_sha256)} · data {short(r.data_sha256)} · Python {r.python ?? "—"} · runner {r.runner ?? "—"}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button className={btn2} onClick={() => showRun(r.run_id)}>Details</button>
                {!r.run_id.startsWith("legacy:") && (
                  <button className={btn2} disabled={busy || (lab?.active.length ?? 0) > 0} onClick={() => repeat(r.run_id)}
                    title={r.legacy ? "Repeating gives this run a full receipt with fingerprints" : undefined}>Repeat</button>
                )}
                <Link className={btn2} target="_blank" href={`/view/${id}?path=${encodeURIComponent(r.file)}`}>Receipt file</Link>
              </div>
              {open?.id === r.run_id && (
                <div className="mt-3 space-y-2 border-t border-line pt-3 text-xs">
                  {open.r.receipt?.environment && (
                    <div>Python {open.r.receipt.environment.python} · {open.r.receipt.environment.platform}
                      {open.r.receipt.environment.packages && Object.keys(open.r.receipt.environment.packages).length > 0 && (
                        <> · {Object.entries(open.r.receipt.environment.packages).map(([n, v]) => `${n} ${v ?? "not installed"}`).join(", ")}</>
                      )}
                      <div className="text-faint">code: {open.r.receipt.code?.count} file(s), {open.r.receipt.code?.tree_sha256} · data: {open.r.receipt.data?.count} file(s), {open.r.receipt.data?.tree_sha256 ?? "none"}</div>
                    </div>
                  )}
                  {open.r.jobs.map((j) => (
                    <div key={j.id}>
                      <div><b>{j.id}</b> · <span className="font-mono">{j.command}</span> · exit {String(j.exit_code)}{j.timed_out ? " (time limit)" : ""} · {j.seconds}s</div>
                      {Object.entries(j.slots).map(([k, s]) => <div key={k} className={s.ok ? "" : "text-[#7f1d1d]"}>{k}: {s.ok ? String(s.value) : s.error}</div>)}
                      {j.log_tail && <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-[#f6f5f1] p-2">{j.log_tail}</pre>}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
          {lab && runs.length === 0 && <Card className="p-5 text-sm text-muted">No recorded runs here yet.</Card>}
        </div>
      </div>
    </main>
  );
}
