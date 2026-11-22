import type { ShopData, ScenarioInfo, ScenarioResult, Advice, PlayDay, Plan, RealRun, WeatherSeason, ArenaMatch, DayRecord, FarmState, MemoryFile, ProviderInfo, Research, Results, RunData, RunHeader, RunInfo } from "./types";

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
  realLlm: () => get<RealRun[]>("/api/real-llm"),
  playStart: (body: { agent: string; seed: number; weather: string; events: boolean; provider: string }) =>
    post<{ sid: string; ai_label: string; note: string; states: FarmState[]; day: number; advice: Advice }>("/api/play", body),
  playDay: (sid: string, plan: Plan) => post<PlayDay>(`/api/play/${sid}/day`, { plan }),
  playSuggest: (sid: string) => get<{ plan: Plan }>(`/api/play/${sid}/suggest`),
  shop: () => get<ShopData>("/api/shop"),
  scenarios: () => get<{ scenarios: ScenarioInfo[]; results: Record<string, ScenarioResult> }>("/api/scenarios"),
  scenarioRun: (scenario: string, seed: number) => post<ScenarioResult>("/api/scenarios/run", { scenario, seed }),
  weather: () => get<WeatherSeason[]>("/api/weather"),
  arenaMatches: () => get<string[]>("/api/arena/matches"),
  arenaMatch: (name: string) => get<ArenaMatch>(`/api/arena/matches/${encodeURIComponent(name)}`),
  liveStart: (body: { agent: string; provider: string; seed: number; events: boolean; weather: string }) =>
    post<{ sid: string; header: RunHeader; state: FarmState; note: string }>("/api/live", body),
  liveStep: (sid: string) =>
    post<{ done: boolean; record: DayRecord | null; state: FarmState }>(`/api/live/${sid}/step`),
};
