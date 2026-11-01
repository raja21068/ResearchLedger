"use client";

// Claude-app-style sidebar: New / Search / main places on top, chat history grouped by
// day in the middle, workspace and settings at the bottom. Collapses to icons.

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const I = {
  plus: "M12 5v14M5 12h14",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.3-4.3",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  folder: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
  tools: "M14 7l3-3 3 3-3 3M4 20l9-9M6 4h4v4H6zM15 15h5v5h-5z",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM8 7h7",
  brain: "M12 4v16M8 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1M16 4a3 3 0 0 1 3 3 3 3 0 0 1 1 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4",
  menu: "M4 6h16M4 12h16M4 18h16",
};

const MAIN: { href: string; label: string; icon: keyof typeof I }[] = [
  { href: "/paper", label: "Paper Studio", icon: "book" },
  { href: "/brainstorm", label: "Brainstorm ideas", icon: "spark" },
  { href: "/projects", label: "Projects", icon: "folder" },
  { href: "/tools", label: "Tools & skills", icon: "tools" },
  { href: "/library", label: "Library", icon: "book" },
  { href: "/memory", label: "Research memory", icon: "brain" },
  { href: "/results", label: "Results", icon: "chart" },
];

interface Recent { id: string; project_id: string; title: string; project_title: string; updated_at: string; last_status: string | null }

function Icon({ d }: { d: string }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="flex-none"><path d={d} /></svg>;
}

