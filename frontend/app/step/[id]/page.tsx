"use client";

// One screen for every research step: what you give, what you get, drop files or paste text, Start.
// The steps come from the server (webapi/app/steps.py), the same list as the console's /rl menu.

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Project } from "@/lib/types";
import { btn, ErrorBox } from "@/components/ui";

interface Option { name: string; label: string; choices?: string[] }
interface Step { n: number; id: string; group: string; name: string; give: string; get: string; engines: string[]; href: string; options?: Option[] }
interface Steps { steps: Step[] }

const QUICK = "__quick";
const NEW_PAPER = "__new";
const PLACEHOLDER: Record<string, string> = {
  literature: "Optional: a topic to search, e.g. verifiable LLM inference on blockchains",
  idea: "A topic (e.g. zero-knowledge proofs for AI oracles) — or paste your whole idea",
  code: "Paste your idea or method, or add it as a file",
  experiments: "What should be tested? Paste the reviewer's request if you have one",
  write: "Paste your idea and key results, or add them as files",
  review: "Optional: paste a review (e.g. from ChatGPT) or the journal's comments",
  check: "Nothing to type — add your .tex file (with its .bib and figures, a zip is easiest)",
};

export default function StepPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [all, setAll] = useState<Step[]>([]);
  const [papers, setPapers] = useState<Project[]>([]);
  const [current, setCurrent] = useState<Project | null>(null);
  const [where, setWhere] = useState(QUICK);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [options, setOptions] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Steps>("/steps").then((s) => setAll(s.steps)).catch(setError);
    const q = new URLSearchParams(window.location.search).get("project");
    api<Project[]>("/projects?kind=paper").then(setPapers).catch(() => {});
    // Coming from a finished job ("Next: …"): keep working in the same paper or quick job, with its files.
    if (q) api<Project>(`/projects/${q}`).then((p) => { setCurrent(p); setWhere(p.id); }).catch(() => {});
  }, []);
  const step = all.find((s) => s.id === id);
  const next = all.find((s) => step && s.n === step.n + 1);

  async function start() {
    if (!text.trim() && !files.length) { setError("Add a file or type something first."); return; }
    setBusy(true); setError(null);
    try {
      let pid = where;
      if (where === QUICK || where === NEW_PAPER) {
        const title = (text.trim().split("\n")[0] || files[0]?.name || step?.name || "Job").slice(0, 80);
        pid = (await post<Project>("/projects", { title: `${step?.name}: ${title}`.slice(0, 120), kind: where === QUICK ? "quick" : "paper" })).id;
      }
      const paths: string[] = [];
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api<{ path: string; files?: string[] }>(`/projects/${pid}/files?folder=uploads&unzip=true`, { method: "POST", body: fd });
        paths.push(...(r.files ?? [r.path]));
      }
      const r = await post<{ url: string }>(`/projects/${pid}/steps/${id}/start`, { text, files: paths, options });
      router.push(r.url);
    } catch (e) { setError(e); setBusy(false); }
  }

  const add = (list: FileList | null) => list && setFiles((fs) => [...fs, ...Array.from(list).filter((f) => !fs.some((x) => x.name === f.name))]);

  return (
    <main className="mx-auto max-w-[820px] px-4 py-7 sm:px-8">
      <nav aria-label="Steps" className="mb-6 flex flex-wrap gap-1.5">
        {all.map((s) => (
          <Link key={s.id} href={`/step/${s.id}${where !== QUICK && where !== NEW_PAPER ? `?project=${where}` : ""}`}
            className={`rounded-full border px-3 py-1 text-xs ${s.id === id ? "border-accent bg-accent text-white" : "border-line bg-white text-muted hover:border-accent"}`}>
            {s.n} {s.name}
          </Link>
        ))}
        <Link href="/paper" className="rounded-full border border-line bg-white px-3 py-1 text-xs text-muted hover:border-accent">8 All steps</Link>
      </nav>

      {step && (
        <>
          <h1 className="font-serif text-[30px] font-medium"><span className="text-accent">{step.n}.</span> {step.name}</h1>
          <p className="mt-2 text-[15px]"><span className="text-muted">You give:</span> {step.give}</p>
          <p className="text-[15px]"><span className="text-muted">You get:</span> {step.get}</p>

          <section className="mt-6 rounded-2xl border border-line bg-white p-5">
            <label className="flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed border-[#dcd6cc] px-4 py-6 text-center hover:border-accent"
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files); }}>
              <input type="file" multiple className="sr-only" onChange={(e) => add(e.target.files)} />
              <span className="font-medium">Drop files here, or click to choose</span>
              <span className="text-xs text-faint">PDF, Word, .tex, .bib, Markdown, CSV — a .zip is unpacked for you</span>
            </label>
            {files.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-2">
                {files.map((f) => (
                  <li key={f.name} className="flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs">
                    {f.name}<button aria-label={`Remove ${f.name}`} className="text-faint hover:text-ink" onClick={() => setFiles((fs) => fs.filter((x) => x !== f))}>×</button>
                  </li>
                ))}
              </ul>
            )}
            <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} aria-label="Text"
              placeholder={PLACEHOLDER[step.id]} className="mt-4 w-full rounded-lg border border-line px-3 py-2 text-sm" />

            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
              {step.options?.map((o) => (
                <label key={o.name} className="flex items-center gap-2">{o.label}
                  {o.choices
                    ? <select value={options[o.name] ?? o.choices[0]} onChange={(e) => setOptions({ ...options, [o.name]: e.target.value })}
                        className="rounded-md border border-line bg-white px-2 py-1">{o.choices.map((c) => <option key={c}>{c}</option>)}</select>
                    : <input value={options[o.name] ?? ""} onChange={(e) => setOptions({ ...options, [o.name]: e.target.value })}
                        className="rounded-md border border-line px-2 py-1" />}
                </label>
              ))}
              <label className="flex items-center gap-2">Keep it in
                <select value={where} onChange={(e) => setWhere(e.target.value)} className="max-w-[260px] rounded-md border border-line bg-white px-2 py-1">
                  {current && current.kind === "quick" && <option value={current.id}>This job: {current.title}</option>}
                  <option value={QUICK}>Just this once (quick job)</option>
                  {papers.length > 0 && <optgroup label="Add to paper">{papers.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</optgroup>}
                  <option value={NEW_PAPER}>+ New paper</option>
                </select>
              </label>
            </div>
            {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}
            <div className="mt-4 flex items-center gap-3">
              <button className={btn} disabled={busy} onClick={start}>{busy ? "Starting…" : "Start"}</button>
              <span className="text-xs text-faint">Nothing that runs code starts without your click.</span>
            </div>
          </section>

          <p className="mt-4 text-xs text-faint">Uses your engines: {step.engines.join(" · ")}</p>
          {next && <p className="mt-1 text-sm text-muted">After this: <Link className="text-accent underline" href={`/step/${next.id}`}>{next.n}. {next.name}</Link></p>}
        </>
      )}
      {!step && all.length > 0 && <p>Unknown step. <Link className="text-accent underline" href="/">Back home</Link></p>}
    </main>
  );
}
