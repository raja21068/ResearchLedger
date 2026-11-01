"use client";

// "Ready-made agents": drop files and the system suggests the right agent, or pick one.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { Recipe, Suggestion } from "@/lib/recipes";

export function AgentsGrid() {
  const router = useRouter();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { api<Recipe[]>("/recipes").then(setRecipes).catch(() => {}); }, []);

  async function drop(list: FileList | null) {
    if (!list?.length) return;
    setBusy(true); setNote(null);
    try {
      const names = Array.from(list).map((f) => f.name);
      const s = await post<Suggestion[]>("/recipes/suggest", { filenames: names, text: "" });
      const pick = s[0]?.id ?? "review_paper";
      const p = await post<{ id: string }>("/projects", { title: `${s[0]?.name ?? "Task"}: ${names[0]}`.slice(0, 120) });
      const paths: string[] = [];
      for (const f of Array.from(list)) {
        const fd = new FormData(); fd.append("file", f);
        paths.push((await api<{ path: string }>(`/projects/${p.id}/files?folder=uploads`, { method: "POST", body: fd })).path);
      }
      router.push(`/do/${pick}?project=${p.id}&${paths.map((x) => `f=${encodeURIComponent(x)}`).join("&")}`);
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); setBusy(false); }
  }

  return (
    <section className="mt-12 w-full max-w-[900px]">
      <label className="flex cursor-pointer flex-col items-center gap-1 rounded-2xl border-2 border-dashed border-[#dcd6cc] bg-white/60 px-4 py-6 text-center hover:border-accent"
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); drop(e.dataTransfer.files); }}>
        <input type="file" multiple className="sr-only" onChange={(e) => drop(e.target.files)} />
        <span className="font-semibold">{busy ? "Choosing the right agent…" : "Drop your paper or files here"}</span>
        <span className="text-sm text-faint">The system picks the right agent and prompts for you.</span>
        {note && <span className="text-sm text-[#7f1d1d]">{note}</span>}
      </label>
      <h2 className="mb-3 mt-8 text-xs font-bold uppercase tracking-[.1em] text-faint">Ready-made agents</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {recipes.map((r) => (
          <Link key={r.id} href={`/do/${r.id}`} className="rounded-xl border border-line bg-white p-4 hover:border-accent">
            <div className="font-semibold">{r.name}</div>
            <p className="mt-1 text-sm text-muted">{r.pitch}</p>
            <p className="mt-2 text-xs text-faint">Upload: {r.inputs.filter((i) => i.required).map((i) => i.label).join(", ") || "optional"}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
