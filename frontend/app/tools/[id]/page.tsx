"use client";

// One tool = one form, CitedEvidence-style: choose options, upload a file or pick it
// from the library, press Generate. The backend runs the declared engine (Claude Code
// or the repository's researchctl), and you land in the project to watch it work.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import { SECTION_LABEL, type Project, type Workflow, type WorkflowInput, type WorkspaceFile } from "@/lib/types";
import { btn, btn2, CapabilityBadge, ErrorBox } from "@/components/ui";

const NEW = "__new";

export default function ToolPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [wf, setWf] = useState<Workflow | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Workflow>(`/workflows/${id}`).then((w) => {
      setWf(w);
      // Fields can be prefilled from the URL (e.g. ?topic=… from a Brainstorm idea card).
      const q = new URLSearchParams(window.location.search);
      setValues(Object.fromEntries(w.inputs.map((i) => [i.name,
        i.kind === "checkbox" ? false : q.get(i.name) ?? i.default ?? ""])));
    }).catch(setError);
    api<Project[]>("/projects").then((ps) => {
      setProjects(ps);
      const wanted = new URLSearchParams(window.location.search).get("project");
      setProjectId(ps.find((p) => p.id === wanted)?.id ?? ps[0]?.id ?? NEW);
    }).catch(setError);
  }, [id]);

  const loadFiles = useCallback(async (pid: string) => {
    if (!pid || pid === NEW) { setFiles([]); return; }
    try { setFiles(await api<WorkspaceFile[]>(`/projects/${pid}/files`)); } catch (e) { setError(e); }
  }, []);
  useEffect(() => { loadFiles(projectId); }, [projectId, loadFiles]);

  async function ensureProject(): Promise<string> {
    if (projectId && projectId !== NEW) return projectId;
    const title = newTitle.trim() || (wf ? `${wf.name} project` : "My research");
    const p = await post<Project>("/projects", { title });
    setProjects((ps) => [p, ...(ps ?? [])]);
    setProjectId(p.id);
    return p.id;
  }

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (!wf) return;
    setBusy(true); setError(null);
    try {
      const pid = await ensureProject();
      const res = await post<{ project_id: string; conversation_id: string }>(
        `/projects/${pid}/workflows/${wf.id}`, { values });
      router.push(`/projects/${res.project_id}?conv=${res.conversation_id}`);
    } catch (err) { setError(err); setBusy(false); }
  }

  if (!wf) return <main className="p-8"><ErrorBox error={error} />{!error && <p className="rl-pulse text-faint">Loading…</p>}</main>;

  return (
    <main className="mx-auto max-w-[760px] px-4 py-8 sm:px-8">
      <div className="mb-3 text-sm text-faint">{SECTION_LABEL[wf.section]}</div>
      <form onSubmit={generate} className="rounded-2xl border border-line bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold">{wf.name}</h1>
          <CapabilityBadge status={wf.status} />
        </div>
        <p className="mt-2 text-[15px] text-muted">{wf.description}</p>
        <p className="mt-2 text-xs text-faint">Runs on: <span className="font-semibold text-muted">{wf.engine_label}</span>
          {wf.requires && <> · Needs: {wf.requires}</>}</p>

        <div className="mt-6 grid gap-5">
          <Field label="Project">
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}
              className="min-h-11 w-full rounded-lg border border-line bg-white px-3">
              {projects?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              <option value={NEW}>+ New project…</option>
            </select>
            {projectId === NEW && (
              <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="New project title"
                aria-label="New project title" className="mt-2 min-h-11 w-full rounded-lg border border-line px-3" />
            )}
          </Field>

          {wf.inputs.map((inp) => (
            <InputField key={inp.name} inp={inp} value={values[inp.name]} files={files}
              onChange={(v) => setValues((s) => ({ ...s, [inp.name]: v }))}
              onUpload={async (f) => {
                const pid = await ensureProject();
                const fd = new FormData(); fd.append("file", f);
                const res = await api<{ path: string }>(`/projects/${pid}/files`, { method: "POST", body: fd });
                await loadFiles(pid);
                return res.path;
              }} onError={setError} />
          ))}
        </div>

        {wf.outputs.length > 0 && (
          <div className="mt-6 rounded-lg bg-[#f6f8fa] p-3 text-sm">
            <span className="font-semibold">Produces:</span>{" "}
            <span className="font-mono text-xs">{wf.outputs.join(" · ")}</span>
          </div>
        )}
        {error ? <div className="mt-4"><ErrorBox error={error} /></div> : null}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button className={`${btn} min-h-12 flex-1 text-base`} disabled={busy}>
            {busy ? "Starting…" : wf.approval ? "Approve and run" : "Generate"}
          </button>
          {projectId && projectId !== NEW && (
            <Link className={btn2} href={`/projects/${projectId}`}>Open project</Link>
          )}
        </div>
        <p className="mt-3 text-xs text-faint">
          {wf.engine === "claude"
            ? "Runs on your local Claude Code CLI. Your inputs and files are sent to Anthropic under your account."
            : "Runs the repository's own engine on the server. Model steps use your Claude Code login."}
          {" "}You will see live progress and the resulting files in the project.
        </p>
      </form>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><div className="mb-1.5 text-sm font-semibold">{label}</div>{children}</div>;
}

function InputField({ inp, value, files, onChange, onUpload, onError }: {
  inp: WorkflowInput; value: string | boolean | undefined; files: WorkspaceFile[];
  onChange: (v: string | boolean) => void; onUpload: (f: File) => Promise<string>; onError: (e: unknown) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const label = inp.label + (inp.required ? " *" : "");
  const cls = "w-full rounded-lg border border-line bg-white px-3";

  if (inp.kind === "checkbox") {
    return (
      <label className="flex items-start gap-3 rounded-lg border border-[#f0d2ac] bg-[#fff8ef] p-3 text-sm">
        <input type="checkbox" className="mt-0.5 h-5 w-5" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        <span>{label}</span>
      </label>
    );
  }
  if (inp.kind === "file") {
    const matching = files.filter((f) => inp.accept?.some((ext) => f.path.toLowerCase().endsWith(ext)));
    return (
      <Field label={label}>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={`${btn2} min-h-11 flex-1`} disabled={uploading}
            onClick={() => fileRef.current?.click()}>{uploading ? "Uploading…" : "Upload file"}</button>
          <select aria-label={`${inp.label} from library`} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}
            className="min-h-11 min-w-[200px] flex-1 rounded-lg border border-line bg-white px-3 text-sm">
            <option value="">From library…</option>
            {matching.map((f) => <option key={f.path} value={f.path}>{f.path}</option>)}
          </select>
        </div>
        <input ref={fileRef} type="file" className="hidden" accept={inp.accept?.join(",")}
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setUploading(true);
            try { onChange(await onUpload(f)); } catch (err) { onError(err); } finally {
              setUploading(false); e.target.value = "";
            }
          }} />
        {value ? <p className="mt-1.5 text-xs text-accent">Selected: <span className="font-mono">{String(value)}</span></p>
          : <p className="mt-1.5 text-xs text-faint">Accepted: {inp.accept?.join(" ")}</p>}
      </Field>
    );
  }
  return (
    <Field label={label}>
      {inp.kind === "select" ? (
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} className={`${cls} min-h-11`}>
          {inp.options?.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : inp.kind === "textarea" ? (
        <textarea rows={4} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} className={`${cls} py-2`}
          required={inp.required} />
      ) : (
        <input value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} className={`${cls} min-h-11`}
          required={inp.required} />
      )}
    </Field>
  );
}
