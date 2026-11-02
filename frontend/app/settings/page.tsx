"use client";

import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";
import type { Provider } from "@/lib/types";
import { type Bridge, useBridge, WorkerHowTo } from "@/components/BridgeStatus";
import { btn2, Card, ErrorBox, PageHeader } from "@/components/ui";
import { PreferencesCard } from "@/components/Preferences";
import { BackupsCard } from "@/components/BackupsCard";

const TONE: Record<string, string> = {
  installed: "bg-[#d4eee9] text-[#07423d]", unavailable: "bg-[#f3d9d9] text-[#7f1d1d]", planned: "bg-[#e6e9ed] text-[#3a4552]",
};

export default function Settings() {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const live = useBridge(3000);
  const [bridge, setBridge] = useState<Bridge | null>(null);
  useEffect(() => { if (live) setBridge(live); }, [live]);
  const check = () => { setError(null); setProviders(null); api<Provider[]>("/providers/health").then(setProviders).catch(setError); };
  useEffect(check, []);

  async function choose(executor: "bridge" | "cli") {
    try { setBridge(await api<Bridge>("/bridge/executor", { method: "PUT", body: JSON.stringify({ executor }) })); }
    catch (e) { setError(e); }
  }

  return (
    <main className="mx-auto max-w-[900px] px-4 py-7 sm:px-8">
      <PageHeader title="Settings" sub={<>Everything runs on this PC. API: <span className="font-mono">{API_URL}</span></>}
        actions={<button className={btn2} onClick={check}>Re-check</button>} />
      <ErrorBox error={error} />

      <Card className="mb-6 p-5">
        <h2 className="text-lg font-semibold">Where agents run</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {([
            ["bridge", "Claude app (recommended)", "Uses your logged-in Claude desktop app. Tasks from this website run in a Claude Code session in the app's Code tab, and the replies come back here."],
            ["cli", "claude.exe in the background", "The website starts the Claude Code CLI itself. Needs claude.exe to be logged in separately (claude auth login)."],
          ] as const).map(([id, title, text]) => (
            <button key={id} onClick={() => choose(id)} aria-pressed={bridge?.executor === id}
              className={`rounded-xl border p-4 text-left ${bridge?.executor === id ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-[#8796a5]"}`}>
              <div className="font-semibold">{bridge?.executor === id ? "● " : "○ "}{title}</div>
              <p className="mt-1 text-sm text-muted">{text}</p>
            </button>
          ))}
        </div>
        {bridge?.executor === "bridge" && (
          <div className="mt-4 rounded-lg bg-[#f6f8fa] p-4">
            <div className="flex items-center gap-2 font-medium">
              <span className={`h-2.5 w-2.5 rounded-full ${bridge.worker_connected ? "bg-accent" : "bg-[#b91c1c]"}`} />
              {bridge.worker_connected
                ? (bridge.worker_state === "busy" ? "Claude app worker is busy with a task (unresponsive tasks return to the queue after 15 minutes)" : `Claude app worker is free (checked in ${bridge.last_poll_seconds_ago}s ago)`)
                : "Claude app worker not connected"}
              {bridge.queued > 0 && <span className="text-sm text-faint">· {bridge.queued} task(s) waiting</span>}
            </div>
            {!bridge.worker_connected && <div className="mt-2"><WorkerHowTo /></div>}
          </div>
        )}
      </Card>

      <PreferencesCard />

      <BackupsCard />
      <Card className="divide-y divide-[#e6eaee]">
        <div className="p-5 pb-3 font-semibold">Tools on this PC</div>
        {!providers && !error && <p className="rl-pulse p-5 text-sm text-faint">Checking…</p>}
        {providers?.map((p) => (
          <div key={p.id} className="flex flex-wrap items-start justify-between gap-3 p-5">
            <div className="min-w-0"><div className="font-semibold">{p.name}</div>
              <div className="mt-1 break-words text-sm text-muted">{p.detail || "—"}</div></div>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE[p.status] ?? TONE.planned}`}>{p.status}</span>
          </div>
        ))}
      </Card>
    </main>
  );
}
