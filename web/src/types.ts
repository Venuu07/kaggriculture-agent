export type Grid = string[][];

export interface Plot {
  x: number; y: number; crop: string; age: number; yield: number;
  watered: boolean; ready_in: number; fertilised: boolean;
}

export interface Weather {
  day?: number; weather?: string; events?: string[];
  real?: { date: string; rain_mm: number; tmax_c: number; place: string };
}

export interface WeatherSeason { name: string; label: string; start: string; counts: Record<string, number>; rain_mm: number }

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
  weather_source?: string;
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

export interface RealRun {
  name: string; label: string; agent: string; provider: string; model?: string; real: boolean; profit: number;
  llm_calls: number; tokens: number; cost_usd: number; fallback_days: number; tool_calls: number;
  days_with_tools: number; simulations: number; guardrails: number; minutes: number;
}

export interface Advice {
  crops: { crop: string; seed: number; days: number; profit_per_plot: number; feasible: boolean; price: number }[];
  animals: { animal: string; cost: number; product: string }[];
  cash: number; free_plots: number; shed: Record<string, number>; next_land_cost: number | null; days_left: number; growing: number;
}
export interface PlayDay {
  done: boolean; day: number; events: Weather; states: FarmState[]; advice: Advice | null;
  you: { plan: Plan; rejected: string[]; reward: number };
  ai: { day: number; trace: TraceStep[]; plan: Plan; rejected: string[]; reward: number; tokens: number; latency_s: number; llm_calls: number; fallback: boolean };
}
