"use client";

// Evidence and integrity: the project's ResearchLedger — claims (C###), evidence (E###) and sealed runs (R####).
// Recorded runs arrive as *observed* evidence; only you mark evidence checked, verified or invalid, and claim status
// is derived by the ledger from that — never set by hand or by an agent.

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn, btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Claim { id: string; name: string; status: string; statement: string; evidence: string[]; contradicts: string[] }
interface Ev { id: string; name: string; status: string; meaning: string; supports: string[]; contradicts: string[];
  runs: string[]; values: Record<string, unknown>; app_ref: string | null }
interface Run { id: string; command: string | null; finished_at: string | null; reproducibility: string | null; app_ref: string | null }
interface Overview { claims: Claim[]; evidence: Ev[]; runs: Run[]; issues: { level: string; code: string; message: string }[];
  valid: boolean; sync: { evidence_added?: number; claims_added?: number; error?: string } | null }

const CLAIM_TONE: Record<string, string> = {
  hypothesis: "bg-[#f4f5f7] text-[#3a4552]", provisional: "bg-[#fff4dc] text-[#7a4b06]", supported: "bg-[#dff3e4] text-[#14532d]",
  mixed: "bg-[#f3ecdf] text-[#7a3a06]", contradicted: "bg-[#fbe4e4] text-[#7f1d1d]", withdrawn: "bg-[#ece7f6] text-[#4c1d95]",
};
const CLAIM_WORDS: Record<string, string> = {
  hypothesis: "no reviewed evidence yet", provisional: "backed by recorded or reviewed evidence", supported: "backed by evidence you verified",
  mixed: "evidence both for and against", contradicted: "reviewed evidence goes against it", withdrawn: "withdrawn",
};
const EV_TONE: Record<string, string> = {
  observed: "bg-[#fff4dc] text-[#7a4b06]", checked: "bg-[#e6eefb] text-[#1e3a8a]", verified: "bg-[#dff3e4] text-[#14532d]",
  invalidated: "bg-[#fbe4e4] text-[#7f1d1d]", contradicted: "bg-[#fbe4e4] text-[#7f1d1d]", proposed: "bg-[#f4f5f7] text-[#3a4552]",
  superseded: "bg-[#f4f5f7] text-[#3a4552]",
};

