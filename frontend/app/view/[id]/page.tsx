"use client";

// Full-tab document view (opened from "Open in new tab ↗"), like a standalone
// artifact page in ChatGPT or Claude.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, use } from "react";
import { FileViewer } from "@/components/FileViewer";

function ViewInner({ id }: { id: string }) {
  const path = useSearchParams().get("path");
  if (!path) return <p className="p-6 text-sm text-muted">No file selected.</p>;
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <div className="flex h-[57px] items-center gap-3 border-b border-line px-4">
        <Link href={`/projects/${id}`} className="text-sm text-accent">← Back to project</Link>
        <span className="truncate font-semibold">{path.split("/").pop()}</span>
      </div>
      <FileViewer projectId={id} path={path} fullPage />
    </div>
  );
}

export default function ViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Suspense><ViewInner id={id} /></Suspense>;
}
