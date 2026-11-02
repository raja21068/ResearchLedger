"use client";

// One ready-made agent: upload the files it asks for, press Start. The engine and the
// user's stored prompts are chosen by the backend; nothing to prompt.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { guessRole, type Recipe } from "@/lib/recipes";
import type { Project, WorkspaceFile } from "@/lib/types";
import { BridgeBanner } from "@/components/BridgeStatus";
import { btn, btn2, ErrorBox } from "@/components/ui";

const NEW = "__new";

export default function RecipePage({ params }: { params: Promise<{ recipe: string }> }) {
  const { recipe: rid } = use(params);
  const router = useRouter();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [files, setFiles] = useState<Record<string, string[]>>({});
  const [library, setLibrary] = useState<WorkspaceFile[]>([]);
  const [options, setOptions] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    api<Recipe>(`/recipes/${rid}`).then((r) => {
      setRecipe(r);
      setOptions(Object.fromEntries(r.options.map((o) => [o.name, q.get(o.name) ?? o.default ?? ""])));
      // Files handed over from the home page drop zone: ?f=uploads/a.pdf&f=uploads/b.pdf
      const handed = q.getAll("f");
      const pre: Record<string, string[]> = {};
      for (const f of handed) {
        const role = guessRole(r, f);
        if (role) pre[role] = [...(pre[role] ?? []), f];
      }
      setFiles(pre);
    }).catch(setError);
    api<Project[]>("/projects").then((ps) => {
      setProjects(ps);
      setProjectId(ps.find((p) => p.id === q.get("project"))?.id ?? (q.get("project") ? "" : NEW));
    }).catch(setError);
  }, [rid]);

  const loadLibrary = useCallback((pid: string) => {
    if (!pid || pid === NEW) { setLibrary([]); return; }
    api<WorkspaceFile[]>(`/projects/${pid}/files`).then(setLibrary).catch(() => setLibrary([]));
  }, []);
  useEffect(() => { loadLibrary(projectId); }, [projectId, loadLibrary]);

  async function ensureProject(): Promise<string> {
    if (projectId && projectId !== NEW) return projectId;
    const first = Object.values(files).flat()[0]?.split("/").pop();
    const p = await post<Project>("/projects", { title: `${recipe?.name ?? "Task"}${first ? `: ${first}` : ""}`.slice(0, 120) });
    setProjects((ps) => [p, ...ps]); setProjectId(p.id);
    return p.id;
  }

  async function upload(role: string, list: FileList | null, multiple?: boolean) {
    if (!list?.length) return;
    setUploading(role); setError(null);
    try {
      const pid = await ensureProject();
      const added: string[] = [];
      for (const f of Array.from(list)) {
        const fd = new FormData(); fd.append("file", f);
        added.push((await api<{ path: string }>(`/projects/${pid}/files?folder=uploads`, { method: "POST", body: fd })).path);
      }
      setFiles((s) => ({ ...s, [role]: multiple ? [...(s[role] ?? []), ...added] : added.slice(0, 1) }));
      loadLibrary(pid);
    } catch (e) { setError(e); } finally { setUploading(null); }
  }

  async function start() {
    if (!recipe) return;
    setBusy(true); setError(null);
    try {
      const pid = await ensureProject();
      const r = await post<{ project_id: string; conversation_id: string }>(`/projects/${pid}/recipes/${rid}/run`, { files, options });
      router.push(`/projects/${r.project_id}?conv=${r.conversation_id}`);
    } catch (e) { setError(e); setBusy(false); }
  }

  if (!recipe) return <main className="p-8"><ErrorBox error={error} />{!error && <p className="rl-pulse text-faint">Loading…</p>}</main>;
  const ready = recipe.inputs.every((i) => !i.required || (files[i.role]?.length ?? 0) > 0)
    && recipe.options.every((o) => !o.required || options[o.name]?.trim());

  return (
    <main className="mx-auto max-w-[760px] px-4 py-8 sm:px-8">
      <Link href="/" className="text-sm text-faint hover:text-ink">← All agents</Link>
      <div className="mt-3 rounded-2xl border border-line bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-semibold">{recipe.name}</h1>
        <p className="mt-1.5 text-[15px] text-muted">{recipe.pitch}</p>

        <div className="mt-6 grid gap-5">
          {recipe.inputs.map((inp) => (
            <div key={inp.role}>
              <div className="mb-1.5 text-sm font-semibold">{inp.label}{inp.required ? " *" : ""}</div>
              <label className={`flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-5 text-center text-sm ${(files[inp.role]?.length ?? 0) > 0 ? "border-accent bg-accent-soft" : "border-line hover:border-[#c9a18f]"}`}>
                <input type="file" className="sr-only" multiple={inp.multiple} accept={inp.accept.join(",")}
                  onChange={(e) => { upload(inp.role, e.target.files, inp.multiple); e.target.value = ""; }} />
                {uploading === inp.role ? <span className="rl-pulse">Uploading…</span>
                  : (files[inp.role]?.length ?? 0) > 0
                    ? files[inp.role].map((f) => <span key={f} className="font-mono text-xs">✓ {f.split("/").pop()}</span>)
                    : <><span className="font-medium">Click to upload</span><span className="text-xs text-faint">{inp.accept.join("  ")}</span></>}
              </label>
              {library.filter((f) => inp.accept.some((x) => f.path.toLowerCase().endsWith(x))).length > 0 && (
                <select aria-label={`${inp.label} from library`} value="" className="mt-2 min-h-9 w-full rounded-lg border border-line bg-white px-2 text-sm text-muted"
                  onChange={(e) => e.target.value && setFiles((s) => ({ ...s, [inp.role]: inp.multiple ? [...(s[inp.role] ?? []), e.target.value] : [e.target.value] }))}>
                  <option value="">…or choose from this project&apos;s files</option>
                  {library.filter((f) => inp.accept.some((x) => f.path.toLowerCase().endsWith(x))).map((f) => <option key={f.path} value={f.path}>{f.path}</option>)}
                </select>
              )}
            </div>
          ))}

          {recipe.options.map((o) => (
            <label key={o.name} className="grid gap-1.5 text-sm font-semibold">{o.label}{o.required ? " *" : ""}
              {o.kind === "select"
                ? <select value={options[o.name] ?? ""} onChange={(e) => setOptions({ ...options, [o.name]: e.target.value })}
                    className="min-h-11 rounded-lg border border-line bg-white px-3 font-normal">
                    {o.options?.map((x) => <option key={x}>{x}</option>)}</select>
                : <input value={options[o.name] ?? ""} onChange={(e) => setOptions({ ...options, [o.name]: e.target.value })}
                    className="min-h-11 rounded-lg border border-line px-3 font-normal" />}
            </label>
          ))}

          <label className="grid gap-1.5 text-sm font-semibold">Save in project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="min-h-11 rounded-lg border border-line bg-white px-3 font-normal">
              <option value={NEW}>New project (named automatically)</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </label>
        </div>

        {error ? <div className="mt-4"><ErrorBox error={error} /></div> : null}
        <button className={`${btn} mt-6 min-h-12 w-full text-base`} disabled={!ready || busy} onClick={start}>
          {busy ? "Starting…" : ready ? "Start" : "Upload the required files to start"}
        </button>

        <details className="mt-5 rounded-lg bg-[#f6f4f0] p-3 text-sm">
          <summary className="cursor-pointer font-medium">What the system will use automatically</summary>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <div><div className="font-semibold">Engines</div><ul className="mt-1 list-disc pl-5 text-muted">{recipe.engines.map((e) => <li key={e.id}>{e.label}</li>)}</ul></div>
            <div><div className="font-semibold">Your stored prompts</div><ul className="mt-1 list-disc pl-5 text-muted">
              {recipe.prompts.map((p) => <li key={p.name}>{p.name}{p.available ? "" : " (not found)"}</li>)}</ul></div>
          </div>
          <div className="mt-3 font-semibold">You will get</div>
          <p className="font-mono text-xs text-muted">{recipe.outputs.join(" · ")}</p>
        </details>
      </div>
      <div className="mt-4"><BridgeBanner waiting={false} /></div>
    </main>
  );
}
