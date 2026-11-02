"use client";

// The instructions the user repeats in every session ("verify every reference", "surgical changes only", …),
// added to every agent task so they never have to be typed again.

import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn, btn2, Card, ErrorBox } from "@/components/ui";

interface Prefs { enabled: boolean; rules: string[]; custom: boolean; defaults: string[] }

export function PreferencesCard() {
  const [p, setP] = useState<Prefs | null>(null);
  const [text, setText] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const take = (x: Prefs) => { setP(x); setText(x.rules.join("\n")); setEnabled(x.enabled); };
  useEffect(() => { api<Prefs>("/preferences").then(take).catch(setError); }, []);

  async function save() {
    setError(null); setSaved(false);
    try {
      take(await api<Prefs>("/preferences", { method: "PUT", body: JSON.stringify({ enabled, rules: text.split("\n") }) }));
      setSaved(true);
    } catch (e) { setError(e); }
  }

  return (
    <Card className="mb-6 p-5">
      <h2 className="text-lg font-semibold">Your standing instructions</h2>
      <p className="mt-1 text-sm text-muted">Added to every agent task — chat, Paper Studio, recipes and research loops — so you no longer repeat them. One instruction per line.</p>
      <ErrorBox error={error} />
      <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Apply to every task</label>
      <textarea rows={9} value={text} onChange={(e) => { setText(e.target.value); setSaved(false); }} aria-label="Standing instructions"
        className="mt-2 w-full rounded-lg border border-line px-3 py-2 text-sm" disabled={!p} />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button className={btn} onClick={save} disabled={!p}>Save</button>
        <button className={btn2} onClick={async () => { try { take(await post<Prefs>("/preferences/reset")); } catch (e) { setError(e); } }}>Reset to defaults</button>
        {saved && <span className="text-sm text-[#1d6b3a]">Saved</span>}
      </div>
    </Card>
  );
}
