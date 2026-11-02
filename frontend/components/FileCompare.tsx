"use client";

// Side-by-side comparison of a saved version (left) with a later version or the current file (right).
// Unchanged stretches are folded; removed lines are red on the left, added lines green on the right.

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { btn2, ErrorBox } from "./ui";

interface Block { tag: "equal" | "replace" | "delete" | "insert" | "skip"; a: string[]; b: string[]; a_start: number; b_start: number; count?: number }
interface Diff { old: number; new: number | null; added: number; removed: number; blocks: Block[] }

const LEFT: Record<string, string> = { replace: "bg-[#fbe4e4]", delete: "bg-[#fbe4e4]" };
const RIGHT: Record<string, string> = { replace: "bg-[#dff3e4]", insert: "bg-[#dff3e4]" };

function Lines({ lines, start, tone }: { lines: string[]; start: number; tone?: string }) {
  return (
    <>
      {lines.map((l, i) => (
        <div key={i} className={`flex ${tone ?? ""}`}>
          <span className="w-10 shrink-0 select-none pr-2 text-right text-faint">{start + i}</span>
          <span className="whitespace-pre-wrap break-all">{l || " "}</span>
        </div>
      ))}
    </>
  );
}

export function FileCompare({ projectId, path, old, onClose }: {
  projectId: string; path: string; old: number; onClose: () => void;
}) {
  const [diff, setDiff] = useState<Diff | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setDiff(null); setError(null);
    api<Diff>(`/projects/${projectId}/files/compare?path=${encodeURIComponent(path)}&old=${old}`).then(setDiff).catch(setError);
  }, [projectId, path, old]);

  return (
    <div className="min-h-full bg-white">
      <div className="sticky top-0 flex items-center gap-3 border-b border-line bg-white px-4 py-2 text-sm">
        <span className="font-semibold">Version {old} → now</span>
        {diff && <span className="text-faint"><span className="text-[#1d6b34]">+{diff.added}</span> · <span className="text-[#9b1c1c]">−{diff.removed}</span> lines</span>}
        <button className={`${btn2} ml-auto`} onClick={onClose}>Close compare</button>
      </div>
      {error ? <div className="p-4"><ErrorBox error={error} /></div> : null}
      {!diff && !error && <p className="rl-pulse p-5 text-sm text-faint">Comparing…</p>}
      {diff && diff.added === 0 && diff.removed === 0 && <p className="p-5 text-sm text-muted">No differences: this version is the same as the current file.</p>}
      {diff && (diff.added > 0 || diff.removed > 0) && (
        <div className="grid grid-cols-2 font-mono text-[12.5px] leading-relaxed">
          <div className="border-b border-r border-line px-2 py-1 text-xs font-semibold text-muted">Version {old}</div>
          <div className="border-b border-line px-2 py-1 text-xs font-semibold text-muted">Now</div>
          {diff.blocks.map((b, i) => b.tag === "skip" ? (
            <div key={i} className="col-span-2 border-y border-line bg-[#f4f5f7] px-3 py-0.5 text-xs text-faint">
              {b.count} unchanged line{b.count === 1 ? "" : "s"}
            </div>
          ) : (
            <div key={i} className="contents">
              <div className="border-r border-line"><Lines lines={b.a} start={b.a_start} tone={LEFT[b.tag]} /></div>
              <div><Lines lines={b.b} start={b.b_start} tone={RIGHT[b.tag]} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
