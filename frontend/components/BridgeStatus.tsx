"use client";

// Shows whether a Claude app worker (/rl-worker) is connected, and how to start one.

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface Bridge { executor: "bridge" | "cli"; worker_connected: boolean; worker_state?: "busy" | "free" | "offline"; last_poll_seconds_ago: number | null; queued: number }

export function useBridge(intervalMs = 5000) {
  const [b, setB] = useState<Bridge | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = () => api<Bridge>("/bridge/status").then((x) => alive && setB(x)).catch(() => {});
    tick();
    const t = setInterval(tick, intervalMs);
    return () => { alive = false; clearInterval(t); };
  }, [intervalMs]);
  return b;
}

export function WorkerHowTo() {
  return (
    <ol className="ml-5 list-decimal space-y-1 text-sm text-muted">
      <li>Open the <b>Claude app</b> and switch to the <b>Code</b> tab.</li>
      <li>Start a session in the folder <span className="font-mono">D:\AutoResearch\ResearchLedger</span>.</li>
      <li>Type <span className="font-mono font-semibold text-ink">/rl-worker</span> and press Enter. Leave that session open.</li>
    </ol>
  );
}

export function BridgeBanner({ waiting }: { waiting: boolean }) {
  const b = useBridge();
  if (!b || b.executor !== "bridge" || (b.worker_connected && !waiting)) return null;
  if (b.worker_connected) return null;
  return (
    <div className="rounded-xl border border-[#f0d2ac] bg-[#fff8ef] p-3 text-sm">
      <div className="font-semibold text-[#7a3a06]">
        {waiting ? "Your task is waiting for the Claude app." : "The Claude app worker is not connected."}
      </div>
      <p className="mb-1.5 mt-0.5 text-muted">Agents run inside your logged-in Claude app. To connect it:</p>
      <WorkerHowTo />
    </div>
  );
}
