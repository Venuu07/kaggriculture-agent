import type { ArenaMatch, DayRecord, FarmState, MemoryFile, ProviderInfo, Research, Results, RunData, RunHeader, RunInfo } from "./types";

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  runs: () => get<RunInfo[]>("/api/runs"),
  run: (name: string) => get<RunData>(`/api/runs/${encodeURIComponent(name)}`),
  results: () => get<Results>("/api/results"),
  providers: () => get<ProviderInfo[]>("/api/providers"),
  memory: () => get<MemoryFile[]>("/api/memory"),
  research: () => get<Research>("/api/research"),
  arenaMatches: () => get<string[]>("/api/arena/matches"),
  arenaMatch: (name: string) => get<ArenaMatch>(`/api/arena/matches/${encodeURIComponent(name)}`),
  liveStart: (body: { agent: string; provider: string; seed: number; events: boolean }) =>
    post<{ sid: string; header: RunHeader; state: FarmState; note: string }>("/api/live", body),
  liveStep: (sid: string) =>
    post<{ done: boolean; record: DayRecord | null; state: FarmState }>(`/api/live/${sid}/step`),
};
