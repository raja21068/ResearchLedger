"use client";

// Document tools for one paper: compare two versions, ask the agent to revise one passage
// (shown as old vs new, applied only when you click), and build the submission package.

import { useCallback, useEffect, useState } from "react";
import { api, fileUrl, post } from "@/lib/api";
import { btn, btn2, ErrorBox } from "@/components/ui";

interface Edit {
  id: string; file: string; selection: string; instruction: string; status: "waiting" | "proposed" | "applied" | "failed";
  proposal: { original: string; revised: string; rationale: string } | null; warnings: string[];
}
interface Diff { added: number; removed: number; identical: boolean; diff: string[]; truncated: boolean }
interface Pkg { path: string; files: string[]; warnings: string[] }

export function PaperDocument({ projectId, files }: { projectId: string; files: string[] }) {
  const texFiles = files.filter((f) => f.endsWith(".tex") || (f.startsWith("paper/") && f.endsWith(".md")));
  const [a, setA] = useState(""); const [b, setB] = useState("");
  const [diff, setDiff] = useState<Diff | null>(null);
  const [file, setFile] = useState(""); const [selection, setSelection] = useState(""); const [instruction, setInstruction] = useState("");
  const [edits, setEdits] = useState<Edit[]>([]);
  const [pkg, setPkg] = useState<Pkg | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);

  const loadEdits = useCallback(() => api<Edit[]>(`/projects/${projectId}/paper/edits`).then(setEdits).catch(() => {}), [projectId]);
  useEffect(() => { loadEdits(); }, [loadEdits]);
  useEffect(() => {
    if (!edits.some((e) => e.status === "waiting")) return;
    const t = setInterval(loadEdits, 4000);
    return () => clearInterval(t);
  }, [edits, loadEdits]);

  async function run<T>(fn: () => Promise<T>, then?: (r: T) => void) {
    setBusy(true); setError(null);
    try { const r = await fn(); then?.(r); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  const base = `/projects/${projectId}/paper`;

  if (texFiles.length === 0) return null;
  return (
    <div className="mt-6 space-y-5 rounded-2xl border border-line bg-white p-5 text-sm">
      <h2 className="text-lg font-semibold">Document tools</h2>

      <section className="space-y-2">
        <h3 className="font-semibold">Compare two versions</h3>
        <div className="flex flex-wrap gap-2">
          <select aria-label="Older version" value={a} onChange={(e) => setA(e.target.value)} className="rounded-lg border border-line px-2 py-2">
            <option value="">Older…</option>{texFiles.map((f) => <option key={f}>{f}</option>)}
          </select>
          <select aria-label="Newer version" value={b} onChange={(e) => setB(e.target.value)} className="rounded-lg border border-line px-2 py-2">
            <option value="">Newer…</option>{texFiles.map((f) => <option key={f}>{f}</option>)}
          </select>
          <button className={btn2} disabled={busy || !a || !b} onClick={() => run(() => api<Diff>(`${base}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`), setDiff)}>Compare</button>
        </div>
        {diff && (diff.identical ? <p className="text-faint">The two files are identical.</p> : (
          <>
            <p className="text-muted">{diff.added} lines added, {diff.removed} removed{diff.truncated && " (showing the first part)"}.</p>
            <pre className="max-h-80 overflow-auto rounded-lg bg-[#f6f5f1] p-3 text-xs leading-5">
              {diff.diff.map((l, i) => (
                <div key={i} className={l.startsWith("+") && !l.startsWith("+++") ? "bg-[#d4eee9]" : l.startsWith("-") && !l.startsWith("---") ? "bg-[#f3d9d9]" : "text-faint"}>{l || " "}</div>
              ))}
            </pre>
          </>
        ))}
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold">Revise one passage</h3>
        <p className="text-muted">Paste the passage exactly as it is in the file. The agent proposes a replacement; nothing changes until you apply it.</p>
        <select aria-label="File to edit" value={file} onChange={(e) => setFile(e.target.value)} className="rounded-lg border border-line px-2 py-2">
          <option value="">File…</option>{texFiles.map((f) => <option key={f}>{f}</option>)}
        </select>
        <textarea rows={4} value={selection} onChange={(e) => setSelection(e.target.value)} aria-label="Passage" placeholder="Passage to revise"
          className="w-full rounded-lg border border-line px-3 py-2 font-mono text-xs" />
        <input value={instruction} onChange={(e) => setInstruction(e.target.value)} aria-label="What to change" placeholder="What should change? e.g. shorter, less strong claim"
          className="w-full rounded-lg border border-line px-3 py-2" />
        <button className={btn} disabled={busy || !file || selection.trim().length < 10}
          onClick={() => run(() => post(`${base}/edits`, { file, selection, instruction }), () => { setSelection(""); setInstruction(""); loadEdits(); })}>Ask the agent to revise it</button>
        {edits.map((e) => (
          <div key={e.id} className="rounded-lg border border-line p-3">
            <div className="flex flex-wrap justify-between gap-2 text-xs text-faint"><span className="font-mono">{e.file}</span><span>{e.status}</span></div>
            {e.status === "waiting" && <p className="rl-pulse text-faint">Waiting for the agent…</p>}
            {e.status === "failed" && <p className="text-[#7f1d1d]">The agent did not produce a proposal. Try again.</p>}
            {e.proposal && (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <div className="rounded bg-[#f3d9d9] p-2 text-xs"><b>Before</b><p className="mt-1 whitespace-pre-wrap">{e.selection}</p></div>
                <div className="rounded bg-[#d4eee9] p-2 text-xs"><b>After</b><p className="mt-1 whitespace-pre-wrap">{e.proposal.revised}</p></div>
                <p className="text-xs text-muted sm:col-span-2">{e.proposal.rationale}</p>
                {e.warnings.map((w) => <p key={w} className="text-xs text-[#7f1d1d] sm:col-span-2">⚠ {w}</p>)}
              </div>
            )}
            {e.status === "proposed" && <button className={`${btn} mt-2`} disabled={busy} onClick={() => run(() => post(`${base}/edits/${e.id}/apply`), loadEdits)}>Apply this change</button>}
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold">Submission package</h3>
        <p className="text-muted">A zip with the latest PDF and LaTeX, bibliography, figures, response letter and a checksum manifest. Warnings list placeholders that are still in the paper.</p>
        <button className={btn2} disabled={busy} onClick={() => run(() => post<Pkg>(`${base}/package`), setPkg)}>Build submission package</button>
        {pkg && (
          <div>
            <a className="text-accent underline" href={fileUrl(projectId, pkg.path, true)}>Download {pkg.path.split("/").pop()}</a>
            <p className="text-xs text-faint">{pkg.files.join(", ")}</p>
            {pkg.warnings.map((w) => <p key={w} className="text-xs text-[#7f1d1d]">⚠ {w}</p>)}
          </div>
        )}
      </section>
      {error ? <ErrorBox error={error} /> : null}
    </div>
  );
}
