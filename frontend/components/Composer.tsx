"use client";

// Claude Code-style input: grows with the text, Enter sends, Shift+Enter adds a line,
// "/" opens the command list, + attaches files, and Stop replaces Send while working.

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Command } from "@/lib/commands";

const MODELS = [["", "Default"], ["opus", "Opus"], ["sonnet", "Sonnet"], ["haiku", "Haiku"]];

export function Composer({ value, onChange, onSend, onStop, busy, working, commands, onAttach, attached, onDetach,
  model, onModel, placeholder, footer, autoFocus }: {
  value: string; onChange: (v: string) => void; onSend: () => void; onStop?: () => void;
  busy?: boolean; working?: boolean; commands: Command[]; onAttach: (files: FileList) => void;
  attached: string[]; onDetach: (p: string) => void; model: string; onModel: (m: string) => void;
  placeholder?: string; footer?: ReactNode; autoFocus?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [sel, setSel] = useState(0);

  // Auto-grow up to ~12 lines.
  useEffect(() => {
    const t = ref.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 300) + "px";
    t.style.overflowY = t.scrollHeight > 300 ? "auto" : "hidden";
  }, [value]);

  const slash = value.match(/^\/([\w.-]*)$/);
  const matches = useMemo(() => {
    if (!slash) return [];
    const q = slash[1].toLowerCase();
    return commands.filter((c) => c.name.toLowerCase().includes(q) || c.label.toLowerCase().includes(q)).slice(0, 12);
  }, [slash, commands]);
  useEffect(() => setSel(0), [matches.length]);

  function choose(c: Command) {
    onChange(`/${c.name} `);
    ref.current?.focus();
  }

  return (
    <div className="relative">
      {matches.length > 0 && (
        <div role="listbox" aria-label="Commands"
          className="absolute bottom-full left-0 right-0 z-20 mb-2 max-h-80 overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-lg">
          {matches.map((c, i) => (
            <button key={c.kind + c.id} role="option" aria-selected={i === sel} onMouseDown={(e) => { e.preventDefault(); choose(c); }}
              className={`flex w-full items-baseline gap-3 rounded-lg px-3 py-2 text-left text-sm ${i === sel ? "bg-[#eef1f4]" : ""}`}>
              <span className="font-mono text-accent">/{c.name}</span>
              <span className="min-w-0 flex-1 truncate text-muted">{c.label} — {c.hint}</span>
              <span className="text-[11px] text-faint">{c.kind === "skill" ? "skill" : "tool"}</span>
            </button>
          ))}
        </div>
      )}
      <div className="rounded-2xl border border-[#d6d6d0] bg-white shadow-[0_2px_12px_rgba(20,26,33,.06)] focus-within:border-[#9aa6b2]">
        {attached.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-3">
            {attached.map((a) => (
              <span key={a} className="inline-flex items-center gap-1.5 rounded-lg bg-[#f0f0ec] px-2 py-1 font-mono text-xs">
                {a.split("/").pop()}
                <button aria-label={`Remove ${a}`} onClick={() => onDetach(a)} className="text-faint hover:text-ink">×</button>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2 p-2">
          <input ref={fileRef} type="file" multiple className="hidden"
            onChange={(e) => { if (e.target.files?.length) onAttach(e.target.files); e.target.value = ""; }} />
          <button aria-label="Attach files" onClick={() => fileRef.current?.click()}
            className="flex h-9 w-9 flex-none items-center justify-center rounded-lg text-xl text-muted hover:bg-[#f0f0ec]">+</button>
          <label htmlFor="composer" className="sr-only">Message</label>
          <textarea id="composer" ref={ref} rows={1} value={value} autoFocus={autoFocus}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (matches.length) {
                if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => (s + 1) % matches.length); return; }
                if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => (s - 1 + matches.length) % matches.length); return; }
                if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) { e.preventDefault(); choose(matches[sel]); return; }
                if (e.key === "Escape") { onChange(""); return; }
              }
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); onSend(); }
            }}
            placeholder={placeholder ?? "Enter to send · Shift+Enter for a new line · / for tools"}
            className="max-h-[300px] min-h-9 flex-1 resize-none bg-transparent px-1 py-1.5 text-[15px] leading-relaxed outline-none" />
          <label htmlFor="composer-model" className="sr-only">Model</label>
          <select id="composer-model" value={model} onChange={(e) => onModel(e.target.value)}
            className="h-9 flex-none rounded-lg px-1 text-xs text-muted hover:bg-[#f0f0ec]">
            {MODELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          {working && onStop ? (
            <button aria-label="Stop" onClick={onStop}
              className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-ink text-white">
              <span className="h-3 w-3 rounded-sm bg-white" />
            </button>
          ) : (
            <button aria-label="Send" onClick={onSend} disabled={busy || !value.trim()}
              className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-accent text-white disabled:bg-[#c9d2da]">
              <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
          )}
        </div>
      </div>
      {footer}
    </div>
  );
}
