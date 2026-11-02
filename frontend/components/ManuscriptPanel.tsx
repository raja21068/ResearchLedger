"use client";

// Evidence side panel for a LaTeX manuscript: where every number in the tables and abstract comes from, how far it
// has been reviewed, and what is still a placeholder. It shows provenance; it never says a number is correct.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { btn2, ErrorBox } from "./ui";

interface Num {
  value: string; where: string; context: string; slot: string | null; file?: string; unit?: string | null; run?: string | null;
  evidence?: { id: string; status: string } | null; backing: "backed" | "recorded" | "measured" | "untraced"; other_slots?: string[];
}
interface Trace {
  numbers: Num[]; counts: Record<string, number>; reported: number; placeholders: { line: number; text: string }[];
  slots: { slot: string; value: number; used: boolean; evidence: { id: string; status: string } | null; run: string | null }[];
  unused_slots: string[]; sources: number; sections: string[]; tables: number; figures: number; words: number; notes: string[];
}

const BACKING: Record<string, [string, string, string]> = {
  backed: ["backed", "bg-[#dff3e4] text-[#14532d]", "Matches a measured result whose evidence you checked or verified."],
  recorded: ["recorded", "bg-[#fff4dc] text-[#7a4b06]", "Matches a recorded run; the evidence is still only “observed” (you have not reviewed it)."],
  measured: ["measured", "bg-[#e6eefb] text-[#1e3a8a]", "Matches a results file, but no recorded run or evidence is known for it."],
  untraced: ["untraced", "bg-[#fbe4e4] text-[#7f1d1d]", "Matches no measured result. Planned values (thresholds, sample sizes) are expected here; a number that claims a finding is worth checking."],
};

export function ManuscriptPanel({ projectId, path, refreshKey }: { projectId: string; path: string; refreshKey: number }) {
  const [t, setT] = useState<Trace | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState<"numbers" | "results" | "gaps">("numbers");
  const [only, setOnly] = useState<string>("");

  const load = useCallback(() => {
    setError(null);
    api<Trace>(`/projects/${projectId}/manuscript/trace?path=${encodeURIComponent(path)}`).then(setT).catch(setError);
  }, [projectId, path]);
  useEffect(load, [load, refreshKey]);

  const nums = (t?.numbers ?? []).filter((n) => !only || n.backing === only);
  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-white">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="text-sm font-semibold">Evidence</span>
        <button className="text-xs text-faint hover:text-ink" onClick={load}>Refresh</button>
      </div>
      {error ? <div className="p-3"><ErrorBox error={error} /></div> : null}
      {!t && !error && <p className="rl-pulse p-3 text-sm text-faint">Tracing numbers…</p>}
      {t && (
        <>
          <div className="grid grid-cols-3 gap-2 border-b border-line p-3 text-center text-xs">
            <div className="rounded-lg bg-[#f6f5f1] p-2"><div className="text-lg font-semibold">{t.sources}</div>sources cited</div>
            <div className="rounded-lg bg-[#f6f5f1] p-2"><div className="text-lg font-semibold">{t.tables}/{t.figures}</div>tables / figures</div>
            <div className="rounded-lg bg-[#f6f5f1] p-2"><div className="text-lg font-semibold">{t.placeholders.length}</div>placeholders</div>
          </div>
          <div className="border-b border-line p-3 text-xs">
            <div className="mb-1 font-semibold">{t.reported} number(s) in tables and the abstract</div>
            <div className="flex flex-wrap gap-1">
              {(["backed", "recorded", "measured", "untraced"] as const).map((k) => (
                <button key={k} title={BACKING[k][2]} onClick={() => setOnly(only === k ? "" : k)} aria-pressed={only === k}
                  className={`rounded-full px-2 py-0.5 ${BACKING[k][1]} ${only === k ? "ring-2 ring-accent" : ""}`}>{t.counts[k] ?? 0} {BACKING[k][0]}</button>
              ))}
            </div>
            {t.notes.map((n) => <p key={n} className="mt-2 rounded bg-[#fffaf0] p-2 text-[#7a4b06]">{n}</p>)}
          </div>
          <div className="flex border-b border-line text-xs" role="tablist">
            {([["numbers", "Numbers"], ["results", `Results (${t.slots.length})`], ["gaps", "Gaps"]] as const).map(([v, l]) => (
              <button key={v} role="tab" aria-selected={tab === v} onClick={() => setTab(v)}
                className={`flex-1 border-b-2 px-2 py-2 ${tab === v ? "border-accent font-semibold" : "border-transparent text-muted"}`}>{l}</button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-3 text-xs">
            {tab === "numbers" && (
              <ul className="space-y-2">
                {nums.map((n, i) => (
                  <li key={i} className="rounded-lg border border-line p-2">
                    <div className="flex items-center gap-2"><b className="font-mono text-sm">{n.value}</b>
                      <span className={`rounded-full px-2 py-0.5 ${BACKING[n.backing][1]}`}>{BACKING[n.backing][0]}</span>
                      <span className="ml-auto text-faint">{n.where}</span></div>
                    <div className="mt-1 text-faint">…{n.context}…</div>
                    {n.slot && (
                      <div className="mt-1">
                        <span className="font-mono">{n.slot}</span> · <span className="font-mono">{n.file}</span>
                        {n.run && <> · run <span className="font-mono">{n.run}</span></>}
                        {n.evidence && <> · <Link className="text-accent underline" href={`/projects/${projectId}/evidence`}>{n.evidence.id} ({n.evidence.status})</Link></>}
                        {n.other_slots && n.other_slots.length > 0 && <div className="text-faint">also matches: {n.other_slots.join(", ")}</div>}
                      </div>
                    )}
                  </li>
                ))}
                {!nums.length && <li className="text-faint">{t.reported ? "None in this group." : "No numbers in tables or the abstract."}</li>}
              </ul>
            )}
            {tab === "results" && (
              <ul className="space-y-2">
                {t.slots.map((s) => (
                  <li key={s.slot} className="rounded-lg border border-line p-2">
                    <div className="flex items-center gap-2"><span className="font-mono">{s.slot}</span> = <b>{s.value}</b>
                      <span className={`ml-auto rounded-full px-2 py-0.5 ${s.used ? "bg-[#dff3e4] text-[#14532d]" : "bg-[#f4f5f7] text-faint"}`}>{s.used ? "used" : "not used"}</span></div>
                    <div className="text-faint">{s.evidence ? `${s.evidence.id} (${s.evidence.status})` : "no recorded evidence"}{s.run ? ` · run ${s.run}` : ""}</div>
                  </li>
                ))}
                {!t.slots.length && <li className="text-faint">No measured result files yet.</li>}
                {t.slots.length > 0 && <li><Link className={btn2} href={`/projects/${projectId}/lab`}>Open experiment records</Link></li>}
              </ul>
            )}
            {tab === "gaps" && (
              <div className="space-y-3">
                <div><b>Placeholders ({t.placeholders.length})</b>
                  <ul className="mt-1 space-y-1">{t.placeholders.map((p, i) => <li key={i} className="text-faint">line {p.line}: {p.text}</li>)}
                    {!t.placeholders.length && <li className="text-faint">None.</li>}</ul></div>
                <div><b>Measured but not used ({t.unused_slots.length})</b>
                  <p className="mt-1 font-mono text-faint">{t.unused_slots.join(", ") || "none"}</p></div>
                <div><b>Sections</b><p className="mt-1 text-faint">{t.sections.join(" · ") || "none found"} · {t.words} words</p></div>
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
