"use client";

// Settings → Backups: the server copies and verifies the database every day (the last 14 are kept); file contents
// are already kept read-only by version. "Check everything" re-hashes saved versions and reports, never repairs.

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { btn2, Card, ErrorBox } from "./ui";

interface Backup { id: string; created_at: string; path: string; present: boolean; size: number | null; reason: string | null; objects: number }
interface Audit {
  ok: boolean; database_ok: boolean; checked_versions: number; total_versions: number; damaged: string[];
  deleted_since_last_save: string[]; changed_since_last_save: string[]; orphan_objects: number;
}

function when(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function BackupsCard() {
  const [list, setList] = useState<{ backups: Backup[]; folder: string } | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [busy, setBusy] = useState<"backup" | "audit" | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => { api<{ backups: Backup[]; folder: string }>("/backups").then(setList).catch(setError); }, []);
  useEffect(load, [load]);

  async function backupNow() {
    setBusy("backup"); setError(null);
    try { await post("/backups"); load(); } catch (e) { setError(e); } finally { setBusy(null); }
  }
  async function check() {
    setBusy("audit"); setError(null); setAudit(null);
    try { setAudit(await api<Audit>("/integrity?full=true")); } catch (e) { setError(e); } finally { setBusy(null); }
  }

  const last = list?.backups[0];
  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-lg font-semibold">Backups and safety check</h2>
        <button className={btn2} disabled={busy !== null} onClick={backupNow}>{busy === "backup" ? "Backing up…" : "Back up now"}</button>
        <button className={btn2} disabled={busy !== null} onClick={check}>{busy === "audit" ? "Checking…" : "Check everything"}</button>
      </div>
      <p className="mt-1 text-sm text-muted">
        The database is copied and verified automatically once a day; the last 14 copies are kept. Every version of
        every file is kept separately, read-only.
      </p>
      <ErrorBox error={error} />
      <p className="mt-3 text-sm">
        {!list ? "Loading…" : last
          ? <>Last backup: <b>{when(last.created_at)}</b> ({last.reason ?? "backup"}) · {list.backups.length} kept</>
          : "No backup yet. One is made when the server starts."}
      </p>
      {list && <p className="mt-1 break-all font-mono text-xs text-faint">{list.folder}</p>}
      {audit && (
        <div className={`mt-3 rounded-lg border px-3 py-2 text-sm ${audit.ok ? "border-[#b8e0d2] bg-[#effaf6]" : "border-[#f0c4c4] bg-[#fdf1f1]"}`}>
          <b>{audit.ok ? "All good." : "Problems found."}</b>{" "}
          Database {audit.database_ok ? "intact" : "DAMAGED"}; {audit.checked_versions} saved versions re-checked
          {audit.damaged.length ? <>, <b>{audit.damaged.length} damaged</b></> : ", none damaged"}.
          {(audit.changed_since_last_save.length > 0 || audit.deleted_since_last_save.length > 0) && (
            <> {audit.changed_since_last_save.length + audit.deleted_since_last_save.length} file(s) changed since they
              were last saved; they are saved before the next agent run or when you open their History.</>
          )}
          {!audit.ok && <> Restore the newest backup (see the folder above) before working further, and keep the damaged files for inspection.</>}
        </div>
      )}
    </Card>
  );
}