export default function EvidencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<{ id: string; text: string } | null>(null);
  const [adding, setAdding] = useState(false);
  const [statement, setStatement] = useState("");
  const [picked, setPicked] = useState<string[]>([]);

  const load = useCallback(() => { setError(null); api<Overview>(`/projects/${id}/evidence`).then(setOv).catch(setError); }, [id]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); load(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  function judge(e: Ev, status: string, question: string) {
    const reason = window.prompt(question);
    if (!reason?.trim()) return;
    act(() => post(`/projects/${id}/evidence/${e.id}/status`, { status, reason }));
  }
  async function showTrace(eid: string) {
    try { setTrace(await api<{ id: string; text: string }>(`/projects/${id}/ledger/trace/${eid}`)); } catch (e) { setError(e); }
  }
  const evById = new Map((ov?.evidence ?? []).map((e) => [e.id, e]));

  return (
    <main className="mx-auto max-w-[1100px] px-4 py-7 sm:px-8">
      <div className="mb-1 text-sm text-faint"><Link href={`/projects/${id}/home`} className="hover:text-ink">← Back to the project</Link></div>
      <PageHeader title="Evidence"
        sub="Claims, the evidence behind them, and the sealed runs that produced it. Recorded runs arrive as “observed”; only you mark evidence checked, verified or invalid. Claim status follows from that automatically. Passing these checks is not proof of correctness, novelty or publication readiness."
        actions={<button className={btn2} onClick={load}>Refresh</button>} />
      <ErrorBox error={error} />

      {ov && (
        <div className={`mb-5 rounded-lg border px-3 py-2 text-sm ${ov.valid ? "border-[#b8e0d2] bg-[#effaf6]" : "border-[#f0c4c4] bg-[#fdf1f1]"}`}>
          <b>{ov.valid ? "Ledger integrity: no errors." : "Ledger integrity: problems found."}</b>{" "}
          {ov.claims.length} claim(s) · {ov.evidence.length} evidence · {ov.runs.length} sealed run(s)
          {ov.sync && (ov.sync.evidence_added || ov.sync.claims_added) ? ` · just added ${ov.sync.evidence_added ?? 0} evidence, ${ov.sync.claims_added ?? 0} claim(s)` : ""}
          {ov.sync?.error && <div className="text-[#7f1d1d]">Import problem: {ov.sync.error}</div>}
          {ov.issues.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-xs">{ov.issues.map((i, n) => <li key={n}><span className="font-mono">{i.code}</span> {i.level}: {i.message}</li>)}</ul>
          )}
        </div>
      )}

      {trace && (
        <Card className="mb-5 p-4">
          <div className="flex items-center justify-between"><b>Provenance of {trace.id}</b><button className="text-faint" onClick={() => setTrace(null)} aria-label="Close">✕</button></div>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-[#f6f5f1] p-3 font-mono text-xs">{trace.text}</pre>
        </Card>
      )}

      <section className="mb-8">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Claims</h2>
          <button className={btn2} onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add a claim"}</button>
        </div>
        {adding && (
          <Card className="mb-3 space-y-2 p-4">
            <textarea rows={2} className="w-full rounded-lg border border-line px-3 py-2 text-sm" placeholder="One clear sentence the paper asserts, e.g. “Method X reaches 0.81 AUROC on the scaffold split.”"
              value={statement} onChange={(e) => setStatement(e.target.value)} aria-label="Claim statement" />
            <div className="text-xs text-muted">Supported by:</div>
            <div className="flex flex-wrap gap-2">
              {(ov?.evidence ?? []).filter((e) => e.status !== "invalidated").map((e) => (
                <label key={e.id} className="flex items-center gap-1 rounded border border-line px-2 py-1 text-xs">
                  <input type="checkbox" checked={picked.includes(e.id)} onChange={(x) => setPicked(x.target.checked ? [...picked, e.id] : picked.filter((p) => p !== e.id))} />
                  <span className="font-mono">{e.id}</span> {e.name.slice(0, 50)}
                </label>
              ))}
            </div>
            <button className={btn} disabled={busy || statement.trim().length < 5} onClick={() => act(async () => {
              await post(`/projects/${id}/claims`, { statement, supports: picked }); setStatement(""); setPicked([]); setAdding(false);
            })}>Save claim</button>
          </Card>
        )}
        <div className="space-y-2">
          {ov?.claims.map((c) => (
            <Card key={c.id} className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <b className="font-mono text-sm">{c.id}</b>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${CLAIM_TONE[c.status] ?? ""}`} title={CLAIM_WORDS[c.status]}>{c.status}</span>
                <span className="text-xs text-faint">{CLAIM_WORDS[c.status]}</span>
              </div>
              <p className="mt-1 text-sm">{c.statement || c.name}</p>
              <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                {c.evidence.map((e) => <span key={e} className={`rounded px-1.5 ${EV_TONE[evById.get(e)?.status ?? ""] ?? ""}`}>for: {e} ({evById.get(e)?.status ?? "?"})</span>)}
                {c.contradicts.map((e) => <span key={e} className={`rounded px-1.5 ${EV_TONE[evById.get(e)?.status ?? ""] ?? ""}`}>against: {e} ({evById.get(e)?.status ?? "?"})</span>)}
                {!c.evidence.length && !c.contradicts.length && <span className="text-faint">no evidence linked</span>}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <button className={btn2} onClick={() => showTrace(c.id)}>Trace</button>
                {c.status !== "withdrawn" && (
                  <button className={btn2} disabled={busy} onClick={() => {
                    const reason = window.prompt(`Why withdraw ${c.id}? (kept with the claim)`);
                    if (reason?.trim()) act(() => post(`/projects/${id}/claims/${c.id}/withdraw`, { reason }));
                  }}>Withdraw</button>
                )}
              </div>
            </Card>
          ))}
          {ov && ov.claims.length === 0 && <Card className="p-4 text-sm text-muted">No claims yet. Pre-registered experiments become claims when they get a verdict; you can also add one.</Card>}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Evidence</h2>
        <div className="space-y-2">
          {ov?.evidence.map((e) => (
            <Card key={e.id} className="p-4">
              <div className="flex flex-wrap items-center gap-2">
                <b className="font-mono text-sm">{e.id}</b>
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${EV_TONE[e.status] ?? ""}`}>{e.status}</span>
                <span className="text-xs text-faint">{e.meaning}</span>
                {e.runs.map((r) => <span key={r} className="font-mono text-xs text-faint">run {r}</span>)}
              </div>
              <p className="mt-1 text-sm">{e.name}</p>
              <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                {Object.entries(e.values).map(([k, v]) => <span key={k} className="rounded bg-[#f6f5f1] px-2 py-0.5"><span className="font-mono">{k}</span> = {String(v)}</span>)}
                {e.supports.map((c) => <span key={c} className="text-[#14532d]">supports {c}</span>)}
                {e.contradicts.map((c) => <span key={c} className="text-[#7f1d1d]">against {c}</span>)}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {e.status === "observed" && <button className={btn2} disabled={busy} onClick={() => judge(e, "checked", `What did you check in ${e.id}? (e.g. "read the log and analysis; values match the code")`)}>Mark checked</button>}
                {["observed", "checked"].includes(e.status) && <button className={btn2} disabled={busy} onClick={() => judge(e, "verified", `How was ${e.id} confirmed? (e.g. "a repeat run gave the same values")`)}>Mark verified</button>}
                {e.status !== "invalidated" && <button className={btn2} disabled={busy} onClick={() => judge(e, "invalidated", `Why is ${e.id} invalid?`)}>Invalidate</button>}
                <button className={btn2} onClick={() => showTrace(e.id)}>Trace</button>
                {e.app_ref && !e.app_ref.startsWith("legacy:") && <Link className={btn2} href={`/projects/${id}/lab`}>Experiment record</Link>}
              </div>
            </Card>
          ))}
          {ov && ov.evidence.length === 0 && <Card className="p-4 text-sm text-muted">No evidence yet. Every experiment run with measured results adds observed evidence here.</Card>}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Sealed runs</h2>
        <Card className="divide-y divide-line">
          {ov?.runs.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
              <b className="font-mono">{r.id}</b>
              <span className="truncate font-mono text-xs text-muted">{r.command}</span>
              <span className="ml-auto text-xs text-faint">{r.reproducibility === "NOT_INDEPENDENTLY_REPRODUCED" ? "recorded, not independently reproduced" : r.reproducibility ?? ""}</span>
            </div>
          ))}
          {ov && ov.runs.length === 0 && <p className="px-4 py-3 text-sm text-muted">No sealed runs yet.</p>}
        </Card>
      </section>
    </main>
  );
}
