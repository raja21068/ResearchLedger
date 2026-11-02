export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Project {
  id: string; title: string; description: string; domain: string; status: string; kind: "paper" | "quick";
  created_at: string; updated_at: string; conversations?: Conversation[];
}

export interface Conversation {
  id: string; project_id: string; title: string; claude_session_id: string | null;
  created_at: string; updated_at: string; runs?: Run[];
}

export interface RunEvent {
  id: number; ts: string; kind: string;
  payload: Record<string, unknown> & { text?: string };
}

export interface Run {
  id: string; project_id: string; conversation_id: string; kind: string; prompt: string; status: RunStatus;
  provider: string; model: string | null; created_at: string; started_at: string | null;
  finished_at: string | null; error: string | null; result_text: string | null;
  cost_usd: number | null; duration_ms: number | null; project_title?: string;
  events?: RunEvent[];
}

export interface WorkspaceFile {
  path: string; size: number; modified: number;
  kind: "pdf" | "docx" | "image" | "markdown" | "text" | "binary"; last_run_id: string | null;
}

export type CapabilityStatus = "integrated" | "available_standalone" | "optional" | "planned" | "disabled";

export interface Agent {
  id: string; name: string; category: string; status: CapabilityStatus; description: string;
  implementation_ref: string | null; implementation_present: boolean | null;
  inputs: string[]; outputs: string[]; permissions: string;
}

export interface Provider { id: string; name: string; status: string; detail: string }

export interface WorkflowInput {
  name: string; label: string; kind: "textarea" | "text" | "select" | "file" | "checkbox";
  required?: boolean; options?: string[]; default?: string; accept?: string[];
}

export interface Workflow {
  id: string; section: "discover" | "analyze" | "manuscripts" | "review" | "evidence"; name: string;
  engine: "cli" | "claude"; engine_label: string; status: CapabilityStatus; description: string;
  inputs: WorkflowInput[]; outputs: string[]; requires: string; approval?: boolean;
}

export interface Skill { id: string; name: string; slug: string; description: string; category: string }
export interface SkillCatalog { skills: Skill[]; zipped_packages: number; roots: string[] }

export interface ProgressStep { step: string; title: string; state: "done" | "running" | "not_started"; evidence: string[]; workflows: string[] }

export const SECTION_LABEL: Record<Workflow["section"], string> = {
  discover: "Discover", analyze: "Analyze", manuscripts: "Manuscripts", review: "Peer Review", evidence: "Evidence",
};
