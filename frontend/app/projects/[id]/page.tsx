"use client";

// Project studio: a Claude-style chat with the Claude Code research agent on the
// left and a tabbed document panel (PDF / Word / LaTeX / Markdown) on the right.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { parseCommand, runCommand, useCommands } from "@/lib/commands";
import { Composer } from "@/components/Composer";
import { IdeaList } from "@/components/IdeaCards";
import { BridgeBanner } from "@/components/BridgeStatus";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, eventsUrl, post } from "@/lib/api";
import type { Conversation, Project, Run, RunEvent, WorkspaceFile } from "@/lib/types";
import { FileViewer } from "@/components/FileViewer";
import { NextStep } from "@/components/NextStep";
import { Markdown } from "@/components/Markdown";
import { btn, btn2, ErrorBox, RunBadge } from "@/components/ui";

const MODELS = [
  { id: "", label: "Default model" },
  { id: "opus", label: "Opus" },
  { id: "sonnet", label: "Sonnet" },
  { id: "haiku", label: "Haiku" },
];

const STARTERS = [
  "/brainstorm Blockchain, LLM, VLM",
  "/literature verifiable LLM inference on blockchains",
  "Draft a LaTeX manuscript (manuscript/main.tex) for a study on [YOUR TOPIC] with Introduction, Related Work, Method, Experiments and Conclusion. Use placeholders for every result and citation, then compile it to PDF.",
  "Write the manuscript as Markdown in manuscript/main.md so I can export it to Word. Topic: [YOUR TOPIC].",
  "Read the files in uploads/ and write a structured peer-review report (review/report.md) with major and minor concerns, each tied to a section or page.",
];

const DOC_EXT = /\.(pdf|docx)$/i;

interface PlanStep { workflow: string; title?: string; why?: string; name?: string; known?: boolean; values?: Record<string, unknown> }
interface PlanInfo {
  path: string;
  plan: { goal?: string; summary?: string; steps: PlanStep[]; error?: string } | null;
  plan_run: { id: string; status: string } | null;
}

