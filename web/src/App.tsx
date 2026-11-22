import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { ArenaView } from "./components/ArenaView";
import { FarmGrid } from "./components/FarmGrid";
import { HowItWorks } from "./components/HowItWorks";
import { MindFeed } from "./components/MindFeed";
import { PlanChips } from "./components/PlanChips";
import { ResearchView } from "./components/ResearchView";
import { ResultsView } from "./components/ResultsView";
import { WEATHER_ICON, agentColor as colorOf, money, titleCase } from "./constants";
import type { DayRecord, FarmState, ProviderInfo, RunHeader, RunInfo, WeatherSeason } from "./types";

type Tab = "farm" | "mind" | "arena" | "research" | "results" | "how";
type Mode = "replay" | "live";

const AGENTS = [
  { key: "llm_multi", label: "LLM multi-agent" },
  { key: "llm_single", label: "LLM single-agent" },
  { key: "greedy", label: "Greedy heuristic" },
  { key: "random", label: "Random" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("farm");
  const [mode, setMode] = useState<Mode>("replay");
  const [dark, setDark] = useState(() => { try { return localStorage.getItem("theme") === "dark"; } catch { return false; } });
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [runName, setRunName] = useState("");
  const [header, setHeader] = useState<RunHeader | null>(null);
  const [days, setDays] = useState<DayRecord[]>([]);
  const [finalState, setFinalState] = useState<FarmState | null>(null);
  const [initialState, setInitialState] = useState<FarmState | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2200);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [live, setLive] = useState({ agent: "llm_multi", provider: "offline", seed: 0, events: true, weather: "" });
  const [seasons, setSeasons] = useState<WeatherSeason[]>([]);
  const [sid, setSid] = useState("");
  const [liveDone, setLiveDone] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch { /* storage unavailable */ }
  }, [dark]);

  useEffect(() => {
    api.runs().then((r) => { setRuns(r); if (r.length) setRunName(r[0].name); }).catch((e) => setToast(`Cannot reach the API: ${e}`));
    api.providers().then(setProviders).catch(() => setProviders([]));
    api.weather().then(setSeasons).catch(() => setSeasons([]));
  }, []);

  useEffect(() => {
    if (mode !== "replay" || !runName) return;
    setPlaying(false);
    setBusy(true);
    api.run(runName).then((r) => {
      setHeader(r.header); setDays(r.days); setFinalState(r.summary.final ?? null);
      setInitialState(r.days[0]?.before ?? null); setCursor(0);
    }).catch((e) => setToast(String(e))).finally(() => setBusy(false));
  }, [mode, runName]);

  const startLive = useCallback(async () => {
    setPlaying(false); setBusy(true);
    try {
      const r = await api.liveStart(live);
      setSid(r.sid); setHeader(r.header); setDays([]); setInitialState(r.state); setFinalState(r.state);
      setCursor(0); setLiveDone(false);
      if (r.note) setToast(r.note);
    } catch (e) { setToast(String(e)); } finally { setBusy(false); }
  }, [live]);

  const total = mode === "live" ? 30 : days.length;
  const state: FarmState | null = cursor === 0 ? initialState : cursor < days.length ? days[cursor].before : finalState;
  const record: DayRecord | undefined = cursor > 0 ? days[cursor - 1] : undefined;

  const advance = useCallback(async () => {
    if (busyRef.current) return;
    if (cursor < days.length) { setCursor((c) => c + 1); return; }
    if (mode === "live" && sid && !liveDone) {
      busyRef.current = true; setBusy(true);
      try {
        const r = await api.liveStep(sid);
        if (r.record) { setDays((d) => [...d, r.record as DayRecord]); setFinalState(r.state); setCursor((c) => c + 1); }
        if (r.done) { setLiveDone(true); setPlaying(false); }
      } catch (e) { setToast(String(e)); setPlaying(false); } finally { busyRef.current = false; setBusy(false); }
      return;
    }
    setPlaying(false);
  }, [cursor, days.length, mode, sid, liveDone]);

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => { void advance(); }, cursor === 0 ? 300 : speed);
    return () => clearTimeout(t);
  }, [playing, cursor, speed, advance]);

  const cashSeries = useMemo(() => {
    const start = initialState?.cash ?? 3000;
    return [{ day: 0, profit: 0 }, ...days.slice(0, cursor).map((d) => ({ day: d.day + 1, profit: d.cash - start }))];
  }, [days, cursor, initialState]);

  const isOffline = header?.provider === "offline";
  const agentColor = header ? colorOf(header.agent) : "var(--accent)";
  const ended = (mode === "replay" && cursor >= days.length && days.length > 0) || (mode === "live" && liveDone && cursor >= days.length);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><span className="mark">A</span><div><b>AgriMind</b><small>An agentic farm manager</small></div></div>

        <label className="lbl">Mode</label>
        <div className="seg">
          <button className={mode === "replay" ? "on" : ""} onClick={() => setMode("replay")}>Replay</button>
          <button className={mode === "live" ? "on" : ""} onClick={() => { setMode("live"); setDays([]); setCursor(0); setSid(""); setInitialState(null); setHeader(null); }}>Live</button>
        </div>

        {mode === "replay" ? (
          <>
            <label className="lbl">Recorded run</label>
            <select value={runName} onChange={(e) => setRunName(e.target.value)}>
              {runs.map((r) => <option key={r.name} value={r.name}>{r.recorded ? "● " : ""}{r.label} · seed {r.seed}</option>)}
            </select>
            <p className="hint">Replays work with no internet and no API key.</p>
          </>
        ) : (
          <>
            <label className="lbl">Agent</label>
            <select value={live.agent} onChange={(e) => setLive({ ...live, agent: e.target.value })}>
              {AGENTS.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
            </select>
            {live.agent.startsWith("llm") && (
              <>
                <label className="lbl">LLM provider</label>
                <select value={live.provider} onChange={(e) => setLive({ ...live, provider: e.target.value })}>
                  {(providers.length ? providers : [{ name: "offline", ready: true, detail: "" }]).map((p) => (
                    <option key={p.name} value={p.name}>{p.name === "offline" ? "Offline reasoner (no key)" : `${titleCase(p.name)}${p.ready ? " (key found)" : " (no key)"}`}</option>
                  ))}
                </select>
              </>
            )}
            <div className="row2">
              <div><label className="lbl">Seed</label><input type="number" min={0} value={live.seed} onChange={(e) => setLive({ ...live, seed: Number(e.target.value) || 0 })} /></div>
              <div><label className="lbl">Weather</label>
                <button className={`toggle ${live.events ? "on" : ""}`} onClick={() => setLive({ ...live, events: !live.events })}>{live.events ? "events on" : "off"}</button>
              </div>
            </div>
            <label className="lbl">Weather source</label>
            <select value={live.weather} onChange={(e) => setLive({ ...live, weather: e.target.value, events: true })}>
              <option value="">Simulated (seeded)</option>
              {seasons.map((s) => <option key={s.name} value={s.name}>Real: {s.label.split(" (")[0]} · {s.start}</option>)}
            </select>
            {!seasons.length && <p className="hint">Fetch real weather once: <code>python -m kagri.realweather --district anantapur</code></p>}
            <button className="primary wide" disabled={busy} onClick={startLive}>{sid ? "Restart season" : "Start season"}</button>
          </>
        )}

        <label className="lbl">Speed <span className="muted">{(speed / 1000).toFixed(1)}s / day</span></label>
        <input type="range" min={400} max={5000} step={100} value={5400 - speed} onChange={(e) => setSpeed(5400 - Number(e.target.value))} />

        <div className="side-foot">
          <button className="ghost" onClick={() => setDark(!dark)}>{dark ? "Light" : "Dark"} theme</button>
          <small>Kaggle Kaggriculture rules · B.Tech major project</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Agentic AI for <em>farm profit</em> maximisation</h1>
            <div className="sub">
              {header ? (
                <>
                  <span className="badge" style={{ color: agentColor }}><i className="d" /><span style={{ color: "var(--ink)" }}>{header.label}</span></span>
                  <span className="badge gray">seed {header.seed}</span>
                  <span className="badge gray">{mode === "live" ? "LIVE" : "REPLAY"}</span>
                  {isOffline && <span className="badge amber" title="Deterministic rule-based reasoner speaking the same tool protocol; not a language model">offline reasoner · no LLM</span>}
                  {header.weather_source && header.weather_source !== "simulated"
                    ? <span className="badge" style={{ color: "var(--t-blue)" }}><i className="d" />real weather · {header.weather_source.split(" (")[0]}</span>
                    : header.events && <span className="badge gray">weather & events on</span>}
                </>
              ) : <span className="muted">{mode === "live" ? "Configure the season on the left and press Start." : "Loading runs…"}</span>}
            </div>
          </div>
          <nav className="tabs">
            {([["farm", "Live farm"], ["mind", "Agent's mind"], ["arena", "Arena"], ["research", "Research"], ["results", "Results"], ["how", "How it works"]] as [Tab, string][]).map(([k, l]) => (
              <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
            ))}
          </nav>
        </header>

        {toast && <div className="toast" onClick={() => setToast("")}>{toast} <span className="muted">(click to dismiss)</span></div>}

        {(tab === "farm" || tab === "mind") && state && (
          <>
            <Metrics state={state} record={record} played={cursor} total={total} />
            <div className="controls">
              <button title="Back to day 0" onClick={() => { setPlaying(false); setCursor(0); }} disabled={cursor === 0}>⏮</button>
              <button title="Previous day" onClick={() => { setPlaying(false); setCursor((c) => Math.max(0, c - 1)); }} disabled={cursor === 0}>◀</button>
              <button className="primary play" onClick={() => setPlaying(!playing)} disabled={ended || (mode === "live" && !sid)}>
                {playing ? "⏸ Pause" : ended ? "Season over" : "▶ Play"}
              </button>
              <button title="Next day" onClick={() => { setPlaying(false); void advance(); }} disabled={ended || busy || (mode === "live" && !sid)}>▶|</button>
              <input className="timeline" type="range" min={0} max={Math.max(days.length, 1)} value={cursor}
                onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)); }} />
              <span className="muted day-label">{busy ? "agent is thinking…" : `day ${cursor} of ${total}`}</span>
            </div>
          </>
        )}

        <Boundary key={tab}>
          {tab === "farm" && state && (
            <div className="farm-layout">
              <div className="card farm-card">
                <div className="card-head">
                  <h3>Your farm</h3>
                  <span className="muted small">{state.land_quadrants.length}/4 quadrants · {state.free_plots} free plots · {state.weeds} weeds</span>
                </div>
                <FarmGrid state={state} />
                {ended && <div className="season-over fade-in">Season over. Profit <b>{money(state.profit)}</b> vs opponent {money(state.opponent_cash - 3000)}</div>}
              </div>
              <div className="farm-side">
                <WeatherCard state={state} />
                <div className="card">
                  <h3>Today's decision</h3>
                  {record ? <PlanChips plan={record.plan} /> : <p className="muted">No decision yet: press Play.</p>}
                  {record && <button className="link" onClick={() => setTab("mind")}>See how the agent decided →</button>}
                </div>
                <div className="card">
                  <h3>Profit so far</h3>
                  <ResponsiveContainer width="100%" height={150}>
                    <AreaChart data={cashSeries} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
                      <defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={agentColor} stopOpacity={0.35} /><stop offset="100%" stopColor={agentColor} stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid vertical={false} stroke="var(--grid)" />
                      <XAxis dataKey="day" tick={{ fontSize: 10, fill: "var(--muted)" }} domain={[0, 30]} type="number" />
                      <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 10, fill: "var(--muted)" }} width={52} />
                      <Tooltip formatter={(v: number) => money(v)} labelFormatter={(d) => `After day ${d}`} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
                      <Area dataKey="profit" stroke={agentColor} strokeWidth={2} fill="url(#g)" isAnimationActive={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <ShedAndPrices state={state} prevPrices={cursor > 1 ? days[cursor - 2]?.before?.prices : undefined} />
              </div>
            </div>
          )}
          {tab === "mind" && (
            <div className="mind-layout">
              <div className="card"><MindFeed record={record} animate={playing || mode === "live"} stepMs={Math.max(120, Math.min(450, speed / ((record?.trace.length ?? 4) + 2)))} /></div>
              <div className="card day-list">
                <h3>Season log</h3>
                <ol>
                  {days.map((d, i) => (
                    <li key={d.day} className={cursor === i + 1 ? "on" : ""} onClick={() => { setPlaying(false); setCursor(i + 1); }}>
                      <span>Day {d.day}</span>
                      <span className="wx-s" title={d.events?.weather}>{WEATHER_ICON[d.events?.weather ?? ""] ?? ""}</span>
                      <span className={d.reward >= 0 ? "pos" : "neg"}>{d.reward >= 0 ? "+" : ""}{money(d.reward, true)}</span>
                      
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          )}
          {tab === "arena" && <ArenaView speed={speed} />}
          {tab === "research" && <ResearchView />}
          {tab === "results" && <ResultsView />}
          {tab === "how" && <HowItWorks />}
          {(tab === "farm" || tab === "mind") && !state && (
            <div className="empty big">{mode === "live" ? "Pick an agent and press ▶ Start season." : busy ? "Loading…" : "No recorded runs found. Run python -m kagri.evaluate first."}</div>
          )}
        </Boundary>
      </main>
    </div>
  );
}

function Metrics({ state, record, played, total }: { state: FarmState; record?: DayRecord; played: number; total: number }) {
  const lead = state.cash - state.opponent_cash;
  return (
    <div className="metrics">
      <Metric label="Day" value={`${played}`} sub={`of ${total}`} />
      <Metric label="Cash" value={money(state.cash)} sub="in the bank" />
      <Metric label="Profit" value={money(state.profit)} sub="since day 0" tone={state.profit >= 0 ? "pos" : "neg"} />
      <Metric label="Today" value={record ? `${record.reward >= 0 ? "+" : ""}${money(record.reward)}` : "–"} sub="cash change" tone={record && record.reward < 0 ? "neg" : "pos"} />
      <Metric label="vs opponent" value={`${lead >= 0 ? "+" : ""}${money(lead, true)}`} sub={`starter bot: ${money(state.opponent_cash, true)}`} tone={lead >= 0 ? "pos" : "neg"} />
      <Metric label="Farm" value={`${Object.values(state.crops_growing).reduce((a, b) => a + b, 0)} · ${Object.values(state.animals).reduce((a, b) => a + b, 0)}`} sub="plants · animals" />
    </div>
  );
}

function Metric({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="metric">
      <div className="eyebrow">{label}</div>
      <div key={value} className={`mval ${tone ?? ""} tick`}>{value}</div>
      <div className="muted small">{sub}</div>
    </div>
  );
}

function WeatherCard({ state }: { state: FarmState }) {
  const w = state.weather?.weather ?? "";
  return (
    <div className={`card weather-card w-${w}`}>
      <div className="wx">
        <span className="wx-glyph">{WEATHER_ICON[w] ?? "–"}</span>
        <div><div className="eyebrow">Today</div><b>{w ? titleCase(w) : "–"}</b></div>
      </div>
      {state.weather?.real && (
        <div className="real-wx">
          <span>{state.weather.real.place}</span><span>{state.weather.real.date}</span>
          <span>{state.weather.real.rain_mm.toFixed(1)} mm rain</span><span>{state.weather.real.tmax_c.toFixed(0)}°C max</span>
        </div>
      )}
      {(state.weather?.events ?? []).map((e, i) => <div key={i} className="event fade-in">{e}</div>)}
      {state.forecast?.length > 0 && (
        <div className="forecast">
          {state.forecast.map((f) => <div key={f.day} className="fc"><span>{WEATHER_ICON[f.weather] ?? "?"} {titleCase(f.weather)}</span><small>day {f.day}</small></div>)}
          <small className="muted">forecast · {Math.round((state.forecast[0]?.confidence ?? 0) * 100)}% reliable</small>
        </div>
      )}
    </div>
  );
}

const SHOW = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"];

function ShedAndPrices({ state, prevPrices }: { state: FarmState; prevPrices?: Record<string, number> }) {
  return (
    <div className="card">
      <h3>Market & shed</h3>
      <table className="prices">
        <tbody>
          {SHOW.map((item) => {
            const p = state.prices[item];
            const prev = prevPrices?.[item];
            const d = prev !== undefined ? p - prev : 0;
            return (
              <tr key={item}>
                <td>{titleCase(item)}</td>
                <td className="num">${p}</td>
                <td className={`num ${d > 0 ? "pos" : d < 0 ? "neg" : "muted"}`}>{d > 0 ? `▲${d}` : d < 0 ? `▼${-d}` : "·"}</td>
                <td className="num muted">{state.shed[item] ? `${state.shed[item]} in shed` : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

class Boundary extends Component<{ children: ReactNode }, { err: string }> {
  state = { err: "" };
  static getDerivedStateFromError(e: Error) { return { err: e.message }; }
  render() {
    if (this.state.err) return <div className="empty">Something went wrong in this view ({this.state.err}). Switch tabs or reload; the server is fine.</div>;
    return this.props.children;
  }
}
