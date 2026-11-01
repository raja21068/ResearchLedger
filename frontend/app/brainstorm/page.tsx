"use client";

// Brainstorm: pick research areas as chips, press one button, watch the agent search and
// attack its own ideas, then read the surviving ideas as cards with next-step buttons.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, eventsUrl, post } from "@/lib/api";
import type { Project, Run, RunEvent } from "@/lib/types";
import { btn, btn2, ErrorBox } from "@/components/ui";
import { IdeaCard, type Idea } from "@/components/IdeaCards";

const AREAS = ["Blockchain", "LLM", "VLM", "Federated learning", "AI agents", "RAG", "Diffusion models",
  "Medical imaging", "Edge / IoT", "Smart contracts", "Zero-knowledge proofs", "Robotics", "Remote sensing", "Graph neural networks"];
const FOCUS = ["Trust & verifiability", "Privacy", "Security", "Efficiency", "Robustness", "Fairness", "New benchmark/dataset"];


export default function Brainstorm() {
  const [areas, setAreas] = useState<string[]>(["Blockchain", "LLM", "VLM"]);
  const [custom, setCustom] = useState("");
  const [focus, setFocus] = useState<string[]>([]);
  const [n, setN] = useState("5");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [run, setRun] = useState<{ id: string; conv: string; status: string } | null>(null);
  const [steps, setSteps] = useState<RunEvent[]>([]);
  const [ideas, setIdeas] = useState<Idea[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const loadIdeas = useCallback(async (pid: string) => {
    try {
      const p = await api<{ text?: string }>(`/projects/${pid}/files/preview?path=${encodeURIComponent("ideas/ideas.json")}`);
      const parsed = JSON.parse(p.text ?? "{}");
      setIdeas(Array.isArray(parsed.ideas) ? parsed.ideas : []);
    } catch { setIdeas(null); }
  }, []);

  useEffect(() => {
    api<Project[]>("/projects").then((ps) => {
      setProjects(ps);
      const wanted = new URLSearchParams(window.location.search).get("project");
      const pid = ps.find((p) => p.id === wanted)?.id ?? "";
      setProjectId(pid);
      if (pid) loadIdeas(pid);
    }).catch(setError);
    return () => esRef.current?.close();
  }, [loadIdeas]);

  const toggle = (list: string[], set: (x: string[]) => void, v: string) =>
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  function follow(runId: string, pid: string) {
    esRef.current?.close();
    const es = new EventSource(eventsUrl(runId, 0));
    esRef.current = es;
    const onEvent = (ev: MessageEvent) => {
      const e: RunEvent = JSON.parse(ev.data);
      setSteps((s) => (s.some((x) => x.id === e.id) ? s : [...s, e]));
      if (e.kind === "done") setRun((r) => r && { ...r, status: String(e.payload.status) });
    };
    for (const k of ["status", "tool_use", "assistant_text", "error", "done"]) es.addEventListener(k, onEvent as EventListener);
    es.addEventListener("end", () => { es.close(); loadIdeas(pid); setBusy(false); });
  }

  async function generate() {
    const all = [...areas, ...custom.split(",").map((s) => s.trim()).filter(Boolean)];
    if (all.length < 1) { setError(new Error("Pick at least one research area.")); return; }
    setBusy(true); setError(null); setSteps([]); setIdeas(null);
    try {
      let pid = projectId;
      if (!pid) {
        const p = await post<Project>("/projects", { title: `Brainstorm: ${all.slice(0, 3).join(" + ")}`, domain: all.join(", ") });
        pid = p.id; setProjectId(pid); setProjects((ps) => [p, ...ps]);
      }
      const r = await post<{ run_id: string; conversation_id: string }>(`/projects/${pid}/workflows/brainstorm`,
        { values: { areas: all.join(", "), focus: focus.join(", "), n_ideas: n } });
      setRun({ id: r.run_id, conv: r.conversation_id, status: "running" });
      window.history.replaceState(null, "", `/brainstorm?project=${pid}`);
      follow(r.run_id, pid);
    } catch (e) { setError(e); setBusy(false); }
  }

  const failed = run?.status === "failed";
  const toolSteps = steps.filter((s) => s.kind === "tool_use");
  const lastText = [...steps].reverse().find((s) => s.kind === "assistant_text");

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8">
      <h1 className="font-serif text-3xl font-semibold">Brainstorm research ideas</h1>
      <p className="mt-1.5 text-muted">Pick the areas to combine. The agent searches real papers, invents ideas with three personas
        (innovator, pragmatist, critic), tries to kill each idea with prior work, and keeps only falsifiable survivors.</p>

      <section className="mt-6 rounded-2xl border border-line bg-white p-5 sm:p-6">
        <h2 className="text-sm font-semibold">1. Areas to combine</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {AREAS.map((a) => (
            <button key={a} aria-pressed={areas.includes(a)} onClick={() => toggle(areas, setAreas, a)}
              className={`rounded-full border px-3.5 py-1.5 text-sm ${areas.includes(a) ? "border-accent bg-accent text-white" : "border-line bg-white hover:border-[#8796a5]"}`}>
              {areas.includes(a) ? "✓ " : ""}{a}
            </button>
          ))}
        </div>
        <input value={custom} onChange={(e) => setCustom(e.target.value)} aria-label="Other areas"
          placeholder="Other areas, comma separated (e.g. carbon markets, supply chain)"
          className="mt-3 min-h-11 w-full rounded-lg border border-line px-3 text-sm" />

        <h2 className="mt-5 text-sm font-semibold">2. Focus <span className="font-normal text-faint">(optional)</span></h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {FOCUS.map((f) => (
            <button key={f} aria-pressed={focus.includes(f)} onClick={() => toggle(focus, setFocus, f)}
              className={`rounded-full border px-3.5 py-1.5 text-sm ${focus.includes(f) ? "border-ink bg-ink text-white" : "border-line bg-white hover:border-[#8796a5]"}`}>{f}</button>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap items-end gap-4">
          <div>
            <h2 className="text-sm font-semibold">3. How many ideas</h2>
            <div className="mt-2 flex gap-1 rounded-lg bg-[#eef1f4] p-1">
              {["3", "5", "8"].map((x) => (
                <button key={x} onClick={() => setN(x)} aria-pressed={n === x}
                  className={`min-h-9 rounded-md px-4 text-sm ${n === x ? "bg-white font-semibold shadow-sm" : "text-muted"}`}>{x}</button>
              ))}
            </div>
          </div>
          <label className="text-sm font-semibold">Save in project
            <select value={projectId} onChange={(e) => { setProjectId(e.target.value); if (e.target.value) loadIdeas(e.target.value); else setIdeas(null); }}
              className="mt-2 block min-h-11 rounded-lg border border-line bg-white px-2 font-normal">
              <option value="">New project</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </label>
          <button className={`${btn} ml-auto min-h-12 px-6 text-base`} onClick={generate} disabled={busy}>
            {busy ? "Brainstorming…" : "✦ Generate ideas"}
          </button>
        </div>
        {error ? <div className="mt-4"><ErrorBox error={error} /></div> : null}
      </section>

      {run && (
        <section className="mt-6 rounded-2xl border border-line bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold">{busy ? <span className="rl-pulse">Working… this takes a few minutes</span> : failed ? "The brainstorm failed" : "Done"}</h2>
            <Link className="text-sm text-accent underline" href={`/projects/${projectId}?conv=${run.conv}`}>Open full conversation</Link>
          </div>
          <ol className="mt-3 space-y-1.5 text-sm">
            {toolSteps.slice(-8).map((s) => (
              <li key={s.id} className="flex gap-2 text-muted">
                <span className="text-accent">●</span>
                <span className="min-w-0 truncate">{label(String(s.payload.name), String(s.payload.target ?? ""))}</span>
              </li>
            ))}
            {!toolSteps.length && busy && <li className="text-faint">Starting Claude Code…</li>}
          </ol>
          {steps.filter((s) => s.kind === "error").map((s) => <div key={s.id} className="mt-3"><ErrorBox error={String(s.payload.text)} /></div>)}
          {!busy && !failed && lastText && <p className="mt-3 text-sm text-muted">{String(lastText.payload.text).slice(0, 400)}</p>}
        </section>
      )}

      {ideas && ideas.length > 0 && (
        <section className="mt-8">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-semibold">{ideas.length} ideas</h2>
            <Link className={btn2} href={`/view/${projectId}?path=${encodeURIComponent("ideas/ideas.md")}`} target="_blank">Full report ↗</Link>
          </div>
          <div className="grid gap-4">
            {ideas.map((idea, i) => <IdeaCard key={idea.id ?? i} idea={idea} projectId={projectId} />)}
          </div>
          <p className="mt-4 text-xs text-faint">Scores are the agent&apos;s judgement, shown separately and never averaged. No idea has been tested yet:
            “Ready for MVE” means it is worth running the minimum experiment, not that it works.</p>
        </section>
      )}
      {ideas && ideas.length === 0 && !busy && <p className="mt-6 text-sm text-muted">No ideas file was produced in this project yet.</p>}
    </main>
  );
}

function label(name: string, target: string) {
  if (name === "WebSearch") return `Searching: ${target}`;
  if (name === "WebFetch") return `Reading: ${target}`;
  if (name === "Write" || name === "Edit") return `Writing ${target.split(/[\\/]/).slice(-2).join("/")}`;
  if (name === "Read") return `Reading ${target.split(/[\\/]/).slice(-2).join("/")}`;
  return `${name} ${target}`;
}
