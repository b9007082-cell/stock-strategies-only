// 若設了 NEXT_PUBLIC_API_BASE 就直接打 FastAPI（避開 Next dev proxy 的 socket hang up），
// 否則走 next.config rewrites 代理。長請求如 /api/run 強烈建議走直連。
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export type Strategy = {
  id: string;
  name: string;
  description?: string;
  source?: "default" | "manual" | "ai";
  created_at?: string;
  updated_at?: string;
  params: Record<string, any>;
};

export type RunResult = {
  universe?: { source: string; count: number; date: string | null };
  strategy: { id: string; name: string };
  market: { bullish: boolean; close: number | null; ma20: number | null; note: string };
  downgraded: number;
  summary: { total: number; buy: number; watch: number; skip: number; error: number };
  results: any[];
};

async function jfetch<T>(path: string, init?: RequestInit): Promise<T> {
  const request = (password = "") => fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(password ? { "X-Web-Password": password } : {}),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  let password = typeof window !== "undefined" ? sessionStorage.getItem("web_password") || "" : "";
  let res = await request(password);
  if (res.status === 401 && typeof window !== "undefined") {
    // Several dashboard requests start together. Reuse a password another
    // request may just have collected instead of opening duplicate prompts.
    password = sessionStorage.getItem("web_password") || "";
    if (!password) password = window.prompt("請輸入選股網站密碼") || "";
    if (password) sessionStorage.setItem("web_password", password);
    res = await request(password);
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch {}
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listStrategies: () => jfetch<{ strategies: Strategy[] }>("/api/strategies"),
  getDefaults: () => jfetch<{ params: Record<string, any> }>("/api/strategies/defaults"),
  getStrategy: (id: string) => jfetch<Strategy>(`/api/strategies/${id}`),
  saveStrategy: (s: Partial<Strategy>) =>
    jfetch<Strategy>("/api/strategies", { method: "POST", body: JSON.stringify(s) }),
  deleteStrategy: (id: string) =>
    jfetch<{ ok: boolean }>(`/api/strategies/${id}`, { method: "DELETE" }),
  generateAI: (prompt: string, name?: string) =>
    jfetch<Strategy>("/api/strategies/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, name }),
    }),
  getMarket: () => jfetch<any>("/api/market"),
  getWatchlist: () => jfetch<{ items: any[]; error?: string }>("/api/watchlist"),
  run: (strategy_id: string, limit?: number, universe: "watchlist" | "active" | "price_groups" = "watchlist", active_count = 20) =>
    jfetch<RunResult>("/api/run", {
      method: "POST",
      body: JSON.stringify({ strategy_id, limit, universe, active_count }),
    }),
};
