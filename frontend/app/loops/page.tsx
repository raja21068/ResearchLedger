"use client";

// Research loops: the prompt rounds you used to type by hand ("why is this not novel?", "score it again",
// "design it again", "review the PDF", "fix it surgically", "check everything again"), run until a stop rule.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { useProject } from "@/lib/useProject";
import type { LoopSummary, LoopType } from "@/lib/loops";
import { STATUS_STYLE } from "@/lib/loops";
import type { WorkspaceFile } from "@/lib/types";
import { btn, Card, Empty, ErrorBox, PageHeader, timeAgo } from "@/components/ui";

const FLOW: Record<string, string[]> = {
  idea_forge: ["Attack: search 50+ recent papers", "Score: your Phase 10 rubric /100", "Redesign the idea", "Repeat until it passes"],
  review_fix: ["Strict review of the PDF", "Fix instructions (MD) for the agent", "Surgical fix + recompile", "Re-review until clean"],
  experiment: ["Pre-registered plan (frozen)", "Agent writes the code", "You approve → server runs it", "Analysis checked vs criteria"],
};

export default function LoopsPage() {
  const router = useRouter();
  const { projects, projectId, setProjectId, error: pErr } = useProject();
  const [types, setTypes] = useState<LoopType[] | null>(null);
  const [loops, setLoops] = useState<LoopSummary[] | null>(null);
  const [texFiles, setTexFiles] = useState<string[]>([]);
  const [pdfFiles, setPdfFiles] = useState<string[]>([]);
  const [example, setExample] = useState("");
  const [type, setType] = useState<LoopType["id"]>("idea_forge");
  const [goal, setGoal] = useState("");
  const [idea, setIdea] = useState("");
  const [manuscript, setManuscript] = useState("");
  const [external, setExternal] = useState("");
  const [experiments, setExperiments] = useState("");
  const [fromLoop, setFromLoop] = useState("");
  const [mode, setMode] = useState<"auto" | "step">("auto");
  const [params, setParams] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => { api<LoopType[]>("/loop-types").then(setTypes).catch(setError); }, []);
  useEffect(() => {  // "Run these experiments" on a review loop links here with ?type=experiment&from=<loop>
    const q = new URLSearchParams(window.location.search);
    if (q.get("type") === "experiment") setType("experiment");
    if (q.get("from")) setFromLoop(q.get("from")!);
  }, []);
  useEffect(() => {
    if (!projectId) { setLoops([]); return; }
    const load = () => api<LoopSummary[]>(`/projects/${projectId}/loops`).then(setLoops).catch(setError);
    load();
    api<WorkspaceFile[]>(`/projects/${projectId}/files`).then((fs) => {
      const tex = fs.map((f) => f.path).filter((p) => p.endsWith(".tex") && !p.includes("_loop"));
      setTexFiles(tex); setManuscript((m) => (tex.includes(m) ? m : tex[0] ?? ""));
      setPdfFiles(fs.map((f) => f.path).filter((p) => p.endsWith(".pdf") && !p.includes("_loop")));
    }).catch(() => setTexFiles([]));
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [projectId]);

  const spec = types?.find((t) => t.id === type);

  async function upload(f: File) {
    let pid = projectId;
    if (!pid) pid = (await post<{ id: string }>("/projects", { title: f.name.replace(/\.tex$/, "") })).id;
    const fd = new FormData(); fd.append("file", f);
    const r = await api<{ path: string }>(`/projects/${pid}/files?folder=paper`, { method: "POST", body: fd });
    if (pid !== projectId) setProjectId(pid);
    setTexFiles((t) => [...new Set([...t, r.path])]); setManuscript(r.path);
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      let pid = projectId;
      if (!pid) pid = (await post<{ id: string }>("/projects", { title: (goal || idea).slice(0, 60) || "Research loop" })).id;
      const body = { type, goal, mode, params,
        idea_text: type === "idea_forge" && idea.trim() ? idea : null,
        manuscript: type === "review_fix" || (type === "experiment" && manuscript) ? manuscript || null : null,
        experiments_text: type === "experiment" && experiments.trim() ? experiments : null,
        from_loop: type === "experiment" && fromLoop ? fromLoop : null,
        external_review: type === "review_fix" && external.trim() ? external : null,
        example_pdf: type === "review_fix" && example ? example : null };
      const v = await post<{ id: string }>(`/projects/${pid}/loops`, body);
      router.push(`/projects/${pid}/loops/${v.id}`);
    } catch (err) { setError(err); setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8">
      <PageHeader title="Research Loops"
        sub="The rounds you used to drive prompt by prompt, run for you. The server checks every round itself — references looked up, review quotes found in the paper, edits kept surgical — and stops when the result passes or stops improving." />
      <ErrorBox error={error || pErr} />

      <Card className="mb-8 p-6">
        <form onSubmit={start} className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {types?.map((t) => (
              <button type="button" key={t.id} onClick={() => { setType(t.id); setParams({}); }} aria-pressed={type === t.id}
                className={`rounded-xl border p-4 text-left ${type === t.id ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-[#8796a5]"}`}>
                <div className="font-semibold">{t.label}</div>
                <div className="mt-1 text-xs text-muted">{t.pitch}</div>
                <ol className="mt-3 flex flex-wrap gap-1 text-[11px] text-ink">
                  {FLOW[t.id].map((s, i) => <li key={i} className="rounded-full border border-line bg-white px-2 py-0.5">{i + 1}. {s}</li>)}
                </ol>
              </button>
            ))}
          </div>

          <label className="grid gap-1 text-sm font-medium">Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal">
              <option value="">New project</option>
              {projects?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </label>

          {type === "idea_forge" ? (
            <>
              <label className="grid gap-1 text-sm font-medium">Topic or research direction
                <input value={goal} onChange={(e) => setGoal(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal"
                  placeholder="e.g. Blockchain + LLM/VLM: verifiable model oracles for smart contracts" />
              </label>
              <label className="grid gap-1 text-sm font-medium">Your idea (optional — leave empty and it generates and ranks candidates first)
                <textarea rows={6} value={idea} onChange={(e) => setIdea(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal"
                  placeholder="Paste the idea you want attacked: problem, claim, method…" />
              </label>
            </>
          ) : type === "experiment" ? (
            <>
              {fromLoop && (
                <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-[#f7f5f1] px-3 py-2 text-sm">
                  Starts from the experiments review loop <b className="font-mono text-xs">{fromLoop}</b> asked for.
                  <button type="button" className="ml-auto text-xs text-accent underline" onClick={() => setFromLoop("")}>Don&apos;t use them</button>
                </div>
              )}
              <label className="grid gap-1 text-sm font-medium">Experiments to run {fromLoop ? "(optional — added to the reviewers' list)" : ""}
                <textarea rows={6} value={experiments} onChange={(e) => setExperiments(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal"
                  placeholder="e.g. Reviewer 2: compare against a keyword-matching baseline on the same 100 projects; ablate the verifier." />
              </label>
              <label className="grid gap-1 text-sm font-medium">Paper these are for (optional)
                <select value={manuscript} onChange={(e) => setManuscript(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal">
                  <option value="">None</option>
                  {texFiles.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </label>
              <p className="text-xs text-faint">Nothing runs without your click: when the code is ready the loop waits, shows the exact commands, and the server runs them on this computer only after you approve. Results count only if that run wrote them.</p>
            </>
          ) : (
            <>
              <div className="grid gap-1 text-sm font-medium">Manuscript (.tex in this project)
                <div className="flex flex-wrap gap-2">
                  <select value={manuscript} onChange={(e) => setManuscript(e.target.value)} className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 font-normal">
                    {texFiles.length === 0 && <option value="">No .tex file yet — upload one</option>}
                    {texFiles.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                  <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-line bg-white px-4 text-sm font-medium hover:border-[#8796a5]">
                    Upload .tex
                    <input type="file" accept=".tex" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f).catch(setError); }} />
                  </label>
                </div>
                <span className="text-xs font-normal text-faint">Figures and .bib must sit next to the .tex in the workspace so it compiles.</span>
              </div>
              <label className="grid gap-1 text-sm font-medium">Example paper to match — style, length, structure (optional)
                <select value={example} onChange={(e) => setExample(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal">
                  <option value="">None</option>
                  {pdfFiles.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-sm font-medium">Goal (optional)
                <input value={goal} onChange={(e) => setGoal(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal"
                  placeholder="e.g. Submission-ready for IEEE TDSC" />
              </label>
              <label className="grid gap-1 text-sm font-medium">External review to start from (optional — paste ChatGPT's review here)
                <textarea rows={5} value={external} onChange={(e) => setExternal(e.target.value)} className="rounded-lg border border-line px-3 py-2 font-normal"
                  placeholder="Each point is checked against the manuscript; invalid points are rejected with a reason." />
              </label>
            </>
          )}

          <details className="rounded-lg border border-line px-3 py-2 text-sm">
            <summary className="cursor-pointer font-medium">Stop rules and limits</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              {spec && Object.entries(spec.params).map(([k, v]) => (
                <label key={k} className="grid gap-1 text-xs font-medium text-muted">{k.replace(/_/g, " ")}
                  <input type="number" step="any" value={params[k] ?? v} className="rounded-lg border border-line px-2 py-1.5 text-sm text-ink"
                    onChange={(e) => setParams({ ...params, [k]: Number(e.target.value) })} />
                </label>
              ))}
            </div>
          </details>

          <fieldset className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="radio" checked={mode === "auto"} onChange={() => setMode("auto")} /> Run until the stop rule (you approve the final result)</label>
            <label className="flex items-center gap-2"><input type="radio" checked={mode === "step"} onChange={() => setMode("step")} /> Pause after every round</label>
          </fieldset>

          <div><button className={btn} disabled={busy || (type === "review_fix" ? !manuscript
            : type === "experiment" ? !(experiments.trim() || fromLoop) : !(goal.trim() || idea.trim()))}>Start loop</button></div>
        </form>
      </Card>

      <h2 className="mb-3 text-xs font-bold uppercase tracking-[.1em] text-faint">Loops in this project</h2>
      {loops && loops.length === 0 && <Empty title="No loops yet">Start one above.</Empty>}
      <ul className="divide-y divide-line rounded-xl border border-line bg-white">
        {loops?.map((l) => (
          <li key={l.id}>
            <Link href={`/projects/${projectId}/loops/${l.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm hover:bg-[#f7f5f1]">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[l.status][1]}`}>{STATUS_STYLE[l.status][0]}</span>
              <span className="min-w-0 flex-1 truncate"><b>{l.label}</b> · {l.goal}</span>
              <span className="text-xs text-faint">round {l.round}{l.score != null ? ` · ${l.score}/100` : ""}{l.verified_major != null ? ` · ${l.verified_major} major` : ""}{l.measured ? ` · ${l.measured} measured` : ""} · {timeAgo(l.created_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
