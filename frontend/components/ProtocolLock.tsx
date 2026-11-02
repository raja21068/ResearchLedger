"use client";

// Protocol lock: approving the Method & experiment plan freezes the protocol and the declared result slots.
// If either changes afterwards, nothing after the Method stage can continue until you approve a recorded amendment
// (a reason, and what it affects) or restore the locked protocol. Locked copies are never overwritten.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn, btn2, ErrorBox } from "./ui";

interface Amendment { id: string; status: string; reason: string; affects: string; proposed_at: string; from_version: number;
  version_after?: number; slots_added: string[]; slots_removed: string[]; slots_changed: string[]; diff: string[]; protocol_changed: boolean }
interface Lock {
  has_method_stage: boolean; locked: boolean; version?: number; locked_at?: string; reason?: string; changed?: boolean; protocol_file?: string; method_approved?: boolean;
  protocol_changed?: boolean; slots_added?: string[]; slots_removed?: string[]; slots_changed?: string[]; diff?: string[];
  amendments: Amendment[]; pending?: boolean; planned_tables: boolean; slots_note?: string | null;
  draft: { exists: boolean; result_numbers: string[]; forbidden_sections: string[] };
}

export function ProtocolLock({ projectId, onChanged }: { projectId: string; onChanged: () => void }) {
  const [lk, setLk] = useState<Lock | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [affects, setAffects] = useState("");

  const load = useCallback(() => { api<Lock>(`/projects/${projectId}/paper/lock`).then(setLk).catch(setError); }, [projectId]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); load(); onChanged(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  if (!lk || !lk.has_method_stage) return null;
  const view = (p: string) => `/view/${projectId}?path=${encodeURIComponent(p)}`;
  const pending = lk.amendments.find((a) => a.status === "pending");

  return (
    <section className="mb-5 rounded-2xl border border-line bg-white p-4" aria-label="Protocol lock">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">Protocol lock</h2>
        {!lk.locked && <span className="rounded-full bg-[#f4f5f7] px-2 py-0.5 text-xs text-muted">{lk.method_approved ? "approved, but not locked" : "not locked yet: approve the Method & experiment plan to lock it"}</span>}
        {!lk.locked && lk.method_approved && (
          <button className={btn2} disabled={busy} onClick={() => { if (window.confirm("Freeze the current protocol and declared result slots? Later changes will need a recorded amendment.")) act(() => post(`/projects/${projectId}/paper/lock`)); }}>Lock the approved plan now</button>
        )}
        {lk.locked && !lk.changed && <span className="rounded-full bg-[#dff3e4] px-2 py-0.5 text-xs font-semibold text-[#14532d]">locked · version {lk.version}</span>}
        {lk.locked && lk.changed && <span className="rounded-full bg-[#fbe4e4] px-2 py-0.5 text-xs font-semibold text-[#7f1d1d]">changed since the lock · later stages are blocked</span>}
        {lk.locked && lk.protocol_file && <Link className="ml-auto text-xs text-accent underline" target="_blank" href={view(`paper/locked/protocol.v${lk.version}.md`)}>View locked protocol</Link>}
      </div>
      <p className="mt-1 text-sm text-muted">
        Hypotheses, datasets, baselines, metrics and the statistical plan are frozen when you approve the plan. Changing them later needs a recorded reason and your approval, so the plan cannot drift after disappointing results.
      </p>
      <ErrorBox error={error} />

      {lk.locked && lk.changed && (
        <div className="mt-3 space-y-2 rounded-lg border border-[#f0c4c4] bg-[#fdf1f1] p-3 text-sm">
          <b>What changed</b>
          <ul className="list-disc pl-5 text-xs">
            {lk.protocol_changed && <li>The protocol text (<span className="font-mono">paper/protocol.md</span>) differs from the lock.</li>}
            {lk.slots_added?.length ? <li>Result slots added: <span className="font-mono">{lk.slots_added.join(", ")}</span></li> : null}
            {lk.slots_removed?.length ? <li>Result slots removed: <span className="font-mono">{lk.slots_removed.join(", ")}</span></li> : null}
            {lk.slots_changed?.length ? <li>Result slots whose metric, unit, dataset or method changed: <span className="font-mono">{lk.slots_changed.join(", ")}</span></li> : null}
          </ul>
          {lk.diff && lk.diff.length > 0 && (
            <details><summary className="cursor-pointer text-xs">Show the text changes</summary>
              <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-white p-2 font-mono text-[11px]">{lk.diff.join("\n")}</pre></details>
          )}
          {!pending ? (
            <div className="space-y-2">
              <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Why is this change necessary"
                placeholder="Why is this change necessary? (at least a sentence; it is kept with the amendment)" className="w-full rounded-lg border border-line px-3 py-2 text-sm" />
              <input value={affects} onChange={(e) => setAffects(e.target.value)} aria-label="What it affects" placeholder="Which experiments or results does it affect?"
                className="w-full rounded-lg border border-line px-3 py-2 text-sm" />
              <div className="flex flex-wrap gap-2">
                <button className={btn} disabled={busy || reason.trim().length < 10} onClick={() => act(async () => { await post(`/projects/${projectId}/paper/lock/amendments`, { reason, affects }); setReason(""); setAffects(""); })}>Record amendment</button>
                <button className={btn2} disabled={busy} onClick={() => { if (window.confirm("Put the locked protocol back? Your edits to paper/protocol.md are replaced (they stay in the file history).")) act(() => post(`/projects/${projectId}/paper/lock/restore`)); }}>Restore the locked protocol</button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <p><b>Amendment {pending.id} is waiting for your decision.</b> Reason: {pending.reason}{pending.affects ? ` · Affects: ${pending.affects}` : ""}</p>
              <p className="text-xs text-muted">Approving makes the changed protocol lock version {(lk.version ?? 0) + 1} and reopens the stages after Method, so work built on the old plan is looked at again. Rejecting puts the locked protocol back.</p>
              <div className="flex flex-wrap gap-2">
                <button className={btn} disabled={busy} onClick={() => act(() => post(`/projects/${projectId}/paper/lock/amendments/${pending.id}/decision`, { approve: true }))}>Approve amendment</button>
                <button className={btn2} disabled={busy} onClick={() => act(() => post(`/projects/${projectId}/paper/lock/amendments/${pending.id}/decision`, { approve: false }))}>Reject and restore</button>
              </div>
            </div>
          )}
        </div>
      )}

      {lk.slots_note && <p className="mt-2 rounded bg-[#fffaf0] p-2 text-xs text-[#7a4b06]">{lk.slots_note}</p>}
      {lk.locked && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {lk.planned_tables && <Link className="text-accent underline" target="_blank" href={view("paper/planned_tables.md")}>Planned result tables (all Pending)</Link>}
          {lk.draft.exists && <Link className="text-accent underline" target="_blank" href={view("paper/pre_experiment_draft.md")}>Draft before coding</Link>}
        </div>
      )}
      {lk.draft.exists && (lk.draft.result_numbers.length > 0 || lk.draft.forbidden_sections.length > 0) && (
        <p className="mt-2 rounded bg-[#fffaf0] p-2 text-xs text-[#7a4b06]">
          The draft before coding should contain no results, but it has
          {lk.draft.forbidden_sections.length > 0 && <> a “{lk.draft.forbidden_sections.map((h) => h.replace(/^#+\s*/, "")).join("”, “")}” section</>}
          {lk.draft.forbidden_sections.length > 0 && lk.draft.result_numbers.length > 0 && " and"}
          {lk.draft.result_numbers.length > 0 && <> decimal or percentage numbers ({lk.draft.result_numbers.slice(0, 6).join(", ")}). Planned values such as thresholds are fine; check that none is a finding.</>}
        </p>
      )}
      {lk.amendments.length > 0 && (
        <details className="mt-3 text-xs"><summary className="cursor-pointer text-muted">Amendments ({lk.amendments.length})</summary>
          <ul className="mt-1 space-y-1">{lk.amendments.map((a) => (
            <li key={a.id}><b>{a.id}</b> · {a.status}{a.version_after ? ` → lock version ${a.version_after}` : ""} · {a.reason}{a.affects ? ` (affects: ${a.affects})` : ""}</li>
          ))}</ul></details>
      )}
    </section>
  );
}