function group(iso: string) {
  const d = new Date(iso); const now = new Date();
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = (day(now) - day(d)) / 86400000;
  if (diff < 1) return "Today";
  if (diff < 2) return "Yesterday";
  if (diff < 7) return "Previous 7 days";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function Sidebar() {
  const path = usePathname();
  const search = useSearchParams();
  const [wide, setWide] = useState(true);
  const [recents, setRecents] = useState<Recent[]>([]);
  const [q, setQ] = useState("");
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    try { setWide(localStorage.getItem("rl-nav") !== "narrow"); } catch { /* storage blocked */ }
  }, []);
  useEffect(() => {
    api<Recent[]>("/conversations?limit=60").then(setRecents).catch(() => setRecents([]));
  }, [path, search]);
  // Inside a project: show that project's documents, like a file tree in a code editor.
  const projectId = path.match(/^\/projects\/(prj_[a-z0-9]+)/)?.[1] ?? null;
  const [docs, setDocs] = useState<{ path: string }[]>([]);
  useEffect(() => {
    if (!projectId) { setDocs([]); return; }
    api<{ path: string; kind: string }[]>(`/projects/${projectId}/files`)
      .then((fs) => setDocs(fs.filter((f) => ["pdf", "docx", "markdown"].includes(f.kind)
        && !/^(_inputs|control|memory|director)\//.test(f.path)).slice(0, 12)))
      .catch(() => setDocs([]));
  }, [projectId, search]);
  if (path.startsWith("/view/")) return null; // the full-tab document view is chrome-free

  const toggle = () => {
    setWide(!wide);
    try { localStorage.setItem("rl-nav", wide ? "narrow" : "wide"); } catch { /* storage blocked */ }
  };
  const active = (href: string) => path === href || path.startsWith(href + "/");
  const current = search.get("conv");
  const item = (on: boolean) => `flex min-h-9 items-center gap-3 whitespace-nowrap rounded-lg px-2.5 text-sm ${on
    ? "bg-[#e7e5df] font-medium text-ink" : "text-[#2f3a45] hover:bg-[#ecebe6]"}`;

  const shown = recents.filter((r) => !q || (r.title + " " + r.project_title).toLowerCase().includes(q.toLowerCase()));
  const groups: [string, Recent[]][] = [];
  for (const r of shown) {
    const g = group(r.updated_at);
    const last = groups.at(-1);
    if (last && last[0] === g) last[1].push(r); else groups.push([g, [r]]);
  }

  return (
    <nav aria-label="Primary"
      className={`flex flex-none bg-[#f5f4ef] max-lg:w-full max-lg:overflow-x-auto max-lg:border-b max-lg:border-line lg:sticky lg:top-0 lg:h-screen lg:flex-col lg:border-r lg:border-[#e4e2dc] ${wide ? "lg:w-[268px]" : "lg:w-[60px]"}`}>
      <div className="hidden items-center justify-between px-3 pt-3 lg:flex">
        {wide && <Link href="/" className="pl-1 font-serif text-[17px] font-semibold">ResearchLedger</Link>}
        <button onClick={toggle} aria-label={wide ? "Collapse sidebar" : "Expand sidebar"}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-[#ecebe6]"><Icon d={I.menu} /></button>
      </div>

      <div className="flex gap-0.5 p-2 lg:flex-col">
        <Link href="/" className={item(path === "/")} title="New chat"><Icon d={I.plus} /><span className={wide ? "" : "lg:hidden"}>New chat</span></Link>
        <button onClick={() => { setSearching(!searching); setQ(""); if (!wide) toggle(); }} className={`${item(searching)} max-lg:hidden`} title="Search chats">
          <Icon d={I.search} /><span className={wide ? "" : "lg:hidden"}>Search</span>
        </button>
        {MAIN.map((it) => (
          <Link key={it.href} href={it.href} title={it.label} className={item(active(it.href))}>
            <Icon d={I[it.icon]} /><span className={wide ? "" : "lg:hidden"}>{it.label}</span>
          </Link>
        ))}
        <Link href="/settings" title="Settings" className={`${item(active("/settings"))} lg:hidden`}><Icon d={I.gear} />Settings</Link>
      </div>

      {wide && (
        <div className="hidden min-h-0 flex-1 flex-col lg:flex">
          {searching && (
            <div className="px-3 pb-2">
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search chats…" aria-label="Search chats"
                className="min-h-9 w-full rounded-lg border border-line bg-white px-3 text-sm" />
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
            {projectId && (
              <div className="mt-2 rounded-lg bg-[#ecebe6]/60 p-1.5">
                <div className="flex items-center justify-between px-2 pb-1 text-xs font-medium text-faint">
                  Current project
                  <span className="flex gap-2">
                    <Link href={`/results?project=${projectId}`} className="hover:text-ink">Results</Link>
                    <Link href={`/memory?project=${projectId}`} className="hover:text-ink">Memory</Link>
                  </span>
                </div>
                {docs.length === 0 && <p className="px-2 py-1 text-xs text-faint">No documents yet.</p>}
                {docs.map((d) => (
                  <Link key={d.path} href={`/view/${projectId}?path=${encodeURIComponent(d.path)}`} target="_blank" title={d.path}
                    className="flex items-center gap-2 rounded-md px-2 py-1 text-[13px] text-[#2f3a45] hover:bg-[#e2e0d9]">
                    <span aria-hidden="true" className="text-faint">{d.path.endsWith(".pdf") ? "▤" : d.path.endsWith(".docx") ? "▥" : "▢"}</span>
                    <span className="min-w-0 truncate">{d.path.split("/").pop()}</span>
                  </Link>
                ))}
              </div>
            )}
            {recents.length === 0 && <p className="px-3 py-2 text-xs text-faint">Your chats will appear here.</p>}
            {groups.map(([g, rows]) => (
              <div key={g} className="mt-3">
                <div className="px-3 pb-1 text-xs font-medium text-faint">{g}</div>
                {rows.map((r) => (
                  <Link key={r.id} href={`/projects/${r.project_id}?conv=${r.id}`} title={`${r.title}\n${r.project_title}`}
                    className={`group flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm ${current === r.id ? "bg-[#e7e5df]" : "hover:bg-[#ecebe6]"}`}>
                    {r.last_status === "running" || r.last_status === "queued"
                      ? <span className="rl-pulse h-2 w-2 flex-none rounded-full bg-[#3b6fd8]" aria-label="running" />
                      : r.last_status === "failed" ? <span className="h-2 w-2 flex-none rounded-full bg-[#b91c1c]" aria-label="failed" /> : null}
                    <span className="min-w-0 truncate text-[#2f3a45]">{r.title}</span>
                  </Link>
                ))}
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 border-t border-[#e4e2dc] px-3 py-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">R</span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-sm font-medium">Local workspace</span>
              <span className="flex gap-2 text-xs text-faint">
                <Link href="/dashboard" className="hover:text-ink">Dashboard</Link>
                <Link href="/agents" className="hover:text-ink">Agents</Link>
                <Link href="/runs" className="hover:text-ink">Runs</Link>
              </span>
            </span>
            <Link href="/settings" aria-label="Settings" className="flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-[#ecebe6]"><Icon d={I.gear} /></Link>
          </div>
        </div>
      )}
    </nav>
  );
}
