export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

let token: string | null = localStorage.getItem("es_token");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("es_token", t);
  else localStorage.removeItem("es_token");
}
export function getToken() {
  return token;
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiGet(path: string) {
  return handle(await fetch(API_BASE + path, { headers: authHeaders() }));
}

export async function apiPost(path: string, body?: any) {
  return handle(
    await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  );
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);
  const res = await fetch(API_BASE + "/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  return handle(res);
}

export function wsUrl(path: string) {
  const base = API_BASE.replace(/^http/, "ws");
  return base + path;
}
