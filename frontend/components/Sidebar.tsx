"use client";

// Claude-style navigation: New task, Decisions, your Papers (long projects) and Quick jobs (one-off chats),
// the current paper's documents, and every tool page folded under "Tools". Settings at the bottom.

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const I = {
  plus: "M12 5v14M5 12h14",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.3-4.3",
  home: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  folder: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
  pen: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  lit: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM9 8h6M9 12h4",
  design: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM16.5 13v7M13 16.5h7",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  flask: "M9 3h6M10 3v6L5 18a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3",
  code: "M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14",
  doc: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5",
  review: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 12l2.5 2.5 4.5-5",
  thesis: "M3 8l9-4 9 4-9 4zM7 10v5c3 2 7 2 10 0v-5",
  evidence: "M9 12l2 2 4-4M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z",
  bot: "M5 9h14v10H5zM12 5v4M9 13h.01M15 13h.01",
  book: "M4 19V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2zM8 7h6",
  brain: "M12 4v16M8 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1M16 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1",
  results: "M3 3v18h18M7 15l4-4 3 3 5-6",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  tools: "M14 7l3-3 3 3-3 3M4 20l9-9M6 4h4v4H6z",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4",
  menu: "M4 6h16M4 12h16M4 18h16",
  loop: "M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4",
};
type IconName = keyof typeof I;
interface Item { href: string; label: string; icon: IconName }

// Every earlier page stays one click away, folded under "Tools" (closed by default).
const TOOLS: Item[] = [
  { href: "/dashboard", label: "Overview", icon: "home" },
  { href: "/paper", label: "Paper Studio", icon: "pen" },
  { href: "/loops", label: "Loops", icon: "loop" },
  { href: "/brainstorm", label: "Idea Discovery", icon: "spark" },
  { href: "/tools/literature_review", label: "Literature Review", icon: "lit" },
  { href: "/tools/research_design", label: "Research Design", icon: "design" },
  { href: "/tools/data_analysis", label: "Data Analysis", icon: "chart" },
  { href: "/tools/code_generation", label: "Code Generation", icon: "code" },
  { href: "/tools/experiments_s4", label: "Experiment Lab", icon: "flask" },
  { href: "/tools/write_manuscript", label: "Manuscripts", icon: "doc" },
  { href: "/tools/thesis_to_manuscript", label: "Thesis to Paper", icon: "thesis" },
  { href: "/tools/quick_review", label: "Peer Review", icon: "review" },
  { href: "/quality", label: "Quality Check", icon: "evidence" },
  { href: "/tools?section=evidence", label: "Evidence Center", icon: "evidence" },
  { href: "/tools", label: "All Tools & Skills", icon: "tools" },
  { href: "/agents", label: "Agent Directory", icon: "bot" },
  { href: "/memory", label: "Research Memory", icon: "brain" },
  { href: "/results", label: "Results", icon: "results" },
  { href: "/runs", label: "Run History", icon: "clock" },
];

interface Recent { id: string; project_id: string; title: string; project_title: string; project_kind?: string; updated_at: string; last_status: string | null }
interface PaperRow { id: string; title: string; updated_at: string }

function Icon({ d }: { d: string }) {
  return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="flex-none"><path d={d} /></svg>;
}

function readPref<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) as T : fallback; } catch { return fallback; }
}
function writePref(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked */ }
}

