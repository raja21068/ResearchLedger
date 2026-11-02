"use client";

// Home: one box for any job. Drop files or type; the box shows which tool will run (Tool), where the work is
// kept (Where: a quick job, or one of your papers), and whether it repeats until a stop rule (Repeat until).
// Below: quick tools that work without a project, and one Recent list for quick jobs and papers.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { parseCommand, runCommand, useCommands } from "@/lib/commands";
import type { Project } from "@/lib/types";
import type { Recipe } from "@/lib/recipes";
import { Composer } from "@/components/Composer";
import { ErrorBox } from "@/components/ui";

const QUICK = "__quick";
const NEW_PAPER = "__new";
const REPEAT: [string, string][] = [
  ["", "Off · one pass"],
  ["review", "Review → fix until clean or your targets (needs the .tex)"],
  ["idea", "Attack → score → redesign until the idea passes"],
];
// Tools that are not ready-made recipes: loops and checks the home box can open directly.
const EXTRA: { label: string; hint: string; href?: string; repeat?: string; prompt?: string }[] = [
  { label: "Novelty attack", hint: "50+ papers vs your idea, repeated", repeat: "idea", prompt: "Why is this idea not novel? " },
  { label: "Submission check", hint: ".tex gate: refs, numbers, figures", href: "/quality" },
  { label: "Run an experiment", hint: "pre-registered, runs after your click", href: "/loops?type=experiment" },
];

