"use client";

// Paper Studio home: your papers and their next stage, and "Start a paper".

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import type { PaperSummary } from "@/lib/paper";
import { btn, Card, Empty, ErrorBox, PageHeader } from "@/components/ui";

interface Types { types: Record<string, { label: string; stages: string[] }>; venues: Record<string, string> }

export default function PaperHome() {
  const router = useRouter();
  const [papers, setPapers] = useState<PaperSummary[] | null>(null);
  const [types, setTypes] = useState<Types | null>(null);
  const [form, setForm] = useState({ title: "", topic: "", type: "research_article", venue: "journal" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<PaperSummary[]>("/papers").then(setPapers).catch(setError);
    api<Types>("/paper-types").then(setTypes).catch(setError);
  }, []);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const p = await post<{ id: string }>("/projects", { title: form.title || form.topic.slice(0, 60) || "New paper", description: form.topic });
      await post(`/projects/${p.id}/paper`, { type: form.type, venue: form.venue, topic: form.topic });
      router.push(`/projects/${p.id}/paper`);
    } catch (err) { setError(err); setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-8">
      <PageHeader title="Paper Studio"
        sub="One guided path per paper. Each stage uses your own engines (PaperOrchestra, PaperCompiler, Idea Discovery V5, Referee-Lean), reads the earlier stages' files, and waits for your approval." />
      <ErrorBox error={error} />

      <Card className="mb-8 p-6">
        <form onSubmit={start} className="grid gap-4">
          <h2 className="text-lg font-semibold">Start a paper</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {types && Object.entries(types.types).map(([id, t]) => (
              <button type="button" key={id} onClick={() => setForm({ ...form, type: id })} aria-pressed={form.type === id}
                className={`rounded-xl border p-4 text-left ${form.type === id ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-[#8796a5]"}`}>
                <div className="font-semibold">{t.label}</div>
                <div className="mt-1 text-xs text-muted">{t.stages.join(" → ")}</div>
              </button>
            ))}
          </div>
          <label className="grid gap-1 text-sm font-medium">Topic or research question
            <textarea required rows={3} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}
              className="rounded-lg border border-line px-3 py-2 font-normal" placeholder="e.g. Verifying vision-language model oracles for blockchain insurance claims" />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium">Short title (optional)
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="min-h-11 rounded-lg border border-line px-3 font-normal" />
            </label>
            <label className="grid gap-1 text-sm font-medium">Venue / template
              <select value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} className="min-h-11 rounded-lg border border-line bg-white px-3 font-normal">
                {types && Object.entries(types.venues).map(([id, l]) => <option key={id} value={id}>{l}</option>)}
              </select>
            </label>
          </div>
          <div><button className={btn} disabled={busy}>{busy ? "Creating…" : "Start paper"}</button></div>
          <p className="text-xs text-faint">Already have ideas from Brainstorm? Open the idea card and press “Use this idea for a paper”.</p>
        </form>
      </Card>

      <h2 className="mb-3 text-lg font-semibold">Your papers</h2>
      {papers && !papers.length && <Empty title="No papers yet">Start one above.</Empty>}
      <div className="grid gap-3">
        {papers?.map((p) => (
          <Link key={p.project_id} href={`/projects/${p.project_id}/paper`} className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-white p-4 hover:border-accent">
            <div className="min-w-0 flex-1">
              <div className="font-semibold">{p.title}</div>
              <div className="text-sm text-muted">{p.type_label} · {p.venue_label}</div>
            </div>
            <div className="text-right text-sm">
              <div className="font-mono">{p.approved}/{p.total} stages approved</div>
              <div className="text-faint">{p.next_stage ? `Next: ${p.next_stage}` : "All stages approved"}</div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
