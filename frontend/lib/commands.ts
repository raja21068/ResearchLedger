"use client";

// Slash commands for the chat box, Claude Code style: "/brainstorm blockchain, LLM, VLM".
// Research tools (workflows) and skills share one list; the text after the command
// becomes the tool's main input.

import { useEffect, useState } from "react";
import { api, post } from "./api";
import type { Skill, SkillCatalog, Workflow } from "./types";

export interface Command { name: string; label: string; hint: string; kind: "workflow" | "skill"; id: string }

// Short names for the research tools; anything else uses its id.
const ALIASES: Record<string, string> = {
  brainstorm: "brainstorm", idea: "idea_generation", literature: "literature_review", proposal: "research_proposal",
  design: "research_design", code: "code_generation", analyze: "data_analysis", draft: "write_manuscript",
  thesis: "thesis_to_manuscript", edit: "language_editing", review: "quick_review", referee: "beihang_review",
  cite: "citation_check", ledger: "ledger_report", audit: "evidence_audit", experiments: "experiments_s4",
};

export function useCommands() {
  const [commands, setCommands] = useState<Command[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  useEffect(() => {
    Promise.all([api<Workflow[]>("/workflows"), api<SkillCatalog>("/skills")]).then(([wfs, cat]) => {
      setWorkflows(wfs); setSkills(cat.skills);
      const byId = new Map(wfs.map((w) => [w.id, w]));
      const wfCmds: Command[] = Object.entries(ALIASES).filter(([, id]) => byId.has(id)).map(([name, id]) => {
        const w = byId.get(id)!;
        return { name, label: w.name, hint: w.description, kind: "workflow", id };
      });
      const skillCmds: Command[] = cat.skills.map((s) => ({ name: s.slug, label: s.name, hint: s.description, kind: "skill", id: s.id }));
      setCommands([...wfCmds, ...skillCmds]);
    }).catch(() => {});
  }, []);
  return { commands, workflows, skills };
}

export function parseCommand(text: string, commands: Command[]) {
  const m = text.match(/^\/([\w.-]+)\s*([\s\S]*)$/);
  if (!m) return null;
  const cmd = commands.find((c) => c.name.toLowerCase() === m[1].toLowerCase());
  return cmd ? { cmd, rest: m[2].trim() } : null;
}

/**
 * Run a parsed command. Returns where to go next: the new chat, or the tool's form when
 * the command needs inputs a chat line cannot supply (e.g. a file nobody attached).
 */
export async function runCommand(projectId: string, cmd: Command, rest: string, workflows: Workflow[],
  attached: string[], model: string | null): Promise<string> {
  if (cmd.kind === "skill") {
    const r = await post<{ project_id: string; conversation_id: string }>(`/projects/${projectId}/tasks`,
      { prompt: rest || "Follow the skill for this project.", skill_id: cmd.id, files: attached, model });
    return `/projects/${r.project_id}?conv=${r.conversation_id}`;
  }
  const w = workflows.find((x) => x.id === cmd.id);
  if (!w) throw new Error(`Unknown tool ${cmd.name}`);
  const values: Record<string, string | boolean> = {};
  const text = w.inputs.find((i) => i.kind === "textarea" || i.kind === "text");
  if (text && rest) values[text.name] = rest;
  const file = w.inputs.find((i) => i.kind === "file");
  if (file && attached[0]) values[file.name] = attached[0];
  const missing = w.inputs.some((i) => i.required && !values[i.name]) || w.inputs.some((i) => i.kind === "checkbox");
  if (missing) {
    const q = new URLSearchParams({ project: projectId });
    if (text && rest) q.set(text.name, rest);
    return `/tools/${w.id}?${q}`;
  }
  const r = await post<{ project_id: string; conversation_id: string }>(`/projects/${projectId}/workflows/${w.id}`, { values });
  return `/projects/${r.project_id}?conv=${r.conversation_id}`;
}