interface Recent { id: string; project_id: string; title: string; project_title: string; project_kind?: string; updated_at: string; last_status: string | null }
interface Preview { mode: string; tool: string | null; why: string }

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Working late?" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function Home() {
  const router = useRouter();
  const { commands, workflows } = useCommands();
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [papers, setPapers] = useState<Project[]>([]);
  const [where, setWhere] = useState(QUICK);
  const [repeat, setRepeat] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [hello, setHello] = useState("What should we research today?");

  useEffect(() => {
    setHello(greeting());
    const q = new URLSearchParams(window.location.search);
    const tool = q.get("tool");
    if (tool) setPrompt(`/${tool.replace(/^skill-/, "")} `);
    api<Project[]>("/projects?kind=paper").then((ps) => {
      setPapers(ps);
      if (ps.some((p) => p.id === q.get("project"))) setWhere(q.get("project")!);
    }).catch(setError);
    api<Recipe[]>("/recipes").then(setRecipes).catch(() => {});
    api<Recent[]>("/conversations?limit=8").then(setRecent).catch(() => {});
  }, []);

  // Live preview of the tool that Start will use (server-side rules, nothing starts).
  useEffect(() => {
    if (!prompt.trim() && !files.length && !repeat) { setPreview(null); return; }
    if (prompt.startsWith("/")) { setPreview({ mode: "command", tool: prompt.split(" ")[0], why: "the tool you typed" }); return; }
    const t = setTimeout(() => {
      post<Preview>("/autopilot/classify", { goal: prompt, filenames: files.map((f) => f.name), repeat: repeat || null })
        .then(setPreview).catch(() => setPreview(null));
    }, 350);
    return () => clearTimeout(t);
  }, [prompt, files, repeat]);

  async function target(): Promise<string> {
    if (where !== QUICK && where !== NEW_PAPER) return where;
    const title = (prompt.replace(/^\/\S+\s*/, "").trim() || files[0]?.name || "Quick job").slice(0, 80);
    const p = await post<Project>("/projects", { title, kind: where === QUICK ? "quick" : "paper" });
    return p.id;
  }

  async function send() {
    if ((!prompt.trim() && !files.length) || busy) return;
    if (preview?.mode === "invalid") { setError(preview.why); return; }
    setBusy(true); setError(null);
    try {
      const pid = await target();
      const paths: string[] = [];
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        paths.push((await api<{ path: string }>(`/projects/${pid}/files?folder=uploads`, { method: "POST", body: fd })).path);
      }
      const parsed = parseCommand(prompt, commands);
      if (parsed) { router.push(await runCommand(pid, parsed.cmd, parsed.rest, workflows, paths, model || null)); return; }
      const r = await post<{ url: string }>(`/projects/${pid}/autopilot/start`,
        { goal: prompt, files: paths, model: model || null, repeat: repeat || null });
      router.push(r.url);
    } catch (e) { setError(e); setBusy(false); }
  }

  const addFiles = (list: FileList) => setFiles((fs) => [...fs, ...Array.from(list).filter((f) => !fs.some((x) => x.name === f.name))]);
  const select = "rounded-md border border-line bg-white px-2 py-1 text-xs text-ink hover:border-[#8796a5]";

  return (
    <main className="flex min-h-screen flex-col items-center px-4 pb-16 pt-[12vh]">
      <h1 className="mb-8 flex items-center gap-3 text-center font-serif text-3xl font-medium text-ink sm:text-[40px]">
        <span aria-hidden="true" className="text-[#d97757]">✳</span>{hello}
      </h1>
      <div className="w-full max-w-[760px]"
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); }}>
        <Composer value={prompt} onChange={setPrompt} onSend={send} busy={busy} commands={commands} autoFocus
          onAttach={addFiles} attached={files.map((f) => f.name)} onDetach={(n) => setFiles((fs) => fs.filter((f) => f.name !== n))}
          model={model} onModel={setModel} placeholder="Drop a PDF, .tex, idea or review — or type what you need (/ for tools)"
          footer={
            <div className="mt-2 grid gap-1.5 text-xs text-faint">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                <span className="flex items-center gap-1.5">Tool:
                  {preview?.tool
                    ? <span className="rounded-md bg-accent-soft px-2 py-0.5 font-medium text-accent" title={preview.why}>{preview.tool}</span>
                    : preview?.mode === "invalid" ? <span className="text-[#8a1f17]">{preview.why}</span>
                    : <span>chosen from what you type</span>}
                </span>
                <label className="flex items-center gap-1.5">Where:
                  <select value={where} onChange={(e) => setWhere(e.target.value)} className={select} aria-label="Where to keep this work">
                    <option value={QUICK}>Just this once (quick job)</option>
                    {papers.length > 0 && <optgroup label="Add to paper">
                      {papers.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                    </optgroup>}
                    <option value={NEW_PAPER}>+ New paper</option>
                  </select>
                </label>
                <label className="flex items-center gap-1.5">Repeat until:
                  <select value={repeat} onChange={(e) => setRepeat(e.target.value)} className={`${select} max-w-[260px]`} aria-label="Repeat until">
                    {REPEAT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
              </div>
              {preview?.why && preview.mode !== "invalid" && preview.mode !== "command" && <span>Why: {preview.why}</span>}
            </div>
          } />
        {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}

        <h2 className="mb-2 mt-10 text-xs font-bold uppercase tracking-[.1em] text-faint">Quick tools — work without a project</h2>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {recipes.map((r) => (
            <Link key={r.id} href={`/do/${r.id}`} className="rounded-xl border border-line bg-white px-3 py-2.5 hover:border-accent">
              <div className="text-sm font-semibold">{r.name}</div>
              <div className="truncate text-xs text-faint" title={r.pitch}>{r.pitch}</div>
            </Link>
          ))}
          {EXTRA.map((x) => x.href ? (
            <Link key={x.label} href={x.href} className="rounded-xl border border-line bg-white px-3 py-2.5 hover:border-accent">
              <div className="text-sm font-semibold">{x.label}</div><div className="truncate text-xs text-faint">{x.hint}</div>
            </Link>
          ) : (
            <button key={x.label} onClick={() => { setRepeat(x.repeat ?? ""); setPrompt(x.prompt ?? ""); document.getElementById("composer")?.focus(); }}
              className="rounded-xl border border-line bg-white px-3 py-2.5 text-left hover:border-accent">
              <div className="text-sm font-semibold">{x.label}</div><div className="truncate text-xs text-faint">{x.hint}</div>
            </button>
          ))}
        </div>

        {recent.length > 0 && (
          <>
            <h2 className="mb-2 mt-10 text-xs font-bold uppercase tracking-[.1em] text-faint">Recent — quick jobs and papers</h2>
            <ul className="divide-y divide-line rounded-xl border border-line bg-white">
              {recent.map((r) => (
                <li key={r.id}>
                  <Link href={`/projects/${r.project_id}?conv=${r.id}`} className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-[#f7f5f1]">
                    <span className={`w-12 flex-none text-xs ${r.project_kind === "quick" ? "text-faint" : "text-accent"}`}>{r.project_kind === "quick" ? "Quick" : "Paper"}</span>
                    <span className="min-w-0 flex-1 truncate">{r.project_title} <span className="text-faint">· {r.title}</span></span>
                    <span className={`flex-none text-xs ${r.last_status === "failed" ? "text-[#8a1f17]" : r.last_status === "running" || r.last_status === "queued" ? "text-[#24508f]" : "text-faint"}`}>
                      {r.last_status === "running" || r.last_status === "queued" ? "working" : r.last_status === "failed" ? "needs a retry" : "done"}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </main>
  );
}
