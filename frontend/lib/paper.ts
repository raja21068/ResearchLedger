export type StageStatus = "locked" | "ready" | "running" | "needs_review" | "incomplete" | "failed" | "approved";

export interface PaperStage {
  id: string; title: string; purpose: string; engines: string[]; engines_present: boolean[];
  reads: string[]; outputs: string[]; status: StageStatus; outputs_found: { path: string; exists: boolean }[];
  run_id: string | null; error: string | null; approved_at: string | null; feedback: string | null;
}

export interface PaperView {
  type: string; type_label: string; venue: string; venue_label: string; topic: string;
  conversation_id: string; stages: PaperStage[];
  results?: { slots: number; measured: number; pending: number } | null;
  collected?: { slots: number; measured: number; pending: number; issues: string[] } | null;
  loop?: LoopView | null;
}

export interface PaperSummary {
  project_id: string; title: string; type_label: string; venue_label: string; topic: string;
  approved: number; total: number; next_stage: string | null; next_status: string;
}

export const STAGE_LABEL: Record<StageStatus, [string, string]> = {
  locked: ["Locked", "bg-[#eceae4] text-[#6b6a64]"],
  ready: ["Ready to run", "bg-[#dce6fb] text-[#1a3e8c]"],
  running: ["Running", "bg-[#dce6fb] text-[#1a3e8c]"],
  needs_review: ["Waiting for your approval", "bg-[#fbe7cf] text-[#7a3a06]"],
  incomplete: ["Incomplete outputs", "bg-[#f3d9d9] text-[#7f1d1d]"],
  failed: ["Failed", "bg-[#f3d9d9] text-[#7f1d1d]"],
  approved: ["Approved", "bg-[#d4eee9] text-[#07423d]"],
};

/** Short, readable name for an engine file path. */
export function engineName(path: string) {
  const parts = path.split("/");
  if (parts[0] === "skills") return `skill: ${parts[1]}`;
  if (path.includes("paperorchestra")) return `PaperOrchestra: ${parts.at(-1)}`;
  if (path.includes("PaperCompiler")) return `PaperCompiler: ${parts.at(-1)}`;
  if (path.includes("idea-discovery")) return `Idea Discovery V5: ${parts.at(-1)}`;
  if (path.includes("Referee-Lean")) return `Referee-Lean v2: ${parts.at(-1)}`;
  return parts.at(-1) ?? path;
}

export interface RefReport {
  checked_at: string; total: number; counts: Record<string, number>;
  entries: { key: string; status: string; source: string | null; note: string; filled: Record<string, string> }[];
}

export interface LoopView {
  rounds: { round: number; closed: boolean; open_verified_major: number;
            concerns: { id: string; severity: string; verification: string; concern: string; status: string; evidence: string; verified_major: boolean }[] }[];
  stop_reason: string | null; last_round: number; max_rounds: number; running_round: number | null; can_start: boolean;
}
