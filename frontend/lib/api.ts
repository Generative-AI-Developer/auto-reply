import type { ImportResultShape, RequestItem, Session, UserItem } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

const SESSION_KEY = "autoreply.session";

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function setSession(s: Session): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}

function authHeaders(): Record<string, string> {
  const s = getSession();
  return s ? { Authorization: `Bearer ${s.token}` } : {};
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export async function login(userId: string, password: string): Promise<Session> {
  const form = new URLSearchParams({ username: userId, password });
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  const data = await handle<{ access_token: string; user_id: string; role: string }>(res);
  return { token: data.access_token, user_id: data.user_id, role: data.role };
}

export async function listRequests(params: {
  q?: string;
  status_filter?: string;
  owner?: string;
} = {}): Promise<RequestItem[]> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.status_filter) qs.set("status_filter", params.status_filter);
  if (params.owner) qs.set("owner", params.owner);
  const res = await fetch(`${API_BASE}/requests?${qs.toString()}`, {
    headers: authHeaders(),
  });
  return handle<RequestItem[]>(res);
}

export async function createRequest(payload: {
  numbers: string[];
  duration_days: number | null;
  case_officer: string;
  justification: string;
  request_date: string | null;
}): Promise<RequestItem> {
  const res = await fetch(`${API_BASE}/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return handle<RequestItem>(res);
}

export async function importRequests(file: File): Promise<ImportResultShape> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/requests/import`, {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  return handle<ImportResultShape>(res);
}

export async function updateStatus(requestId: string, status: string): Promise<RequestItem> {
  const res = await fetch(`${API_BASE}/requests/${requestId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ status }),
  });
  return handle<RequestItem>(res);
}

export async function addUser(payload: {
  user_id: string;
  zone_section: string;
  password: string;
}): Promise<UserItem> {
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  return handle<UserItem>(res);
}

export function requestsSocket(onMessage: () => void): WebSocket | null {
  if (typeof window === "undefined") return null;
  const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/requests";
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => onMessage();
    return ws;
  } catch {
    return null;
  }
}