export default function ProjectStudio({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [project, setProject] = useState<Project | null>(null);
  const [convId, setConvId] = useState<string | null>(null);
  const [conv, setConv] = useState<Conversation | null>(null);
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [tabs, setTabs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string>("__activity");
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [mode, setMode] = useState<"director" | "direct">("director");
  const [panelOpen, setPanelOpen] = useState(false);
  const wantedConv = useSearchParams().get("conv");
  const router = useRouter();
  const { commands, workflows } = useCommands();
  const [attached, setAttached] = useState<string[]>([]);
  const [fileVersion, setFileVersion] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const openFile = useCallback((path: string) => {
    setTabs((t) => (t.includes(path) ? t : [...t, path]));
    setActiveTab(path);
    setPanelOpen(true);
  }, []);

  const loadFiles = useCallback(async () => {
    try { setFiles(await api<WorkspaceFile[]>(`/projects/${id}/files`)); } catch (e) { setError(e); }
  }, [id]);

  const loadProject = useCallback(async () => {
    try {
      const p = await api<Project>(`/projects/${id}`);
      setProject(p);
      const wanted = new URLSearchParams(window.location.search).get("conv");
      setConvId((cur) => cur ?? p.conversations?.find((c) => c.id === wanted)?.id ?? p.conversations?.[0]?.id ?? null);
    } catch (e) { setError(e); }
  }, [id]);

  const loadConv = useCallback(async (cid: string) => {
    try { setConv(await api<Conversation>(`/conversations/${cid}`)); } catch (e) { setError(e); }
  }, []);

  useEffect(() => { loadProject(); loadFiles(); }, [loadProject, loadFiles]);
  // Clicking another chat in the sidebar's Recents changes only ?conv=.
  useEffect(() => { if (wantedConv) setConvId(wantedConv); }, [wantedConv]);
  useEffect(() => { if (convId) loadConv(convId); else setConv(null); }, [convId, loadConv]);

  const activeRuns = (conv?.runs ?? []).filter((r) => r.status === "queued" || r.status === "running");
  // While a Director plan runs, its steps run alongside it; Stop targets the plan.
  const activeRun = activeRuns.find((r) => r.kind === "plan") ?? activeRuns[0] ?? null;
  const activeKey = activeRuns.map((r) => r.id).join(",");

  const loadPlan = useCallback(async (cid: string) => {
    try { setPlan(await api<PlanInfo>(`/conversations/${cid}/plan`)); } catch { setPlan(null); }
  }, []);
  useEffect(() => { if (convId) loadPlan(convId); else setPlan(null); }, [convId, loadPlan]);

  // Live events for every active run over SSE; each resumes from the last event we have.
  useEffect(() => {
    if (!activeRuns.length) return;
    const sources = activeRuns.map((run) => {
      const es = new EventSource(eventsUrl(run.id, run.events?.at(-1)?.id ?? 0));
      const append = (ev: MessageEvent) => {
        const e: RunEvent = JSON.parse(ev.data);
        setConv((c) => c && {
          ...c,
          runs: c.runs?.map((r) => r.id === run.id && !(r.events ?? []).some((x) => x.id === e.id)
            ? { ...r, status: "running", events: [...(r.events ?? []), e] } : r),
        });
        // A plan step started a new agent run in this chat: load it so it streams too.
        if (e.kind === "plan_step" && e.payload.run_id && convId) loadConv(convId);
        if (e.kind === "artifacts") {
          const created = (e.payload.files as { path: string }[]).map((f) => f.path);
          loadFiles();
          setFileVersion((v) => v + 1);
          const doc = created.find((p) => DOC_EXT.test(p));
          if (doc) openFile(doc);
        }
      };
      for (const k of ["init", "status", "assistant_text", "tool_use", "tool_result", "result", "artifacts", "error",
        "log", "result_json", "todos", "plan", "plan_step", "done"]) {
        es.addEventListener(k, append as EventListener);
      }
      es.addEventListener("end", () => {
        es.close();
        if (convId) { loadConv(convId); loadPlan(convId); }
        loadFiles(); loadProject();
      });
      return es;
    });
    return () => sources.forEach((s) => s.close());
    // Re-subscribe only when the set of active runs changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey]);

  // Open the activity panel while agents work or a plan waits for approval.
  useEffect(() => {
    if (activeRuns.length || (plan?.plan && !plan.plan_run)) { setPanelOpen(true); setActiveTab((t) => (t === "__files" ? "__activity" : t)); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, plan?.plan?.steps?.length]);

  async function approvePlan() {
    if (!convId) return;
    setError(null);
    try { await post(`/conversations/${convId}/plan/approve`); await loadConv(convId); await loadPlan(convId); }
    catch (e) { setError(e); }
  }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); },
    [conv?.runs?.length, conv?.runs?.at(-1)?.events?.length]);

  async function newChat() {
    try {
      const c = await post<Conversation>(`/projects/${id}/conversations`, {});
      setConvId(c.id);
      loadProject();
    } catch (e) { setError(e); }
  }

  async function send(text = prompt) {
    if (!text.trim() || activeRun) return;
    setSending(true); setError(null);
    try {
      // "/brainstorm …", "/literature …", "/grant-proposal …": run that tool in a new chat.
      const parsed = parseCommand(text, commands);
      if (parsed) {
        const next = await runCommand(id, parsed.cmd, parsed.rest, workflows, attached, model || null);
        setPrompt(""); setAttached([]);
        router.push(next);
        return;
      }
      let cid = convId;
      if (!cid) {
        cid = (await post<Conversation>(`/projects/${id}/conversations`, {})).id;
        setConvId(cid);
      }
      const withFiles = attached.length
        ? `${text}\n\nAttached files in the workspace:\n${attached.map((a) => `- \`${a}\``).join("\n")}` : text;
      await post<Run>(`/conversations/${cid}/${mode === "director" ? "director" : "runs"}`, { prompt: withFiles, model: model || null });
      setPrompt(""); setAttached([]);
      await loadConv(cid);
      loadProject();
    } catch (e) { setError(e); } finally { setSending(false); }
  }

  async function stop() {
    if (!activeRun) return;
    // Stopping a plan also stops the agent step it is waiting on (server side).
    try { await post(`/runs/${activeRun.id}/cancel`); if (convId) loadConv(convId); } catch (e) { setError(e); }
  }

  async function upload(list: FileList | null) {
    if (!list?.length) return;
    setUploading(true); setError(null);
    try {
      const added: string[] = [];
      for (const f of Array.from(list)) {
        const fd = new FormData(); fd.append("file", f);
        const res = await api<{ path: string }>(`/projects/${id}/files`, { method: "POST", body: fd });
        added.push(res.path);
      }
      await loadFiles();
      setAttached((a) => [...a, ...added]);
    } catch (e) { setError(e); } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function closeTab(path: string) {
    setTabs((t) => {
      const next = t.filter((x) => x !== path);
      if (activeTab === path) setActiveTab(next.at(-1) ?? "__files");
      return next;
    });
  }

  const docs = useMemo(() => files.filter((f) => f.kind === "pdf" || f.kind === "docx"), [files]);

  return (
    <div className="flex h-[calc(100vh-0px)] min-h-0 flex-col max-lg:h-[calc(100vh-72px)]">
      {/* Top bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-white px-4 py-2.5">
        <Link href="/projects" className="text-sm text-faint hover:text-ink">{project?.kind === "quick" ? "Quick jobs" : "Papers"}</Link>
        <span className="text-faint">/</span>
        <h1 className="mr-2 truncate font-semibold">{project?.title ?? "…"}</h1>
        {project?.kind === "quick" && (
          <button className={btn2} title="Move this job to your Papers so it can grow into a full paper"
            onClick={async () => { try { setProject(await api<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ kind: "paper" }), headers: { "Content-Type": "application/json" } })); } catch (e) { setError(e); } }}>
            Keep as a paper</button>
        )}
        {project?.kind === "paper" && (
          <nav aria-label="This paper" className="flex gap-3 text-sm">
            <Link className="text-accent hover:underline" href={`/projects/${id}/home`}>Overview</Link>
            <Link className="text-accent hover:underline" href={`/projects/${id}/paper`}>Writing</Link>
            <Link className="text-accent hover:underline" href={`/loops?project=${id}`}>Loops</Link>
            <Link className="text-accent hover:underline" href={`/quality?project=${id}`}>Check</Link>
            <Link className="text-accent hover:underline" href={`/results?project=${id}`}>Results</Link>
          </nav>
        )}
        {conv && <span className="min-w-0 max-w-[40ch] truncate text-sm text-muted" title={conv.title}>· {conv.title}</span>}
        <button className={btn2} onClick={newChat}>New chat</button>
        <div className="ml-auto flex items-center gap-2">
          {docs.length > 0 && (
            <select aria-label="Open a document" className="min-h-9 max-w-[220px] rounded-lg border border-line bg-white px-2 text-sm"
              value="" onChange={(e) => e.target.value && openFile(e.target.value)}>
              <option value="">Documents ({docs.length})</option>
              {docs.map((d) => <option key={d.path} value={d.path}>{d.path}</option>)}
            </select>
          )}
          <button className={btn2} onClick={() => setPanelOpen(!panelOpen)} aria-pressed={panelOpen}>
            {panelOpen ? "Hide files" : `Files (${files.filter(isUserFile).length})`}
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* Chat */}
        <section className={`flex min-h-0 min-w-0 flex-col ${panelOpen ? "md:w-[46%] md:flex-none" : "flex-1"} max-md:h-[60vh]`}>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
            <div className="mx-auto flex max-w-[760px] flex-col gap-6">
              {!conv?.runs?.length && (
                <div className="py-6">
                  <h2 className="font-serif text-2xl font-semibold">What should the research agent do?</h2>
                  <p className="mt-2 text-sm text-muted">
                    Prompts run on your local Claude Code CLI inside this project&apos;s workspace. Generated PDFs and
                    Word files open in the panel on the right, and each can also open in its own browser tab.
                  </p>
                  <div className="mt-5 grid gap-2">
                    {STARTERS.map((s) => (
                      <button key={s} onClick={() => setPrompt(s)}
                        className="rounded-xl border border-line bg-white p-3 text-left text-sm hover:border-[#8796a5]">{s}</button>
                    ))}
                  </div>
                </div>
              )}
              {conv?.runs?.map((r) => <RunView key={r.id} run={r} onOpen={openFile} />)}
              <BridgeBanner waiting={activeRuns.some((r) => r.status === "queued")} />
              {plan?.plan && !plan.plan_run && !activeRuns.length && (
                <PlanCard plan={plan.plan} onApprove={approvePlan} onOpenFile={() => openFile(plan.path)} />
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* Composer, Claude Code style */}
          <div className="px-4 pb-3 pt-1">
            <div className="mx-auto max-w-[760px]">
              {error ? <div className="mb-2"><ErrorBox error={error} /></div> : null}
              <input ref={fileInput} type="file" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
              <Composer value={prompt} onChange={setPrompt} onSend={() => send()} onStop={stop}
                busy={sending || uploading} working={!!activeRun} commands={commands}
                onAttach={(fl) => upload(fl)} attached={attached} onDetach={(p) => setAttached((a) => a.filter((x) => x !== p))}
                model={model} onModel={setModel}
                placeholder={activeRun ? "The agent is working… you can type your next message" : undefined}
                footer={
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-faint">
                    <div role="radiogroup" aria-label="Who answers" className="flex rounded-lg bg-[#ecebe6] p-0.5">
                      {([["director", "Research Director"], ["direct", "Direct chat"]] as const).map(([m, l]) => (
                        <button key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                          className={`rounded-md px-2.5 py-1 ${mode === m ? "bg-white font-medium text-ink shadow-sm" : ""}`}>{l}</button>
                      ))}
                    </div>
                    <span>{mode === "director"
                      ? "The Director plans which agents to use; nothing runs until you approve."
                      : <>Type <span className="font-mono">/</span> for tools, e.g. <span className="font-mono">/brainstorm Blockchain, LLM, VLM</span></>}</span>
                  </div>} />
            </div>
          </div>
        </section>

        {/* Document panel */}
        {panelOpen && (
          <aside className="flex min-h-[70vh] min-w-0 flex-1 flex-col border-l border-line bg-white md:min-h-0">
            <div role="tablist" aria-label="Open files" className="flex items-end gap-1 overflow-x-auto border-b border-line bg-[#f6f8fa] px-2 pt-2">
              <button role="tab" aria-selected={activeTab === "__activity"} onClick={() => setActiveTab("__activity")}
                className={`whitespace-nowrap rounded-t-lg border px-3 py-2 text-sm ${activeTab === "__activity"
                  ? "border-line border-b-white bg-white font-semibold" : "border-transparent text-muted hover:text-ink"}`}>
                Activity{activeRuns.length ? ` · ${activeRuns.length} running` : ""}
              </button>
              <button role="tab" aria-selected={activeTab === "__files"} onClick={() => setActiveTab("__files")}
                className={`whitespace-nowrap rounded-t-lg border px-3 py-2 text-sm ${activeTab === "__files"
                  ? "border-line border-b-white bg-white font-semibold" : "border-transparent text-muted hover:text-ink"}`}>
                Files ({files.length})
              </button>
              {tabs.map((t) => (
                <div key={t} className={`flex items-center whitespace-nowrap rounded-t-lg border text-sm ${activeTab === t
                  ? "border-line border-b-white bg-white font-semibold" : "border-transparent text-muted"}`}>
                  <button role="tab" aria-selected={activeTab === t} className="py-2 pl-3 pr-1" title={t}
                    onClick={() => setActiveTab(t)}>{t.split("/").pop()}</button>
                  <button aria-label={`Close ${t}`} className="px-2 py-2 text-faint hover:text-ink" onClick={() => closeTab(t)}>×</button>
                </div>
              ))}
            </div>
            <div className="min-h-0 flex-1">
              {activeTab === "__activity"
                ? <ActivityPanel runs={conv?.runs ?? []} plan={plan} onApprove={approvePlan} onOpen={openFile} />
                : activeTab === "__files"
                ? <FileList files={files} onOpen={openFile} onRefresh={loadFiles} onUpload={() => fileInput.current?.click()} />
                : <FileViewer key={activeTab} projectId={id} path={activeTab} version={fileVersion}
                    onExported={(p) => { loadFiles(); setFileVersion((v) => v + 1); openFile(p); }} />}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

function RunView({ run, onOpen }: { run: Run; onOpen: (p: string) => void }) {
  const events = run.events ?? [];
  const results = new Map(events.filter((e) => e.kind === "tool_result").map((e) => [e.payload.id as string, e]));
  const resultEvent = events.find((e) => e.kind === "result");
  const artifacts = events.filter((e) => e.kind === "artifacts")
    .flatMap((e) => e.payload.files as { path: string; change: string }[]);
  const live = run.status === "queued" || run.status === "running";
  const status = [...events].reverse().find((e) => e.kind === "status");
  const logs = events.filter((e) => e.kind === "log");
  const resultJson = events.find((e) => e.kind === "result_json");
  const isWorkflow = run.provider === "researchctl" || run.kind.startsWith("workflow:") || run.kind.startsWith("skill:");
  if (run.kind === "plan") {
    const done = events.filter((e) => e.kind === "plan_step" && e.payload.status === "succeeded").length;
    const total = (events.find((e) => e.kind === "plan")?.payload.steps as unknown[] | undefined)?.length ?? 0;
    const err = events.find((e) => e.kind === "error");
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[#ecd3c6] bg-[#fbf3ee] px-4 py-2.5 text-sm">
        <span className={`h-2.5 w-2.5 rounded-full ${live ? "rl-pulse bg-[#3b6fd8]" : run.status === "succeeded" ? "bg-accent" : "bg-[#b91c1c]"}`} />
        <span className="font-medium">Plan approved</span>
        <span className="text-muted">· {done}/{total} steps done{live ? " · running" : run.status === "succeeded" ? " · finished" : ` · ${run.status}`}</span>
        {err && <span className="w-full text-[#7f1d1d]">{String(err.payload.text)}</span>}
      </div>
    );
  }
  const shownPrompt = run.kind === "director" ? run.prompt.replace(/\n\n\[Research Director:[\s\S]*$/, "") : run.prompt;
  const toolUses = events.filter((e) => e.kind === "tool_use");
  const todos = [...events].reverse().find((e) => e.kind === "todos")?.payload.items as
    { content: string; status: string }[] | undefined;

  return (
    <div className="flex flex-col gap-3">
      {isWorkflow || shownPrompt.length > 600 ? (
        <details className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-[#e8edf1] px-4 py-2.5 text-[15px]">
          <summary className="cursor-pointer font-medium">{shownPrompt.split("\n")[0].slice(0, 120)}</summary>
          <div className="mt-2 whitespace-pre-wrap text-sm text-muted">{shownPrompt}</div>
        </details>
      ) : (
        <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-[#e8edf1] px-4 py-2.5 text-[15px]">
          {shownPrompt}
        </div>
      )}
      <div className="flex flex-col gap-2.5">
        {logs.length > 0 && (
          <details open={live} className="rounded-lg border border-line bg-[#0f1720] text-[#e6edf3]">
            <summary className="cursor-pointer px-3 py-2 text-sm">Engine log ({logs.length} lines)</summary>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap px-3 pb-3 font-mono text-xs leading-relaxed">
              {logs.slice(-300).map((l) => l.payload.text).join("\n")}
            </pre>
          </details>
        )}
        {resultJson && (
          <details className="rounded-lg border border-line bg-white text-sm">
            <summary className="cursor-pointer px-3 py-2 font-semibold">Engine result (technical details)</summary>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap border-t border-line px-3 py-2 font-mono text-xs">
              {JSON.stringify(resultJson.payload.data, null, 2)}
            </pre>
          </details>
        )}
        {todos && todos.length > 0 && (
          // The agent's checklist (TodoWrite), like Claude Code's plan.
          <ul className="rounded-xl border border-line bg-white px-4 py-3 text-sm">
            {todos.map((t, i) => (
              <li key={i} className="flex items-start gap-2.5 py-0.5">
                <span aria-hidden="true" className={`mt-[3px] flex h-4 w-4 flex-none items-center justify-center rounded-full border text-[10px] ${t.status === "completed"
                  ? "border-accent bg-accent text-white" : t.status === "in_progress" ? "rl-pulse border-[#3b6fd8]" : "border-dashed border-[#9aa6b2]"}`}>
                  {t.status === "completed" ? "✓" : ""}</span>
                <span className={t.status === "completed" ? "text-faint line-through" : t.status === "in_progress" ? "font-medium" : "text-muted"}>{t.content}</span>
              </li>
            ))}
          </ul>
        )}
        {toolUses.length > 0 && (
          // All tool calls fold into one line, like Claude's "Worked on N steps".
          <details className="rounded-lg text-sm text-muted">
            <summary className="flex cursor-pointer list-none items-center gap-2 py-1 hover:text-ink">
              <span className={`h-2 w-2 flex-none rounded-full ${live ? "rl-pulse bg-[#3b6fd8]" : "bg-accent"}`} />
              {live ? `Working… ${stepLabel(toolUses.at(-1)!)}` : `Worked through ${toolUses.length} step${toolUses.length > 1 ? "s" : ""}`}
              <span aria-hidden="true" className="text-faint">▸</span>
            </summary>
            <ol className="ml-1 mt-1 space-y-1 border-l border-line pl-4">
              {toolUses.map((e) => {
                const res = results.get(e.payload.id as string);
                return (
                  <li key={e.id} className="flex items-center gap-2">
                    <span className={res?.payload.is_error ? "text-[#b91c1c]" : "text-faint"}>{res ? (res.payload.is_error ? "✕" : "✓") : "…"}</span>
                    <span className="min-w-0 truncate">{stepLabel(e)}</span>
                  </li>
                );
              })}
            </ol>
          </details>
        )}
        {events.map((e) => {
          if (e.kind === "assistant_text") return <Markdown key={e.id} text={e.payload.text ?? ""} />;
          if (e.kind === "error") return <ErrorBox key={e.id} error={String(e.payload.text)} />;
          return null;
        })}
        {artifacts.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {artifacts.map((a) => (
              <button key={a.path} onClick={() => onOpen(a.path)}
                className="flex items-center gap-2 rounded-xl border border-line bg-white px-3 py-2 text-left text-sm hover:border-accent">
                <FileIcon path={a.path} />
                <span><span className="block font-medium">{a.path.split("/").pop()}</span>
                  <span className="block text-xs text-faint">{a.change} · {a.path}</span></span>
              </button>
            ))}
          </div>
        )}
        {!live && artifacts.some((a) => a.path === "ideas/ideas.json") && <IdeaList projectId={run.project_id} compact />}
        {run.status === "succeeded" && run.kind.startsWith("recipe:") && <NextStep projectId={run.project_id} kind={run.kind} files={[]} />}
        <div className="flex flex-wrap items-center gap-2 text-xs text-faint">
          <RunBadge status={run.status} />
          {live && <span className="rl-pulse">{String(status?.payload.text ?? "Working…")}</span>}
          {run.duration_ms != null && <span>{(run.duration_ms / 1000).toFixed(1)} s</span>}
        </div>
      </div>
    </div>
  );
}

const AGENT_NAME: Record<string, string> = {
  director: "Research Director", plan: "Plan", claude_code: "Research agent",
};
function agentName(r: Run) {
  if (r.kind.startsWith("workflow:")) return r.prompt.split("\n")[0].split(":")[0];
  if (r.kind.startsWith("skill:")) return r.prompt.match(/Use the skill \*\*(.+?)\*\*/)?.[1] ?? "Skill";
  return AGENT_NAME[r.kind] ?? "Agent";
}

function PlanCard({ plan, onApprove, onOpenFile }: {
  plan: NonNullable<PlanInfo["plan"]>; onApprove: () => void; onOpenFile: () => void;
}) {
  const bad = plan.steps.some((s) => !s.known);
  return (
    <section className="rounded-2xl border border-[#ecd3c6] bg-[#fbf3ee] p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-accent-dark">Proposed plan · waiting for your approval</div>
      {plan.goal && <div className="mt-1 font-semibold">{plan.goal}</div>}
      {plan.summary && <p className="mt-1 text-sm text-muted">{plan.summary}</p>}
      <ol className="mt-3 space-y-2">
        {plan.steps.map((s, i) => (
          <li key={i} className="flex gap-3 text-sm">
            <span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-white font-mono text-xs ring-1 ring-[#ecd3c6]">{i + 1}</span>
            <span><span className="font-medium">{s.title || s.name}</span>
              <span className="text-faint"> · {s.name}</span>
              {!s.known && <span className="text-[#b91c1c]"> · not allowed</span>}
              {s.why && <span className="block text-muted">{s.why}</span>}</span>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className={btn} onClick={onApprove} disabled={bad}>Approve and run</button>
        <button className={btn2} onClick={onOpenFile}>View plan file</button>
        <span className="self-center text-xs text-faint">Or reply in the chat to change the plan.</span>
      </div>
    </section>
  );
}

function ActivityPanel({ runs, plan, onApprove, onOpen }: {
  runs: Run[]; plan: PlanInfo | null; onApprove: () => void; onOpen: (p: string) => void;
}) {
  const planRun = [...runs].reverse().find((r) => r.kind === "plan");
  const stepStatus = new Map<number, { status: string; run_id?: string }>();
  for (const e of planRun?.events ?? []) {
    if (e.kind === "plan_step") stepStatus.set(Number(e.payload.index), { status: String(e.payload.status), run_id: e.payload.run_id as string | undefined });
  }
  const live = runs.filter((r) => r.status === "queued" || r.status === "running" ).filter((r) => r.kind !== "plan");
  const latest = [...runs].reverse().find((r) => r.kind !== "plan");
  const todos = [...(latest?.events ?? [])].reverse().find((e) => e.kind === "todos")?.payload.items as { content: string; status: string }[] | undefined;
  const files = runs.flatMap((r) => (r.events ?? []).filter((e) => e.kind === "artifacts")
    .flatMap((e) => e.payload.files as { path: string; change: string }[]));
  const uniqueFiles = [...new Map(files.map((f) => [f.path, f])).values()].reverse();
  const dot = (s: string) => s === "succeeded" ? "bg-accent" : s === "failed" || s === "cancelled" ? "bg-[#b91c1c]" : s === "running" ? "rl-pulse bg-[#3b6fd8]" : "bg-[#c9d2da]";

  return (
    <div className="h-full space-y-5 overflow-y-auto p-4 text-sm">
      {plan?.plan && (
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Research Director · plan</h3>
          {plan.plan.goal && <p className="mb-2 font-medium">{plan.plan.goal}</p>}
          <ol className="space-y-1.5">
            {plan.plan.steps.map((s, i) => {
              const st = stepStatus.get(i)?.status ?? (planRun ? "pending" : "proposed");
              return (
                <li key={i} className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 flex-none rounded-full ${dot(st)}`} />
                  <span className="min-w-0 flex-1 truncate">{i + 1}. {s.title || s.name}</span>
                  <span className="text-xs text-faint">{st}</span>
                </li>
              );
            })}
          </ol>
          {!plan.plan_run && <button className={`${btn} mt-3 w-full`} onClick={onApprove} disabled={plan.plan.steps.some((s) => !s.known)}>Approve and run</button>}
        </section>
      )}
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Agents</h3>
        {live.length === 0 && <p className="text-faint">No agent is working right now.</p>}
        {live.map((r) => {
          const steps = (r.events ?? []).filter((e) => e.kind === "tool_use");
          return (
            <div key={r.id} className="mb-2 rounded-lg border border-line p-2.5">
              <div className="flex items-center gap-2 font-medium"><span className={`h-2 w-2 rounded-full ${dot("running")}`} />{agentName(r)}</div>
              <div className="mt-1 truncate text-xs text-muted">{steps.length ? stepLabel(steps.at(-1)!) : "Starting…"}</div>
            </div>
          );
        })}
      </section>
      {todos && todos.length > 0 && (
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Tasks · {agentName(latest!)}</h3>
          <ul className="space-y-1">
            {todos.map((t, i) => (
              <li key={i} className={t.status === "completed" ? "text-faint line-through" : t.status === "in_progress" ? "font-medium" : "text-muted"}>
                {t.status === "completed" ? "✓" : t.status === "in_progress" ? "▸" : "○"} {t.content}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Files from this chat</h3>
        {uniqueFiles.length === 0 && <p className="text-faint">Nothing yet.</p>}
        {uniqueFiles.map((f) => (
          <button key={f.path} onClick={() => onOpen(f.path)} className="flex w-full items-center gap-2 rounded-lg px-1 py-1.5 text-left hover:bg-[#f6f8fa]">
            <FileIcon path={f.path} /><span className="min-w-0 truncate">{f.path}</span>
          </button>
        ))}
      </section>
    </div>
  );
}

function stepLabel(e: RunEvent) {
  const name = String(e.payload.name);
  const target = String(e.payload.target ?? "");
  const short = target.split(/[\\/]/).slice(-2).join("/");
  if (name === "WebSearch") return `Searched the web: ${target}`;
  if (name === "WebFetch") return `Read a web page: ${target}`;
  if (name === "Write") return `Wrote ${short}`;
  if (name === "Edit" || name === "MultiEdit") return `Edited ${short}`;
  if (name === "Read") return `Read ${short}`;
  if (name === "Bash") return `Ran ${target}`;
  if (name === "Glob" || name === "Grep") return `Looked through files (${target})`;
  return `${name} ${short}`;
}

// Files the user cares about; engine bookkeeping stays behind "Show all files".
const INTERNAL = /^(_inputs\/|control\/|\.?researchledger\/|ledger\/|state\.json$|memory\/)/;
function isUserFile(f: { path: string }) { return !INTERNAL.test(f.path); }

function FileIcon({ path }: { path: string }) {
  const ext = path.split(".").pop()?.toLowerCase();
  const [label, color] = ext === "pdf" ? ["PDF", "#b91c1c"] : ext === "docx" ? ["DOC", "#1d4ed8"]
    : ext === "tex" ? ["TEX", "#0b5f58"] : ext === "md" ? ["MD", "#3a4552"] : [ext?.slice(0, 3).toUpperCase() ?? "", "#5a6775"];
  return <span aria-hidden="true" className="flex h-8 w-9 flex-none items-center justify-center rounded-md text-[10px] font-bold text-white"
    style={{ background: color }}>{label}</span>;
}

function FileList({ files, onOpen, onRefresh, onUpload }: {
  files: WorkspaceFile[]; onOpen: (p: string) => void; onRefresh: () => void; onUpload: () => void;
}) {
  const [q, setQ] = useState("");
  const [showAll, setShowAll] = useState(false);
  const hidden = files.filter((f) => !isUserFile(f)).length;
  const shown = files.filter((f) => (showAll || isUserFile(f)) && f.path.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap gap-2 border-b border-line p-3">
        <label htmlFor="fq" className="sr-only">Filter files</label>
        <input id="fq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter files"
          className="min-h-10 min-w-0 flex-1 rounded-lg border border-line px-3 text-sm" />
        <button className={btn2} onClick={onUpload}>Upload</button>
        <button className={btn2} onClick={onRefresh}>Refresh</button>
        {hidden > 0 && (
          <label className="flex w-full items-center gap-2 text-xs text-faint">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            Show {hidden} engine files (inputs, state, memory)
          </label>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {shown.length === 0 && (
          <p className="p-6 text-sm text-muted">
            {files.length ? "No files match." : "The workspace is empty. Ask the agent to write a manuscript, or upload files."}
          </p>
        )}
        {shown.map((f) => (
          <button key={f.path} onClick={() => onOpen(f.path)}
            className="flex w-full items-center gap-3 border-b border-[#e6eaee] px-3 py-2.5 text-left hover:bg-[#f6f8fa]">
            <FileIcon path={f.path} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{f.path}</span>
              <span className="block text-xs text-faint">
                {(f.size / 1024).toFixed(1)} KB · {new Date(f.modified * 1000).toLocaleString()}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