export function Sidebar() {
  const path = usePathname();
  const search = useSearchParams();
  const [wide, setWide] = useState(true);
  const [closed, setClosed] = useState<Record<string, boolean>>({ tools: true });
  const [recents, setRecents] = useState<Recent[]>([]);
  const [papers, setPapers] = useState<PaperRow[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [q, setQ] = useState("");
  const [searching, setSearching] = useState(false);
  const [docs, setDocs] = useState<{ path: string }[]>([]);
  const [worker, setWorker] = useState<{ executor: string; worker_connected: boolean; worker_state?: string } | null>(null);
  const projectId = path.match(/^\/projects\/(prj_[a-z0-9]+)/)?.[1] ?? search.get("project");
  const [approvals, setApprovals] = useState(0);
  useEffect(() => {
    const tick = () => api<{ counts: { approve: number; retry: number } }>("/inbox")
      .then((x) => setApprovals(x.counts.approve + x.counts.retry)).catch(() => {});
    tick(); const t = setInterval(tick, 10000); return () => clearInterval(t);
  }, [path]);

  useEffect(() => { setWide(readPref("rl-nav-wide", true)); setClosed(readPref("rl-nav-closed2", { tools: true })); }, []);
  useEffect(() => {
    api<Recent[]>("/conversations?limit=60").then(setRecents).catch(() => setRecents([]));
    api<PaperRow[]>("/projects?kind=paper").then(setPapers).catch(() => setPapers([]));
  }, [path, search]);
  useEffect(() => {
    const tick = () => api<{ executor: string; worker_connected: boolean; worker_state?: string }>("/bridge/status").then(setWorker).catch(() => setWorker(null));
    tick(); const t = setInterval(tick, 10000); return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!projectId) { setDocs([]); return; }
    api<{ path: string; kind: string }[]>(`/projects/${projectId}/files`)
      .then((fs) => setDocs(fs.filter((f) => ["pdf", "docx", "markdown"].includes(f.kind)
        && !/^(_inputs|control|memory|director|loops|data|code|results)\//.test(f.path)).slice(0, 6)))
      .catch(() => setDocs([]));
  }, [projectId, search]);
  if (path.startsWith("/view/")) return null; // the full-tab document view is chrome-free

  const toggleWide = () => { setWide(!wide); writePref("rl-nav-wide", !wide); };
  const toggleGroup = (id: string) => { const next = { ...closed, [id]: !closed[id] }; setClosed(next); writePref("rl-nav-closed2", next); };
  const fullPath = path + (search.toString() ? `?${search}` : "");
  const active = (href: string) => href.includes("?") ? fullPath === href : (path === href || (href !== "/tools" && path.startsWith(href + "/")));
  const current = search.get("conv");
  const row = (on: boolean) => `flex min-h-[34px] items-center gap-2.5 whitespace-nowrap rounded-lg px-2.5 text-[13px] ${on
    ? "bg-[#e9e5dd] font-semibold text-ink" : "text-[#4d4a44] hover:bg-[#edeae4] hover:text-ink"}`;
  const heading = (id: string, label: string, extra?: React.ReactNode) => (
    <div className="mt-3 flex items-center justify-between px-2.5 pb-1 text-[10px] font-bold uppercase tracking-[.1em] text-faint">
      <button onClick={() => toggleGroup(id)} aria-expanded={!closed[id]} className="flex items-center gap-1 uppercase tracking-[.1em] hover:text-ink">
        {label}<span aria-hidden="true">{closed[id] ? "+" : "–"}</span></button>
      {extra}
    </div>
  );

  const match = (t: string) => !q || t.toLowerCase().includes(q.toLowerCase());
  const quick = recents.filter((r) => r.project_kind === "quick" && match(r.title + " " + r.project_title));
  const visibleQuick = showAll || q ? quick : quick.slice(0, 8);
  const shownPapers = papers.filter((p) => match(p.title)).slice(0, q ? 50 : 8);
  const dot = (s: string | null) => s === "running" || s === "queued"
    ? <span className="rl-pulse h-2 w-2 flex-none rounded-full bg-[#3b6fd8]" aria-label="running" />
    : s === "failed" ? <span className="h-2 w-2 flex-none rounded-full bg-[#b64b43]" aria-label="failed" /> : null;
  const paperStatus = (pid: string) => recents.find((r) => r.project_id === pid)?.last_status ?? null;

  return (
    <nav aria-label="Primary"
      className={`flex flex-none bg-[#f5f3ef] max-lg:w-full max-lg:overflow-x-auto max-lg:border-b max-lg:border-line lg:sticky lg:top-0 lg:h-screen lg:flex-col lg:overflow-y-auto lg:border-r lg:border-line ${wide ? "lg:w-[252px]" : "lg:w-[64px]"}`}>
      <div className="hidden items-center justify-between gap-2 px-3 pb-1 pt-3 lg:flex">
        {wide && (
          <Link href="/" className="flex items-center gap-2 pl-1">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">R</span>
            <span className="text-[15px] font-semibold tracking-tight">ResearchLedger</span>
          </Link>
        )}
        <button onClick={toggleWide} aria-label={wide ? "Collapse sidebar" : "Expand sidebar"}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-faint hover:bg-[#edeae4] hover:text-ink"><Icon d={I.menu} /></button>
      </div>

      {/* New task + search */}
      <div className={`flex gap-1.5 p-2 ${wide ? "" : "lg:flex-col"}`}>
        <Link href="/" title="New task"
          className="flex min-h-9 flex-1 items-center gap-2 whitespace-nowrap rounded-lg bg-accent px-3 text-[13px] font-semibold text-white hover:bg-accent-dark">
          <Icon d={I.plus} /><span className={wide ? "" : "lg:hidden"}>New task</span>
        </Link>
        <button onClick={() => { setSearching(!searching); setQ(""); if (!wide) toggleWide(); }} aria-label="Search papers and jobs" title="Search"
          className="hidden h-9 w-9 flex-none items-center justify-center rounded-lg border border-line bg-white text-faint hover:text-ink lg:flex"><Icon d={I.search} /></button>
      </div>
      {wide && searching && (
        <div className="hidden px-2 pb-2 lg:block">
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search papers and jobs…" aria-label="Search papers and jobs"
            className="min-h-9 w-full rounded-lg border border-line bg-white px-3 text-sm" />
        </div>
      )}

      <div className="flex gap-0.5 px-2 lg:flex-col">
        <Link href="/inbox" title="Decisions" className={`${row(path === "/inbox")} justify-between`}>
          <span className="flex items-center gap-2.5"><Icon d={I.review} /><span className={wide ? "" : "lg:hidden"}>Decisions</span></span>
          {approvals > 0 && <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] font-bold text-white">{approvals}</span>}
        </Link>
        <Link href="/library" title="Library" className={row(active("/library"))}>
          <Icon d={I.book} /><span className={wide ? "" : "lg:hidden"}>Library</span>
        </Link>
        <Link href="/projects" title="Papers" className={`${row(path === "/projects")} ${wide ? "lg:hidden" : ""}`}>
          <Icon d={I.doc} /><span className="lg:hidden">Papers</span>
        </Link>
      </div>

      {wide && (
        <div className="hidden px-2 lg:block">
          {heading("papers", "Papers", <Link href="/projects" className="normal-case tracking-normal hover:text-ink">All</Link>)}
          {!closed.papers && (
            <>
              {papers.length === 0 && <p className="px-2.5 py-1 text-xs text-faint">Long projects appear here — start one by asking to write a paper.</p>}
              {shownPapers.map((p) => (
                <div key={p.id}>
                  <Link href={`/projects/${p.id}/home`} title={p.title}
                    className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px] ${projectId === p.id ? "bg-[#e9e5dd] font-semibold text-ink" : "text-[#4d4a44] hover:bg-[#edeae4]"}`}>
                    {dot(paperStatus(p.id)) ?? <Icon d={I.doc} />}<span className="min-w-0 truncate">{p.title}</span>
                  </Link>
                  {projectId === p.id && (
                    <div className="mb-1 ml-9 mt-0.5 text-xs">
                      <div className="flex flex-wrap gap-x-2.5">
                        <Link href={`/projects/${p.id}`} className="text-accent hover:underline">Chat</Link>
                        <Link href={`/projects/${p.id}/paper`} className="text-accent hover:underline">Writing</Link>
                        <Link href={`/loops?project=${p.id}`} className="text-accent hover:underline">Loops</Link>
                        <Link href={`/quality?project=${p.id}`} className="text-accent hover:underline">Check</Link>
                        <Link href={`/results?project=${p.id}`} className="text-accent hover:underline">Results</Link>
                      </div>
                      {docs.map((d) => (
                        <Link key={d.path} href={`/view/${p.id}?path=${encodeURIComponent(d.path)}`} target="_blank" title={d.path}
                          className="block truncate py-0.5 text-[12px] text-[#4d4a44] hover:underline">{d.path.split("/").pop()}</Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          {heading("quick", "Quick jobs")}
          {!closed.quick && (
            <>
              {quick.length === 0 && <p className="px-2.5 py-1 text-xs text-faint">One-off jobs — a review, a reference check — appear here.</p>}
              {visibleQuick.map((r) => (
                <Link key={r.id} href={`/projects/${r.project_id}?conv=${r.id}`} title={`${r.title}\n${r.project_title}`}
                  className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px] ${current === r.id ? "bg-[#e9e5dd]" : "hover:bg-[#edeae4]"}`}>
                  {dot(r.last_status)}<span className="min-w-0 truncate text-[#4d4a44]">{r.project_title}</span>
                </Link>
              ))}
              {!q && quick.length > 8 && (
                <button onClick={() => setShowAll(!showAll)} className="px-2.5 py-1 text-xs text-faint hover:text-ink">
                  {showAll ? "Show less" : `Show all ${quick.length}`}
                </button>
              )}
            </>
          )}

          {heading("tools", "Tools")}
          {!closed.tools && TOOLS.map((it) => (
            <Link key={it.href} href={it.href} title={it.label} className={row(active(it.href))}>
              <Icon d={I[it.icon]} /><span>{it.label}</span>
            </Link>
          ))}
        </div>
      )}

      {/* Bottom */}
      <div className="hidden border-t border-line p-2 lg:mt-auto lg:block">
        <Link href="/settings" title="Settings" className={row(active("/settings"))}>
          <Icon d={I.gear} /><span className={wide ? "" : "lg:hidden"}>Settings</span>
        </Link>
        {worker?.executor === "bridge" && (
          <Link href="/settings" title="Claude app worker status"
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs ${wide ? "" : "justify-center"} text-faint hover:bg-[#edeae4]`}>
            <span className={`h-2 w-2 flex-none rounded-full ${worker.worker_state === "busy" ? "rl-pulse bg-[#3b6fd8]" : worker.worker_connected ? "bg-[#47765d]" : "bg-[#b64b43]"}`} />
            <span className={wide ? "" : "lg:hidden"}>{worker.worker_state === "busy" ? "Claude app working" : worker.worker_connected ? "Claude app ready" : "Claude app not connected"}</span>
          </Link>
        )}
      </div>
    </nav>
  );
}
