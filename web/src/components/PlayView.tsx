import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { CROP_EMOJI, WEATHER_ICON, agentColor, money, titleCase } from "../constants";
import type { Advice, DayRecord, FarmState, Plan, PlayDay, WeatherSeason } from "../types";
import { FarmGrid } from "./FarmGrid";
import { MindFeed } from "./MindFeed";
import { PlanChips } from "./PlanChips";

const FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55];
const hireCost = (n: number) => FIB.slice(0, n).reduce((a, b) => a + b, 0);
const YOU = "#7a5a3a";

interface Game { sid: string; aiLabel: string; aiKey: string; states: FarmState[]; advice: Advice | null; day: number; done: boolean }

/** Play vs the AI: you farm seat 1, the agent farms seat 2, on one shared market. */
export function PlayView({ seasons }: { seasons: WeatherSeason[] }) {
  const [cfg, setCfg] = useState({ agent: "llm_multi", seed: 7, weather: "", events: true });
  const [game, setGame] = useState<Game | null>(null);
  const [plan, setPlan] = useState<Required<Pick<Plan, "plant" | "buy_animals">> & { hands: number; buy_land: boolean; sellAll: boolean }>(
    { plant: {}, buy_animals: {}, hands: 0, buy_land: false, sellAll: true });
  const [last, setLast] = useState<PlayDay | null>(null);
  const [race, setRace] = useState<{ day: number; you: number; ai: number }[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [showMind, setShowMind] = useState(false);

  const start = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.playStart({ ...cfg, provider: "offline" });
      setGame({ sid: r.sid, aiLabel: r.ai_label, aiKey: cfg.agent, states: r.states, advice: r.advice, day: r.day, done: false });
      setRace([{ day: 0, you: 0, ai: 0 }]); setLast(null);
      setPlan({ plant: {}, buy_animals: {}, hands: 0, buy_land: false, sellAll: true });
      if (r.note) setErr(r.note);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const endDay = async () => {
    if (!game) return;
    setBusy(true); setErr("");
    const adv = game.advice;
    const body: Plan = {
      plant: plan.plant, buy_animals: plan.buy_animals, hands: plan.hands, buy_land: plan.buy_land,
      sell: plan.sellAll && adv ? Object.fromEntries(Object.keys(adv.shed).filter((k) => !["GOOSE", "COW", "SHEEP"].includes(k)).map((k) => [k, "all" as unknown as number])) : {},
    };
    try {
      const r = await api.playDay(game.sid, body);
      setLast(r);
      setGame({ ...game, states: r.states, advice: r.advice ?? null, day: r.day, done: r.done });
      setRace((xs) => [...xs, { day: xs.length, you: r.states[0].profit, ai: r.states[1].profit }]);
      setPlan((p) => ({ ...p, plant: {}, buy_animals: {}, buy_land: false }));
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const suggest = async () => {
    if (!game) return;
    const s = await api.playSuggest(game.sid);
    setPlan({ plant: s.plan.plant ?? {}, buy_animals: s.plan.buy_animals ?? {}, hands: s.plan.hands ?? 0,
      buy_land: !!s.plan.buy_land, sellAll: true });
  };

  const adv = game?.advice;
  const spend = useMemo(() => {
    if (!adv) return 0;
    let s = hireCost(plan.hands) + (plan.buy_land && adv.next_land_cost ? adv.next_land_cost : 0);
    Object.entries(plan.plant).forEach(([c, n]) => { s += (adv.crops.find((x) => x.crop === c)?.seed ?? 0) * n; });
    Object.entries(plan.buy_animals).forEach(([a, n]) => { s += (adv.animals.find((x) => x.animal === a)?.cost ?? 0) * n; });
    return s;
  }, [plan, adv]);
  const planted = Object.values(plan.plant).reduce((a, b) => a + b, 0) + Object.values(plan.buy_animals).reduce((a, b) => a + b, 0);
  const plots = adv ? adv.free_plots + (plan.buy_land ? 25 : 0) : 0;
  const handsNeed = adv ? Math.min(10, Math.ceil((adv.growing + planted) / 6)) : 0;

  if (!game) {
    return (
      <div className="play-start card">
        <div className="eyebrow">Play vs the AI</div>
        <h2 className="play-title">Can you out-farm the AI?</h2>
        <p className="muted">You run the farm on the left, the agent runs the farm on the right. You share one market: when either of you
          floods it with melons, the price falls for both. Each day you choose what to plant, buy and sell; the Foreman does the walking and watering.
          Most cash after 30 days wins.</p>
        <div className="play-cfg">
          <label>Opponent<select value={cfg.agent} onChange={(e) => setCfg({ ...cfg, agent: e.target.value })}>
            <option value="llm_multi">AI team (multi-agent)</option><option value="llm_single">AI single agent</option>
            <option value="greedy">Greedy heuristic (easy)</option></select></label>
          <label>Farm (seed)<input type="number" min={0} value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: Number(e.target.value) || 0 })} /></label>
          <label>Weather<select value={cfg.weather} onChange={(e) => setCfg({ ...cfg, weather: e.target.value })}>
            <option value="">Simulated</option>
            {seasons.map((s) => <option key={s.name} value={s.name}>Real: {s.label.split(" (")[0]} · {s.start}</option>)}</select></label>
        </div>
        <button className="primary big-btn" onClick={start} disabled={busy}>{busy ? "Setting up…" : "Start the season"}</button>
        <div className="tips">
          <div><b>Quick tips</b></div>
          <div>Melons pay most but crash the price if you plant too many.</div>
          <div>Every plant needs water daily: hire about one hand per 6 plants.</div>
          <div>Animals cost a lot but drop fertiliser worth ~$100 every day.</div>
          <div>Stuck? Press "Suggest a plan" any day.</div>
        </div>
        {err && <div className="toast">{err}</div>}
      </div>
    );
  }

  const [you, ai] = game.states;
  const lead = you.cash - ai.cash;
  const aiRecord = last ? ({ ...last.ai, before: ai, events: last.events, sales: {}, cash: ai.cash, profit: ai.profit, cost_usd: 0 } as unknown as DayRecord) : undefined;

  return (
    <div className="play">
      <div className="scoreboard card">
        <div className="sb-side"><div className="eyebrow">You</div><div className="sb-num" style={{ color: YOU }}>{money(you.cash)}</div><div className="muted small">profit {money(you.profit)}</div></div>
        <div className="sb-mid">
          <div className="eyebrow">Day {game.day + (game.done ? 1 : 0)} of 30 · {WEATHER_ICON[you.weather?.weather ?? ""] ?? ""} {titleCase(you.weather?.weather ?? "–")}</div>
          <div className={`sb-lead ${lead >= 0 ? "pos" : "neg"}`}>{game.done ? (lead >= 0 ? "You win!" : "The AI wins") : lead >= 0 ? `You lead by ${money(lead)}` : `AI leads by ${money(-lead)}`}</div>
          {(you.weather?.events ?? []).map((e, i) => <div key={i} className="muted small">{e}</div>)}
        </div>
        <div className="sb-side right"><div className="eyebrow">{game.aiLabel.replace(" (offline)", "")}</div><div className="sb-num" style={{ color: agentColor(game.aiKey) }}>{money(ai.cash)}</div><div className="muted small">profit {money(ai.profit)}</div></div>
      </div>

      <div className="arena-grid">
        <div className="card">
          <div className="card-head"><h3 style={{ color: YOU }}>Your farm</h3><span className="muted small">{you.free_plots} free plots · {you.weeds} weeds</span></div>
          <FarmGrid state={you} />
          {last && <div className="duo-plan"><div className="eyebrow">Yesterday you</div><PlanChips plan={last.you.plan} />
            {last.you.rejected.length > 0 && <ul className="rejected">{last.you.rejected.slice(0, 3).map((r, i) => <li key={i}>{r}</li>)}</ul>}</div>}
        </div>
        <div className="card">
          <div className="card-head"><h3 style={{ color: agentColor(game.aiKey) }}>The AI's farm</h3><span className="muted small">{ai.free_plots} free plots · {ai.weeds} weeds</span></div>
          <FarmGrid state={ai} />
          {last && <div className="duo-plan"><div className="eyebrow">Yesterday the AI</div><PlanChips plan={last.ai.plan} />
            <button className="link" onClick={() => setShowMind(!showMind)}>{showMind ? "Hide" : "Show"} how the AI decided →</button></div>}
        </div>
      </div>

      {showMind && aiRecord && <div className="card"><MindFeed record={aiRecord} animate={false} /></div>}

      {!game.done && adv && (
        <div className="card planner">
          <div className="card-head">
            <h3>Your plan for day {game.day}</h3>
            <div className="planner-actions">
              <button className="ghost" onClick={suggest}>Suggest a plan</button>
              <button className="primary" onClick={endDay} disabled={busy || spend > adv.cash}>{busy ? "The AI is thinking…" : "End day ▶"}</button>
            </div>
          </div>
          <div className="budget">
            <span>Spend <b>{money(spend)}</b> of {money(adv.cash)}</span>
            <span className="bar"><i style={{ width: `${Math.min(100, (100 * spend) / Math.max(1, adv.cash))}%`, background: spend > adv.cash ? "var(--neg)" : "var(--accent)" }} /></span>
            <span>Plots <b>{planted}</b> of {plots}</span>
          </div>
          <div className="planner-grid">
            <div>
              <div className="eyebrow">Plant</div>
              <table className="table compact"><tbody>{adv.crops.map((c) => (
                <tr key={c.crop} className={c.feasible ? "" : "muted"}>
                  <td>{CROP_EMOJI[c.crop]} {titleCase(c.crop)}</td>
                  <td className="muted small">${c.seed} · {c.days}d · ~{money(c.profit_per_plot)}/plot</td>
                  <td><Stepper value={plan.plant[c.crop] ?? 0} max={c.feasible ? plots : 0}
                    onChange={(v) => setPlan({ ...plan, plant: { ...plan.plant, [c.crop]: v } })} /></td>
                </tr>))}</tbody></table>
            </div>
            <div>
              <div className="eyebrow">Animals</div>
              <table className="table compact"><tbody>{adv.animals.map((a) => (
                <tr key={a.animal}><td>{CROP_EMOJI[a.animal]} {titleCase(a.animal)}</td><td className="muted small">${a.cost} · {titleCase(a.product)}</td>
                  <td><Stepper value={plan.buy_animals[a.animal] ?? 0} max={plots} onChange={(v) => setPlan({ ...plan, buy_animals: { ...plan.buy_animals, [a.animal]: v } })} /></td></tr>))}</tbody></table>
              <div className="eyebrow" style={{ marginTop: 12 }}>Workers and land</div>
              <table className="table compact"><tbody>
                <tr><td>Hands</td><td className="muted small">need ~{handsNeed} · costs {money(hireCost(plan.hands))}</td>
                  <td><Stepper value={plan.hands} max={10} onChange={(v) => setPlan({ ...plan, hands: v })} /></td></tr>
                <tr><td>Buy land</td><td className="muted small">{adv.next_land_cost ? `+25 plots for ${money(adv.next_land_cost)}` : "all land owned"}</td>
                  <td><input type="checkbox" checked={plan.buy_land} disabled={!adv.next_land_cost} onChange={(e) => setPlan({ ...plan, buy_land: e.target.checked })} /></td></tr>
                <tr><td>Sell all stock</td><td className="muted small">{Object.entries(adv.shed).filter(([k]) => !["GOOSE", "COW", "SHEEP"].includes(k)).map(([k, v]) => `${v} ${titleCase(k)}`).join(", ") || "shed empty"}</td>
                  <td><input type="checkbox" checked={plan.sellAll} onChange={(e) => setPlan({ ...plan, sellAll: e.target.checked })} /></td></tr>
              </tbody></table>
            </div>
          </div>
          {err && <div className="toast">{err}</div>}
        </div>
      )}

      {game.done && (
        <div className="card season-over big">
          <h2>{lead >= 0 ? "You beat the AI!" : "The AI won this season."}</h2>
          <p>You {money(you.profit)} · AI {money(ai.profit)}. {lead >= 0 ? "Impressive farming." : "It invests early and spreads its crops so prices hold up. Try again with that idea."}</p>
          <button className="primary" onClick={() => setGame(null)}>Play again</button>
        </div>
      )}

      <div className="card">
        <h3>The race</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={race} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="day" type="number" domain={[0, 30]} tick={{ fontSize: 11, fill: "var(--muted)" }} />
            <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} width={60} />
            <Tooltip formatter={(v: number, k: string) => [money(v), k === "you" ? "You" : "AI"]} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
            <Legend formatter={(k: string) => (k === "you" ? "You" : game.aiLabel.replace(" (offline)", ""))} wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="you" stroke={YOU} strokeWidth={2.2} dot={false} isAnimationActive={false} />
            <Line dataKey="ai" stroke={agentColor(game.aiKey)} strokeWidth={2.2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Stepper({ value, max, onChange }: { value: number; max: number; onChange: (v: number) => void }) {
  return (
    <div className="stepper">
      <button onClick={() => onChange(Math.max(0, value - 1))} disabled={value <= 0}>−</button>
      <span>{value}</span>
      <button onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}>+</button>
      <button className="five" onClick={() => onChange(Math.min(max, value + 5))} disabled={value >= max}>+5</button>
    </div>
  );
}
