export const CROP_EMOJI: Record<string, string> = {
  WHEAT: "🌾", CARROT: "🥕", TOMATO: "🍅", STRAWBERRY: "🍓", MELON: "🍈",
  GOOSE: "🪿", COW: "🐄", SHEEP: "🐑", EGG: "🥚", MILK: "🥛", WOOL: "🧶", FERTILIZER: "🧪",
};

export const CODE_TO_NAME: Record<string, string> = {
  WH: "WHEAT", CA: "CARROT", TO: "TOMATO", ST: "STRAWBERRY", ME: "MELON",
  go: "GOOSE", co: "COW", sh: "SHEEP",
};

export const HARVEST_AGE: Record<string, number> = { WHEAT: 4, CARROT: 3, TOMATO: 11, STRAWBERRY: 16, MELON: 10 };

/** Text-presentation glyphs (\uFE0E) so they render in the type, not as emoji. */
export const WEATHER_ICON: Record<string, string> = {
  sunny: "\u2600\uFE0E", cloudy: "\u2601\uFE0E", heavy_rain: "\u2602\uFE0E", drought: "\u2668\uFE0E",
};

export const ROLE: Record<string, { icon: string; name: string; tone: string }> = {
  single: { icon: "F", name: "Farm Manager", tone: "green" },
  planner: { icon: "P", name: "Planner", tone: "blue" },
  market: { icon: "M", name: "Market Analyst", tone: "orange" },
  agronomist: { icon: "A", name: "Agronomist", tone: "teal" },
  manager: { icon: "G", name: "Manager", tone: "violet" },
  system: { icon: "!", name: "Guardrail", tone: "red" },
  shopkeeper: { icon: "S", name: "Shopkeeper", tone: "green" },
};

/** Categorical palette in fixed order (Random, Greedy, LLM single, LLM multi); each mode validated
 *  for colour-blind separation against its own surface. The hero series (multi-agent) is the field green. */
const PALETTE = {
  light: { random: "#3567b5", greedy: "#c4532a", llm_single: "#d19516", llm_multi: "#2e7d3f" },
  dark: { random: "#5b8fe0", greedy: "#bd3c28", llm_single: "#b88722", llm_multi: "#1f9a78" },
};

export const agentColor = (agent: string): string => {
  const mode = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  return (PALETTE[mode] as Record<string, string>)[agent] ?? "#888";
};

export const shortLabel = (label: string) =>
  label.replace(" (offline)", "").replace(" heuristic", "").replace("-agent", "");

export const money = (v: number | undefined | null, compact = false): string => {
  if (v === undefined || v === null || Number.isNaN(v)) return "–";
  const sign = v < 0 ? "−" : "";
  const a = Math.abs(v);
  if (compact && a >= 1000) return `${sign}$${(a / 1000).toFixed(1)}k`;
  return `${sign}$${Math.round(a).toLocaleString("en-US")}`;
};

export const titleCase = (s: string) => s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, " ");
