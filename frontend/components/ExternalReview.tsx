"use client";

// Independent review by another model (e.g. a ChatGPT temporary chat), without the copy-and-paste mess:
// 1. build a packet (manuscript, evidence summary, reviewer prompt); 2. take it to the other tool;
// 3. paste its reply back. A concern counts as VERIFIED only if its quote is really in the manuscript.
// Nothing is sent anywhere by ResearchLedger.

import { useCallback, useEffect, useState } from "react";
import { api, fileUrl, post } from "@/lib/api";
import { btn, btn2, ErrorBox } from "./ui";

interface Listing { packets: { name: string; zip: string }[]; imports: { folder: string; source?: string; total?: number; imported_at?: string }[]; manuscripts: string[] }
interface Packet { packet: string; folder: string; zip: string; has_pdf: boolean }
interface Concern { id: string; severity: string; location: string; concern: string; quote: string; verification: string; minimum_fix: string }
interface Imported { folder: string; file: string; total: number; verified: number; verified_major: number; unverified: number; concerns: Concern[]; feedback_for_revise: string | null }

export function ExternalReview({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const [ls, setLs] = useState<Listing | null>(null);
  const [path, setPath] = useState("");
  const [packet, setPacket] = useState<Packet | null>(null);
  const [reply, setReply] = useState("");
  const [source, setSource] = useState("ChatGPT (temporary chat)");
  const [res, setRes] = useState<Imported | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const load = useCallback(() => {
    api<Listing>(`/projects/${projectId}/review/external`).then((l) => {
      setLs(l);
      setPath((p) => p || l.manuscripts.find((m) => m.includes("revised")) || l.manuscripts[0] || "");
    }).catch(setError);
  }, [projectId]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await fn(); load(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  if (!ls || ls.manuscripts.length === 0) return null;

  return (
    <details className="mb-5 rounded-2xl border border-line bg-white p-4">
      <summary className="cursor-pointer font-semibold">Independent review by another model</summary>
      <p className="mt-2 text-sm text-muted">
        A different model reviewing the paper catches what the one that wrote it cannot. Build a packet, take it to the other tool,
        and paste its answer back. Only concerns whose quote is really in the manuscript count as verified; the rest are shown but never acted on.
        Nothing is sent anywhere from here.
      </p>
      <ErrorBox error={error} />

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <label>Manuscript
          <select className="ml-2 rounded-lg border border-line px-2 py-1.5" value={path} onChange={(e) => setPath(e.target.value)} aria-label="Manuscript">
            {ls.manuscripts.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <button className={btn2} disabled={busy || !path} onClick={() => act(async () => { setPacket(await post<Packet>(`/projects/${projectId}/review/packet`, { path })); })}>1. Build the packet</button>
      </div>
      {packet && (
        <div className="mt-3 rounded-lg bg-[#f6f5f1] p-3 text-sm">
          <b>{packet.packet}</b> is ready. <a className="text-accent underline" href={fileUrl(projectId, packet.zip, true)} download>Download the zip</a>
          {" "}(or open <span className="font-mono text-xs">{packet.folder}</span> in the project folder).
          <ol className="mt-1 list-decimal pl-5 text-xs text-muted">
            <li>Open a new private chat in the other tool.</li>
            <li>{packet.has_pdf ? "Attach manuscript.pdf" : "Paste manuscript.tex (no PDF was compiled)"} and evidence_summary.md, then paste REVIEW_PROMPT.md.</li>
            <li>Copy the table it answers with, and paste it below.</li>
          </ol>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <div className="text-sm font-medium">2. Paste the reviewer&apos;s reply</div>
        <input value={source} onChange={(e) => setSource(e.target.value)} aria-label="Who reviewed" className="w-full rounded-lg border border-line px-3 py-2 text-sm sm:w-80" />
        <textarea rows={6} value={reply} onChange={(e) => { setReply(e.target.value); setSent(false); }} aria-label="Reviewer reply"
          placeholder="Paste the table (or JSON / CSV) with columns id, severity, location, concern, quote, minimum_fix"
          className="w-full rounded-lg border border-line px-3 py-2 font-mono text-xs" />
        <button className={btn} disabled={busy || !path || reply.trim().length < 20}
          onClick={() => act(async () => { setRes(await post<Imported>(`/projects/${projectId}/review/import`, { path, text: reply, source })); setSent(false); })}>Import and check the quotes</button>
      </div>

      {res && (
        <div className="mt-4 space-y-2">
          <div className="rounded-lg border border-line p-3 text-sm">
            <b>{res.verified} of {res.total} concerns verified</b> ({res.verified_major} major){res.unverified > 0 && <> · {res.unverified} not verified: their quote is not in the manuscript</>}.
            Saved as <span className="font-mono text-xs">{res.file}</span>.
          </div>
          <ul className="space-y-2 text-sm">
            {res.concerns.map((c) => (
              <li key={c.id} className={`rounded-lg border p-3 ${c.verification === "VERIFIED" ? "border-[#b8e0d2] bg-[#effaf6]" : "border-line bg-[#f6f5f1] opacity-80"}`}>
                <div className="flex flex-wrap items-center gap-2"><b>{c.id}</b>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs">{c.severity}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${c.verification === "VERIFIED" ? "bg-[#dff3e4] text-[#14532d]" : "bg-[#fff4dc] text-[#7a4b06]"}`}>{c.verification === "VERIFIED" ? "verified" : "not verified"}</span>
                  <span className="text-xs text-faint">{c.location}</span></div>
                <p className="mt-1">{c.concern}</p>
                {c.quote && <p className="mt-1 text-xs text-faint">“{c.quote}”</p>}
                {c.minimum_fix && <p className="mt-1 text-xs">Fix: {c.minimum_fix}</p>}
              </li>
            ))}
          </ul>
          {res.feedback_for_revise && (
            <div className="space-y-1">
              <button className={btn} disabled={busy || sent} onClick={() => act(async () => { await post(`/projects/${projectId}/paper/stages/revise/run`, { feedback: res.feedback_for_revise }); setSent(true); onChanged(); })}>
                {sent ? "Sent to the Revise stage" : "3. Send the verified concerns to the Revise stage"}</button>
              <p className="text-xs text-muted">Starts the Revise stage with these concerns. Unverified ones are left out.</p>
            </div>
          )}
        </div>
      )}
      {ls.imports.length > 0 && <p className="mt-3 text-xs text-faint">Earlier imports: {ls.imports.map((i) => `${i.folder} (${i.total ?? "?"} concerns)`).join(", ")}</p>}
    </details>
  );
}
