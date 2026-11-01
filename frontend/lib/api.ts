// Thin client for the FastAPI backend (webapi/). Every mutating request carries
// the x-rl-client header the server requires (forces a CORS preflight).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    const msg = typeof detail === "string" ? detail
      : (detail as { message?: string })?.message ?? JSON.stringify(detail);
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.method && init.method !== "GET") headers.set("x-rl-client", "web");
  if (init.body && !(init.body instanceof FormData)) headers.set("content-type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, `Cannot reach the ResearchLedger API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export function fileUrl(projectId: string, path: string, download = false) {
  const q = new URLSearchParams({ path });
  if (download) q.set("download", "true");
  return `${API_URL}/api/v1/projects/${projectId}/files/raw?${q}`;
}

export function eventsUrl(runId: string, after: number) {
  return `${API_URL}/api/v1/runs/${runId}/events?after=${after}`;
}
