"use client";

// New chat, Claude-style: a greeting, one Claude Code-style box ("/" for tools), and
// shortcut chips. Sending opens the chat in the chosen project.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { parseCommand, runCommand, useCommands } from "@/lib/commands";
import type { Project } from "@/lib/types";
import { Composer } from "@/components/Composer";
import { ErrorBox } from "@/components/ui";
import { AgentsGrid } from "@/components/AgentsGrid";

const CHIPS: [string, string][] = [
  ["✦ Brainstorm ideas", "/brainstorm Blockchain, LLM, VLM"],
  ["Literature review", "/literature "],
  ["Draft a paper", "/draft "],
  ["Code generation", "/code "],
  ["Analyze data", "/analyze "],
  ["Peer review", "/review "],
  ["Thesis → paper", "/thesis "],
  ["Grant proposal", "/grant-proposal "],
  ["Slides", "/paper-slides "],
  ["Patent", "/patent-pipeline "],
];
const NEW = "__new";

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Working late?" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function NewChat() {
  const router = useRouter();
  const { commands, workflows } = useCommands();
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [attached, setAttached] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [hello, setHello] = useState("What should we research today?");

  useEffect(() => {
    setHello(greeting());
    const q = new URLSearchParams(window.location.search);
    const tool = q.get("tool");
    if (tool) setPrompt(`/${tool.replace(/^skill-/, "")} `);
    api<Project[]>("/projects").then((ps) => {
      setProjects(ps);
      setProjectId(ps.find((p) => p.id === q.get("project"))?.id ?? ps[0]?.id ?? NEW);
    }).catch(setError);
  }, []);

  async function ensureProject() {
    if (projectId && projectId !== NEW) return projectId;
    const title = prompt.replace(/^\/\S+\s*/, "").trim().slice(0, 60) || "My research";
    const p = await post<Project>("/projects", { title });
    setProjects((ps) => [p, ...(ps ?? [])]); setProjectId(p.id);
    return p.id;
  }

  async function upload(list: FileList) {
    setError(null);
    try {
      const pid = await ensureProject();
      for (const f of Array.from(list)) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api<{ path: string }>(`/projects/${pid}/files`, { method: "POST", body: fd });
        setAttached((a) => [...a, r.path]);
      }
    } catch (e) { setError(e); }
  }

  async function send() {
    if (!prompt.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const pid = await ensureProject();
      const parsed = parseCommand(prompt, commands);
      if (parsed) { router.push(await runCommand(pid, parsed.cmd, parsed.rest, workflows, attached, model || null)); return; }
      // Autopilot picks the pipeline: a whole paper (Paper Studio), a ready-made agent, or the Research Director.
      const r = await post<{ url: string }>(`/projects/${pid}/autopilot/start`, { goal: prompt, files: attached, model: model || null });
      router.push(r.url);
    } catch (e) { setError(e); setBusy(false); }
  }

  return (
    <main className="flex min-h-screen flex-col items-center px-4 pb-16 pt-[16vh]">
      <h1 className="mb-8 flex items-center gap-3 text-center font-serif text-3xl font-medium text-ink sm:text-[40px]">
        <span aria-hidden="true" className="text-[#d97757]">✳</span>{hello}
      </h1>
      <div className="w-full max-w-[720px]">
        <Composer value={prompt} onChange={setPrompt} onSend={send} busy={busy} commands={commands} autoFocus
          onAttach={upload} attached={attached} onDetach={(p) => setAttached((a) => a.filter((x) => x !== p))}
          model={model} onModel={setModel} placeholder="How can I help with your research? Type / for tools"
          footer={
            <div className="mt-2 flex items-center justify-end gap-2 text-xs text-faint">
              <label htmlFor="proj">Project</label>
              <select id="proj" value={projectId} onChange={(e) => setProjectId(e.target.value)}
                className="max-w-[220px] rounded-md bg-transparent px-1 py-1 text-muted hover:bg-[#ecebe6]">
                {projects?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                <option value={NEW}>+ New project</option>
              </select>
            </div>
          } />
        {error ? <div className="mt-3"><ErrorBox error={error} /></div> : null}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {CHIPS.filter(([, cmd]) => !commands.length || commands.some((c) => cmd.startsWith(`/${c.name} `))).map(([label, cmd]) => (
            <button key={label} onClick={() => { setPrompt(cmd); document.getElementById("composer")?.focus(); }}
              className="rounded-lg border border-[#dedcd5] bg-white px-3 py-1.5 text-sm text-[#2f3a45] hover:bg-[#f5f4ef]">{label}</button>
          ))}
        </div>
      </div>
      <AgentsGrid />
    </main>
  );
}
