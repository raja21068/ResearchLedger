"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SECTION_LABEL, type SkillCatalog, type Workflow } from "@/lib/types";
import { CapabilityBadge, ErrorBox, PageHeader } from "@/components/ui";

export default function AllTools() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [catalog, setCatalog] = useState<SkillCatalog | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    api<Workflow[]>("/workflows").then(setWorkflows).catch(setError);
    api<SkillCatalog>("/skills").then(setCatalog).catch(setError);
  }, []);

  const m = (...s: string[]) => s.some((x) => x.toLowerCase().includes(q.toLowerCase()));
  const sections = (Object.keys(SECTION_LABEL) as Workflow["section"][])
    .map((s) => [SECTION_LABEL[s], workflows.filter((w) => w.section === s && m(w.name, w.description))] as const)
    .filter(([, items]) => items.length);
  const skills = catalog?.skills.filter((s) => m(s.name, s.description, s.category)) ?? [];
  const cats = [...new Set(skills.map((s) => s.category))];

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title="All tools"
        sub={<>Research tools open a form; skills run your task through a skill from your skill folders. {catalog &&
          <>{catalog.skills.length} skills found; {catalog.zipped_packages} zipped packages are not used until unpacked.</>}</>} />
      <ErrorBox error={error} />
      <input aria-label="Search tools" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tools and skills…"
        className="mb-6 min-h-11 w-full rounded-xl border border-line bg-white px-4" />

      {sections.map(([label, items]) => (
        <section key={label} className="mb-7">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-faint">{label}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((w) => (
              <Link key={w.id} href={`/tools/${w.id}`} className="rounded-xl border border-line bg-white p-4 hover:border-accent">
                <div className="flex items-start justify-between gap-2"><span className="font-semibold">{w.name}</span><CapabilityBadge status={w.status} /></div>
                <p className="mt-1.5 line-clamp-3 text-sm text-muted">{w.description}</p>
                <p className="mt-2 text-xs text-faint">{w.engine_label}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
      {cats.map((c) => (
        <section key={c} className="mb-7">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-faint">{c} · skills</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {skills.filter((s) => s.category === c).map((s) => (
              <Link key={s.id} href={`/?tool=${s.id}`} className="rounded-xl border border-line bg-white p-4 hover:border-accent">
                <div className="font-semibold">{s.name}</div>
                <p className="mt-1.5 line-clamp-3 text-sm text-muted">{s.description || "—"}</p>
                <p className="mt-2 text-xs text-faint">Skill · runs with Claude Code</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
