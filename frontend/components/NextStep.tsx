"use client";

// "Your result" + the next research step, shown when a job finishes (chat runs and loops alike).

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, fileUrl } from "@/lib/api";

interface Step { n: number; id: string; name: string }
interface Steps { steps: Step[]; recipe_step: Record<string, string>; loop_step: Record<string, string> }

let cache: Promise<Steps> | null = null;
const loadSteps = () => (cache ??= api<Steps>("/steps"));

/** kind: a run kind ("recipe:write_paper") or a loop type ("review_fix"). */
export function NextStep({ projectId, kind, files }: { projectId: string; kind: string; files: string[] }) {
  const [steps, setSteps] = useState<Steps | null>(null);
  useEffect(() => { loadSteps().then(setSteps).catch(() => { cache = null; }); }, []);
  if (!steps) return null;
  const sid = kind.startsWith("recipe:") ? steps.recipe_step[kind.slice(7)] : steps.loop_step[kind];
  const cur = steps.steps.find((s) => s.id === sid);
  const next = cur && steps.steps.find((s) => s.n === cur.n + 1);
  const shown = files.filter((f) => /\.(pdf|tex|md|docx|bib|json|csv|py)$/i.test(f)).slice(0, 6);
  if (!cur && !shown.length) return null;
  return (
    <section className="rounded-2xl border border-[#bfe0ca] bg-[#f1f8f3] p-4">
      <div className="text-sm font-semibold text-[#1d6b3a]">Your result{cur ? ` — ${cur.n}. ${cur.name} done` : ""}</div>
      {shown.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {shown.map((f) => (
            <li key={f} className="flex flex-wrap items-center gap-x-3">
              <span className="min-w-0 truncate font-mono text-xs">{f}</span>
              <Link className="text-accent underline" target="_blank" href={`/view/${projectId}?path=${encodeURIComponent(f)}`}>Open</Link>
              <a className="text-accent underline" href={fileUrl(projectId, f, true)}>Download</a>
            </li>
          ))}
        </ul>
      )}
      {next && (
        <Link href={`/step/${next.id}?project=${projectId}`}
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-dark">
          Next: {next.n}. {next.name} →
        </Link>
      )}
    </section>
  );
}
