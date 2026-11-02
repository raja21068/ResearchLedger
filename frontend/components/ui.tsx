import type { ReactNode } from "react";
import type { CapabilityStatus, RunStatus } from "@/lib/types";

const CAP: Record<CapabilityStatus, [string, string]> = {
  integrated: ["Integrated", "bg-[#d4eee9] text-[#07423d]"],
  available_standalone: ["Standalone", "bg-[#fbe7cf] text-[#7a3a06]"],
  optional: ["Optional", "bg-[#dce6fb] text-[#1a3e8c]"],
  planned: ["Planned", "bg-[#e6e9ed] text-[#3a4552]"],
  disabled: ["Disabled", "bg-[#f3d9d9] text-[#7f1d1d]"],
};

const RUN: Record<RunStatus, [string, string]> = {
  queued: ["Queued", "bg-[#e6e9ed] text-[#3a4552]"],
  running: ["Running", "bg-[#dce6fb] text-[#1a3e8c]"],
  succeeded: ["Succeeded", "bg-[#d4eee9] text-[#07423d]"],
  failed: ["Failed", "bg-[#f3d9d9] text-[#7f1d1d]"],
  cancelled: ["Cancelled", "bg-[#e6e9ed] text-[#3a4552]"],
};

function Chip({ label, cls }: { label: string; cls: string }) {
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
}

export const CapabilityBadge = ({ status }: { status: CapabilityStatus }) => <Chip label={CAP[status][0]} cls={CAP[status][1]} />;
export const RunBadge = ({ status }: { status: RunStatus }) => <Chip label={RUN[status][0]} cls={RUN[status][1]} />;

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">{title}</h1>
        {sub && <p className="mt-1.5 max-w-3xl text-[15px] text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-white ${className}`}>{children}</section>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-white/60 p-8 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}

/** One plain sentence: what happened and what to do. Technical detail stays behind "Details". */
export function friendlyError(error: unknown): { text: string; detail?: string } {
  const status = (error as { status?: number })?.status;
  const raw = error instanceof Error ? error.message : String(error);
  const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
  if (status === 0) return { text: "The ResearchLedger server isn't running. Start it with start_web.ps1, then try again.", detail: raw };
  if (status === 404) return { text: "That item no longer exists — it may have been deleted or archived.", detail: raw };
  if (status === 413) return { text: "That file is too large to upload." };
  if (status === 415) return { text: cap(raw.replace(/^file type/, "This file type")) + ". Use PDF, Word, .tex, .bib, Markdown, CSV or a .zip." };
  if (status === 422 || raw.startsWith("[{")) return { text: "Something in the form is missing or not valid. Check it and try again.", detail: raw };
  if (status && status >= 500) return { text: "Something went wrong on the server. Try again; if it keeps happening, look at the API window.", detail: raw };
  return { text: cap(raw) };
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const { text, detail } = friendlyError(error);
  return (
    <div role="alert" className="whitespace-pre-wrap break-words rounded-lg border border-[#e8b4b4] bg-[#fdf2f2] p-3 text-sm text-[#7f1d1d]">
      {text}
      {detail && detail !== text && <details className="mt-1 text-xs opacity-80"><summary className="cursor-pointer">Details</summary>{detail}</details>}
    </div>
  );
}

export const btn = "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent px-4 text-sm font-semibold text-white hover:bg-accent-dark disabled:opacity-50";
export const btn2 = "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-line bg-white px-4 text-sm font-medium text-ink hover:border-[#8796a5] disabled:opacity-50";

export function timeAgo(iso: string | null) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}
