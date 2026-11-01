// Research loops (webapi/app/loops.py): idea forge and review -> fix -> re-review.

export interface LoopType {
  id: "idea_forge" | "review_fix"; label: string; pitch: string; icon: string;
  params: Record<string, number>; moves: { id: string; label: string }[];
}

export interface LoopSummary {
  id: string; type: LoopType["id"]; label: string; goal: string; status: LoopStatus; round: number; move: string | null;
  stop_reason: string | null; paused_reason: string | null; created_at: string; accepted: boolean;
  score?: number | null; verified_major?: number | null;
}

export type LoopStatus = "running" | "paused" | "finished" | "failed" | "stopped";

export interface Evidence {
  papers: number; recent_2024_plus: number; with_identifier: number; sampled: number; verified: number;
  fabricated_or_wrong: number; unreachable: number; problems: string[]; ok: boolean;
  lookups: { id: string; title: string; status: string; note: string }[];
}

export interface Concern {
  id: string; severity: string; verification: string; concern: string; location: string; quote_found: boolean;
  note: string; verified_major: boolean;
}

export interface LoopRound {
  round: number;
  moves: { move: string; label: string; status: string; run_id: string; attempt?: number; error?: string | null }[];
  metrics: {
    total?: number; criteria?: Record<string, number>; fatal_flaws?: string[]; verdict?: string; total_corrected?: boolean;
    claimed_total?: number | null; closest?: string[];
    concerns?: Concern[]; verified_major?: number; downgraded?: number; overall?: number | null; recommendation?: string;
  };
  evidence?: Evidence | null;
  fix?: { change_ratio: number; changed_lines: number; total_lines: number; template_kept: boolean;
          new_citation_keys: string[]; unknown_citation_keys: string[]; warnings?: string[] } | null;
  files: string[];
}

export interface Loop {
  id: string; type: LoopType["id"]; label: string; goal: string; mode: "auto" | "step"; status: LoopStatus;
  round: number; move: string | null; run_id: string | null; conversation_id: string;
  params: Record<string, number>; inputs: { manuscript?: string; external_review?: string };
  stop_reason: string | null; paused_reason?: string | null; notes: { at: string; text: string; used_in: string | null }[];
  rounds: LoopRound[]; best_round: number | null; final_files: string[]; accepted?: boolean; accepted_files?: string[];
  rubric: { id: string; label: string; max: number }[]; report: string;
}

export const STATUS_STYLE: Record<LoopStatus, [string, string]> = {
  running: ["Working", "bg-[#e8effc] text-[#24508f]"],
  paused: ["Waiting for you", "bg-[#fdf3dc] text-[#7a5300]"],
  finished: ["Finished", "bg-[#e3f3e8] text-[#1d6b3a]"],
  failed: ["Needs a retry", "bg-[#fbe7e5] text-[#8a1f17]"],
  stopped: ["Stopped", "bg-[#eeeeee] text-[#555]"],
};
