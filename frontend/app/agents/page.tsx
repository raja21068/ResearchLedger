"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Agent, CapabilityStatus } from "@/lib/types";
import { Card, CapabilityBadge, ErrorBox, PageHeader } from "@/components/ui";

const FILTERS: (CapabilityStatus | "all")[] = ["all", "integrated", "available_standalone", "optional", "planned"];
const LABEL: Record<string, string> = { all: "All", integrated: "Integrated", available_standalone: "Standalone", optional: "Optional", planned: "Planned" };

export default function Agents() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [skills, setSkills] = useState<{ id: string; category: string }[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Agent[]>("/agents").then(setAgents).catch(setError);
    api<{ skills: { id: string; category: string }[] }>("/skills").then((c) => setSkills(c.skills)).catch(() => {});
  }, []);

  const shown = agents?.filter((a) => filter === "all" || a.status === filter) ?? [];
  const bySource = skills.reduce<Record<string, number>>((m, s) => ({ ...m, [s.category]: (m[s.category] ?? 0) + 1 }), {});

  return (
    <main className="mx-auto max-w-[1180px] px-4 py-7 sm:px-8">
      <PageHeader title="Agent Center"
        sub="Status comes from the server registry. Integrated means the web API can actually invoke it, and a test covers it. Standalone means the component exists in the repo but isn't wired in yet." />
      <ErrorBox error={error} />
      <div role="group" aria-label="Filter by status" className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            className={`min-h-10 rounded-full border px-4 text-sm ${filter === f ? "border-ink bg-ink text-white" : "border-line bg-white"}`}>
            {LABEL[f]} · {f === "all" ? agents?.length ?? 0 : agents?.filter((a) => a.status === f).length ?? 0}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {shown.map((a) => (
          <Card key={a.id} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div><div className="text-xs font-semibold uppercase tracking-wider text-faint">{a.category}</div>
                <h2 className="mt-1 text-lg font-semibold">{a.name}</h2></div>
              <CapabilityBadge status={a.status} />
            </div>
            <p className="mt-2 text-sm text-muted">{a.description}</p>
            <dl className="mt-3 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1.5 text-sm">
              {a.inputs.length > 0 && <><dt className="text-faint">Inputs</dt><dd>{a.inputs.join(", ")}</dd></>}
              {a.outputs.length > 0 && <><dt className="text-faint">Outputs</dt><dd>{a.outputs.join(", ")}</dd></>}
              {a.permissions && <><dt className="text-faint">Permissions</dt><dd>{a.permissions}</dd></>}
              <dt className="text-faint">Source</dt>
              <dd className="break-words font-mono text-xs">{a.implementation_ref ?? "—"}
                {a.implementation_present === false && <span className="ml-2 font-sans text-[#7f1d1d]">(not found on disk)</span>}</dd>
            </dl>
          </Card>
        ))}
      </div>
      <Card className="mt-6 p-5">
        <h2 className="text-lg font-semibold">Skills registry</h2>
        <p className="mt-1 text-sm text-muted">Skills are reusable procedures and rubrics, not autonomous agents. Found in your skill folders, by category:</p>
        <ul className="mt-2 text-sm">{Object.entries(bySource).map(([src, n]) => <li key={src}>{src}: {n}</li>)}</ul>
      </Card>
    </main>
  );
}
