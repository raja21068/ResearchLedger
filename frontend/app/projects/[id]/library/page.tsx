"use client";

// Paper library: the papers found for this project, merged by DOI / arXiv id, with four separate checks.
// The first three are done by the software against Crossref and arXiv. The fourth — does the paper really support
// the statement it is cited for — is only ever set by you, with a reason.

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn, btn2, Card, ErrorBox, PageHeader } from "@/components/ui";

interface Paper { id: string; title: string; authors: string[]; year: number | null; venue: string | null; doi: string | null;
  arxiv_id: string | null; url: string | null; sources: { source: string; retrieved_at: string }[];
  exists_level: string; metadata_level: string; retrievable_level: string; check_note: string | null;
  supports_level: string; supports_note: string | null }
interface Hit { title: string; authors: string[]; year: number | null; doi: string | null; arxiv_id: string | null; venue: string | null;
  url: string | null; in_library: string | null }

const TONE: Record<string, string> = { yes: "bg-[#dff3e4] text-[#14532d]", no: "bg-[#fbe4e4] text-[#7f1d1d]",
  unchecked: "bg-[#f4f5f7] text-[#3a4552]", supported: "bg-[#dff3e4] text-[#14532d]", partly: "bg-[#fff4dc] text-[#7a4b06]",
  not_supported: "bg-[#fbe4e4] text-[#7f1d1d]", unreviewed: "bg-[#f4f5f7] text-[#3a4552]" };

function Level({ name, value, hint }: { name: string; value: string; hint: string }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs ${TONE[value] ?? ""}`} title={hint}>{name}: {value.replace("_", " ")}</span>;
}

export default function LibraryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [source, setSource] = useState("openalex");
  const [query, setQuery] = useState("");
  const [path, setPath] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { api<{ papers: Paper[] }>(`/projects/${id}/library`).then((r) => setPapers(r.papers)).catch(setError); }, [id]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null); setMsg("");
    try { await fn(); load(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  const importPaths = () => act(async () => {
    const r = await post<{ created: number; merged: number; skipped: number }>(`/projects/${id}/library/import`, { path });
    setMsg(`${r.created} added, ${r.merged} already there, ${r.skipped} skipped.`);
  });

  return (
    <main className="mx-auto max-w-[1100px] px-4 py-7 sm:px-8">
      <div className="mb-1 text-sm text-faint"><Link href={`/projects/${id}/home`} className="hover:text-ink">← Back to the project</Link></div>
      <PageHeader title="Paper library"
        sub="Every paper found for this project, merged by DOI or arXiv id (never by similar titles). “Exists”, “metadata” and “retrievable” are checked against Crossref and arXiv. “Supports the claim” is only ever set by you after reading the paper; an existing DOI proves nothing about what the paper says." />
      <ErrorBox error={error} />
      {msg && <div className="mb-3 rounded-lg border border-line bg-[#f6f5f1] px-3 py-2 text-sm">{msg}</div>}

      <Card className="mb-5 space-y-3 p-4">
        <div className="flex flex-wrap gap-2">
          <select className="rounded-lg border border-line px-2 py-2 text-sm" value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source">
            <option value="openalex">OpenAlex</option><option value="arxiv">arXiv</option><option value="crossref">Crossref</option>
          </select>
          <input className="min-w-[220px] flex-1 rounded-lg border border-line px-3 py-2 text-sm" placeholder="Search for papers" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Search query" />
          <button className={btn} disabled={busy || query.trim().length < 3}
            onClick={() => act(async () => setHits((await post<{ hits: Hit[] }>(`/projects/${id}/library/search`, { source, query })).hits))}>Search</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <input className="min-w-[220px] flex-1 rounded-lg border border-line px-3 py-2 text-sm" placeholder="Import a file from the project, e.g. paper/refs.bib or loops/…/competitors.csv"
            value={path} onChange={(e) => setPath(e.target.value)} aria-label="File to import" />
          <button className={btn2} disabled={busy || !path.trim()} onClick={importPaths}>Import</button>
        </div>
        {hits && (
          <div className="space-y-2">
            {hits.length === 0 && <p className="text-sm text-muted">Nothing found.</p>}
            {hits.map((h, n) => (
              <div key={n} className="flex flex-wrap items-center gap-2 rounded border border-line px-3 py-2 text-sm">
                <span className="min-w-[200px] flex-1">{h.title} <span className="text-xs text-faint">{h.authors[0]}{h.authors.length > 1 ? " et al." : ""}, {h.year ?? "n.d."}</span></span>
                {h.in_library ? <span className="text-xs text-faint">already in the library</span>
                  : <button className={btn2} disabled={busy} onClick={() => act(() => post(`/projects/${id}/library/import`, { papers: [h], source }))}>Add</button>}
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="space-y-2">
        {papers.map((p) => (
          <Card key={p.id} className="p-4">
            <div className="font-medium">{p.title}</div>
            <div className="text-xs text-faint">
              {p.authors[0] ?? "unknown authors"}{p.authors.length > 1 ? " et al." : ""}, {p.year ?? "n.d."}{p.venue ? ` · ${p.venue}` : ""}
              {p.doi ? ` · doi:${p.doi}` : ""}{p.arxiv_id ? ` · arXiv:${p.arxiv_id}` : ""} · from {p.sources.map((s) => s.source).join(", ")}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Level name="exists" value={p.exists_level} hint="The DOI or arXiv id resolves at the registry." />
              <Level name="metadata" value={p.metadata_level} hint="The registry's title and year match this record." />
              <Level name="retrievable" value={p.retrievable_level} hint="An open page for the paper could be fetched." />
              <Level name="supports the claim" value={p.supports_level} hint="Only you can set this, after reading the paper." />
            </div>
            {p.check_note && <p className="mt-1 text-xs text-muted">{p.check_note}</p>}
            {p.supports_note && <p className="mt-1 text-xs text-muted">Your note: {p.supports_note}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              <button className={btn2} disabled={busy} onClick={() => act(() => post(`/projects/${id}/library/${p.id}/verify`))}>Check against Crossref / arXiv</button>
              <button className={btn2} disabled={busy} onClick={() => {
                const level = window.prompt("Does this paper support the statement it is cited for? Type: supported, partly or not_supported");
                if (!level) return;
                const note = window.prompt("Which statement, and what did you read in the paper?");
                if (note?.trim()) act(() => post(`/projects/${id}/library/${p.id}/supports`, { level: level.trim(), note }));
              }}>I read it…</button>
            </div>
          </Card>
        ))}
        {papers.length === 0 && <Card className="p-4 text-sm text-muted">No papers yet. Search above, or import the competitors file from an idea loop or your references.</Card>}
      </div>
    </main>
  );
}
