export type Grid = string[][];

export interface Plot {
  x: number; y: number; crop: string; age: number; yield: number;
  watered: boolean; ready_in: number; fertilised: boolean;
}

export interface Weather { day?: number; weather?: string; events?: string[] }

export interface FarmState {
  day: number; cash: number; profit: number; opponent_cash: number;
  grid: Grid; prices: Record<string, number>; shed: Record<string, number>;
  weather: Weather; forecast: { day: number; weather: string; confidence: number }[];
  crops_growing: Record<string, number>; animals: Record<string, number>;
  free_plots: number; weeds: number; land_quadrants: string[]; town_shops: string[]; plots: Plot[];
}

export interface TraceStep {
  type: "thought" | "tool" | "action" | "error" | "guardrail" | "fallback";
  agent: string; text?: string; name?: string; args?: unknown; result?: unknown;
  plan?: Record<string, unknown>; ms?: number;
}

export interface Plan {
  plant?: Record<string, number>; sell?: Record<string, number>; buy_animals?: Record<string, number>;
  fertilise?: string[]; hands?: number; buy_land?: boolean;
}

export interface DayRecord {
  day: number; before: FarmState; trace: TraceStep[]; plan: Plan; rejected: string[];
  events: Weather; sales: Record<string, [number, number]>; reward: number; cash: number; profit: number;
  tokens: number; cost_usd: number; latency_s: number; llm_calls: number; fallback: boolean;
}

export interface RunHeader {
  agent: string; label: string; seed: number; events: boolean; provider?: string; live?: boolean; model?: string;
}

export interface RunData { header: RunHeader; days: DayRecord[]; summary: { final?: FarmState; profit?: number } }

export interface RunInfo {
  name: string; label: string; agent: string; provider: string; seed: number; profit: number; recorded: boolean;
}

export interface ProviderInfo { name: string; ready: boolean; detail: string }

export type Row = Record<string, number | string | number[]>;
export interface Results { summary: Row[]; rows: Row[]; reflection: Row[]; charts: string[] }

export interface MemoryFile {
  name: string;
  entries: { episode: number; seed: number; profit: number; lessons: string[] }[];
}

export interface Research { ablation: Row[]; arena: Row[]; matrix: Row[]; reflection: Row[] }

export interface ArenaPlayerDay { before: FarmState; plan: Plan | null; trace: TraceStep[]; reward: number | null }
export interface ArenaDay { day: number; events: Weather; players: ArenaPlayerDay[] }
export interface ArenaMatch {
  header: { seed: number; events: boolean; provider: string; players: { key: string; label: string }[] };
  days: ArenaDay[];
  summary: { profit0: number; profit1: number; cash0: number; cash1: number; winner: string; final: FarmState[] };
}
