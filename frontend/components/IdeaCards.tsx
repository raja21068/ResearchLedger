"use client";

// Research idea cards (from ideas/ideas.json written by the Brainstorm tool). Used on
// the Brainstorm page and inline in chats whose run produced ideas.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { PaperView } from "@/lib/paper";
import { btn, btn2 } from "./ui";

/** Start (or continue) this project's research-article paper from the chosen idea. */
function UseForPaper({ idea, projectId }: { idea: Idea; projectId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    setBusy(true); setErr(null);
    try {
      const existing = await api<PaperView | null>(`/projects/${projectId}/paper`);
      if (!existing) await post(`/projects/${projectId}/paper`, { type: "research_article", venue: "journal", topic: idea.title });
      await post(`/projects/${projectId}/paper/choose-idea/${encodeURIComponent(idea.id)}`);
      router.push(`/projects/${projectId}/paper`);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); setBusy(false); }
  }
  return (
    <>
      <button className={btn} onClick={go} disabled={busy}>{busy ? "Starting…" : "Use this idea for a paper →"}</button>
      {err && <span className="w-full text-xs text-[#7f1d1d]">{err}</span>}
    </>
  );
}

export interface Idea {
  id: string; title: string; pitch: string; areas?: string[]; problem: string; why_open?: string;
  closest_work?: { title: string; year?: number; url_or_doi?: string; difference?: string }[];
  novelty_type?: string; hypothesis: string; null_hypothesis?: string; method: string;
  falsifier?: { metric?: string; threshold?: string; statement?: string };
  minimum_experiment?: string; risks?: string[]; scores?: Record<string, number>; verdict?: string;
}

export function IdeaList({ projectId, version = 0, compact = false }: { projectId: string; version?: number; compact?: boolean }) {
  const [ideas, setIdeas] = useState<Idea[] | null>(null);
  useEffect(() => {
    api<{ text?: string }>(`/projects/${projectId}/files/preview?path=${encodeURIComponent("ideas/ideas.json")}`)
      .then((p) => { const d = JSON.parse(p.text ?? "{}"); setIdeas(Array.isArray(d.ideas) ? d.ideas : []); })
      .catch(() => setIdeas(null));
  }, [projectId, version]);
  if (!ideas?.length) return null;
  return (
    <div className="grid gap-3">
      {!compact && <div className="text-sm font-semibold">{ideas.length} ideas</div>}
      {ideas.map((idea, i) => <IdeaCard key={idea.id ?? i} idea={idea} projectId={projectId} />)}
      <p className="text-xs text-faint">Scores are the agent&apos;s judgement, shown separately and never averaged. “Ready for MVE”
        means worth testing with the minimum experiment, not that it works.</p>
    </div>
  );
}

export function IdeaCard({ idea, projectId }: { idea: Idea; projectId: string }) {
  const [open, setOpen] = useState(false);
  const topic = `${idea.title}. ${idea.problem}`;
  const verdict = (idea.verdict ?? "").toUpperCase();
  const tone = verdict.startsWith("READY") ? "bg-[#d4eee9] text-[#07423d]" : verdict.startsWith("KILL") ? "bg-[#f3d9d9] text-[#7f1d1d]" : "bg-[#fbe7cf] text-[#7a3a06]";
  return (
    <article className="rounded-2xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 text-lg font-semibold leading-snug">{idea.title}</h3>
        {idea.verdict && <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>{verdict.replace(/_/g, " ")}</span>}
      </div>
      <p className="mt-1.5 text-[15px] text-muted">{idea.pitch}</p>
      {idea.scores && (
        <div className="mt-3 flex flex-wrap gap-4 text-sm">
          {Object.entries(idea.scores).map(([k, v]) => (
            <span key={k} className="flex items-center gap-2"><span className="capitalize text-faint">{k}</span>
              <span className="h-1.5 w-16 overflow-hidden rounded bg-[#eef1f4]"><span className="block h-full bg-accent" style={{ width: `${Math.max(0, Math.min(10, v)) * 10}%` }} /></span>
              <span className="font-mono text-xs">{v}/10</span></span>
          ))}
        </div>
      )}
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="font-semibold">Problem</dt><dd className="text-muted">{idea.problem}</dd></div>
        <div><dt className="font-semibold">Hypothesis</dt><dd className="text-muted">{idea.hypothesis}</dd></div>
      </dl>
      {open && (
        <dl className="mt-3 grid gap-3 border-t border-line pt-3 text-sm sm:grid-cols-2">
          {idea.why_open && <div><dt className="font-semibold">Why it is still open</dt><dd className="text-muted">{idea.why_open}</dd></div>}
          {idea.novelty_type && <div><dt className="font-semibold">Novelty</dt><dd className="text-muted">{idea.novelty_type}</dd></div>}
          <div><dt className="font-semibold">Method</dt><dd className="text-muted">{idea.method}</dd></div>
          {idea.falsifier && <div><dt className="font-semibold">What would prove it wrong</dt>
            <dd className="text-muted">{idea.falsifier.statement} <span className="font-mono text-xs">({idea.falsifier.metric} · {idea.falsifier.threshold})</span></dd></div>}
          {idea.minimum_experiment && <div className="sm:col-span-2"><dt className="font-semibold">Minimum experiment</dt><dd className="text-muted">{idea.minimum_experiment}</dd></div>}
          {idea.closest_work && idea.closest_work.length > 0 && (
            <div className="sm:col-span-2"><dt className="font-semibold">Closest existing work</dt>
              <dd><ul className="mt-1 space-y-1">{idea.closest_work.map((w, i) => (
                <li key={i} className="text-muted">
                  {w.url_or_doi ? <a className="text-accent underline" target="_blank" rel="noreferrer noopener"
                    href={w.url_or_doi.startsWith("http") ? w.url_or_doi : `https://doi.org/${w.url_or_doi}`}>{w.title}</a> : w.title}
                  {w.year ? ` (${w.year})` : ""}{w.difference ? ` — ${w.difference}` : ""}
                </li>))}</ul></dd></div>
          )}
          {idea.risks && idea.risks.length > 0 && <div className="sm:col-span-2"><dt className="font-semibold">Likely reviewer objections</dt>
            <dd><ul className="ml-5 list-disc text-muted">{idea.risks.map((r, i) => <li key={i}>{r}</li>)}</ul></dd></div>}
        </dl>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className={btn2} onClick={() => setOpen(!open)}>{open ? "Less" : "Details"}</button>
        <Link className={btn2} href={`/tools/literature_review?project=${projectId}&topic=${encodeURIComponent(topic)}`}>Literature review</Link>
        <Link className={btn2} href={`/tools/research_proposal?project=${projectId}&topic=${encodeURIComponent(topic)}`}>Write proposal</Link>
        <Link className={btn2} href={`/tools/research_design?project=${projectId}&question=${encodeURIComponent(idea.hypothesis)}`}>Design the study</Link>
        <UseForPaper idea={idea} projectId={projectId} />
      </div>
    </article>
  );
}
