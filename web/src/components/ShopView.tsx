import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { agentColor } from "../constants";
import type { DayRecord, ShopData, ShopDay } from "../types";
import { MindFeed } from "./MindFeed";

const EMOJI: Record<string, string> = { MILK: "🥛", BREAD: "🍞", RICE: "🍚", ICE_CREAM: "🍦", SWEETS: "🍬" };
const rs = (v: number | undefined) => (v === undefined ? "–" : `${v < 0 ? "−" : ""}₹${Math.abs(Math.round(v)).toLocaleString("en-IN")}`);

const MAPPING = [
  ["Crops that take days to grow", "Stock that arrives tomorrow", "Inventory planning, supply chains"],
  ["Melons crash when you flood the market", "Fewer buyers when you raise the price", "Retail pricing, revenue management"],
  ["Plants die if not watered", "Milk and bread expire", "Perishables: food, medicine, fashion"],
  ["Droughts, pests, price shocks", "Heatwaves, festivals, rival promotions", "Risk and demand shocks"],
  ["simulate_action on a copy of the farm", "simulate_plan on a copy of the store", "Digital twins, what-if analysis"],
  ["Guardrails: budget, labour", "Guardrails: cash, shelf space, price limits", "Safe automation"],
];

/** Same brain, new world: the identical agent core running a kirana store. */
export function ShopView({ speed }: { speed: number }) {
  const [data, setData] = useState<ShopData | null>(null);
  const [err, setErr] = useState("");
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => { api.shop().then(setData).catch((e) => setErr(String(e))); }, []);
  const days = data?.runs.agent?.days ?? [];
  const base = data?.runs.baseline?.days ?? [];
  useEffect(() => {
    if (!playing) return;
    if (cursor >= days.length) { setPlaying(false); return; }
    const t = setTimeout(() => setCursor((c) => c + 1), Math.max(350, speed * 0.6));
    return () => clearTimeout(t);
  }, [playing, cursor, days.length, speed]);

  const race = useMemo(() => {
    const pts = [{ day: 0, ai: 0, rule: 0 }];
    for (let i = 0; i < cursor && i < days.length; i++) pts.push({ day: i + 1, ai: days[i].cash - 10000, rule: (base[i]?.cash ?? 10000) - 10000 });
    return pts;
  }, [days, base, cursor]);

  const avg = (k: "agent" | "baseline", f: "profit" | "units_wasted" | "customers_lost") => {
    const r = (data?.results ?? []).filter((x) => x.agent === k);
    return r.length ? r.reduce((a, b) => a + b[f], 0) / r.length : 0;
  };

  if (err) return <div className="empty">Could not load the store ({err}). Run <code>python -m kagri.shop</code>.</div>;
  if (!data) return <div className="empty">Opening the store…</div>;

  const today: ShopDay | undefined = cursor > 0 ? days[cursor - 1] : undefined;
  const state = today ? today.before : days[0]?.before;
  const ended = cursor >= days.length;

  return (
    <div className="shop">
      <div className="paper-head">
        <div className="eyebrow">Same brain, new world</div>
        <h2>The farm was a testbed. Here the same agent runs a kirana store.</h2>
        <p className="muted">Nothing about the agent changed: the same ReAct loop (<code>kagri/agents/core.py</code>), the same habit of
          simulating plans before acting, the same guardrails. Only the tools and the simulator are new. That is why this kind
          of agent is useful wherever decisions repeat under uncertainty.</p>
      </div>

      <div className="card">
        <table className="table mapping">
          <thead><tr><th>On the farm</th><th>In the store</th><th>In the real world</th></tr></thead>
          <tbody>{MAPPING.map(([a, b, c]) => <tr key={a}><td>{a}</td><td>{b}</td><td className="muted">{c}</td></tr>)}</tbody>
        </table>
      </div>

      <div className="findings three">
        <div className="finding"><div className="f-n">AI shopkeeper · 5 seeds</div><div className="f-big" style={{ color: agentColor("llm_multi") }}>{rs(avg("agent", "profit"))}</div>
          <b>mean profit in 30 days</b><p>vs {rs(avg("baseline", "profit"))} for a fixed restock rule</p></div>
        <div className="finding"><div className="f-n">Customers turned away</div><div className="f-big">{Math.round(avg("agent", "customers_lost"))}</div>
          <b>vs {Math.round(avg("baseline", "customers_lost"))} for the fixed rule</b><p>It stocks up before heatwaves and festivals it sees in the forecast.</p></div>
        <div className="finding"><div className="f-n">Advantage</div><div className="f-big">+{Math.round(100 * (avg("agent", "profit") / Math.max(1, avg("baseline", "profit")) - 1))}%</div>
          <b>more profit, same agent core</b><p>Units thrown away: {avg("agent", "units_wasted").toFixed(0)} vs {avg("baseline", "units_wasted").toFixed(0)}.</p></div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>The store, day by day <span className="muted">seed 0</span></h3>
          <div className="controls compact">
            <button title="Back to day 0" onClick={() => { setPlaying(false); setCursor(0); }} disabled={cursor === 0}>⏮</button>
            <button className="primary play" onClick={() => setPlaying(!playing)} disabled={ended}>{playing ? "⏸ Pause" : ended ? "Month over" : "▶ Play"}</button>
            <button title="Next day" onClick={() => { setPlaying(false); setCursor((c) => Math.min(days.length, c + 1)); }} disabled={ended}>▶|</button>
            <span className="muted day-label">day {cursor} of {days.length}</span>
          </div>
        </div>
        {today && today.events.events.length > 0 && <div className="shop-events">{today.events.events.map((e, i) => <span key={i} className="event">{e}</span>)}</div>}
        {state && (
          <div className="shelves">
            {Object.entries(state.products).map(([p, info]) => {
              const sold = today?.sold[p], dem = today?.demand[p], waste = today?.wasted[p] ?? 0;
              const price = today?.plan.price?.[p] ?? info.price;
              const total = Math.max(1, info.stock);
              const fresh = info.batches.length ? info.batches.filter((b) => b.days_left > 1).reduce((a, b) => a + b.qty, 0) : info.stock;
              return (
                <div key={p} className="shelf">
                  <div className="shelf-top"><span className="shelf-em">{EMOJI[p]}</span><b>{p.replace("_", " ").toLowerCase()}</b></div>
                  <div className={`tag ${price > info.usual_price ? "up" : price < info.usual_price ? "down" : ""}`}>₹{price}<small> usual ₹{info.usual_price}</small></div>
                  <div className="stockbar" title={`${info.stock} in stock`}>
                    <i className="fresh" style={{ width: `${(100 * fresh) / Math.max(total, 120)}%` }} />
                    <i className="old" style={{ width: `${(100 * (info.stock - fresh)) / Math.max(total, 120)}%` }} />
                  </div>
                  <div className="shelf-meta">
                    <span>{info.stock} on shelf</span>
                    {today && <span>sold {sold}/{dem}{dem !== undefined && sold !== undefined && dem > sold ? <em className="neg"> · {dem - sold} turned away</em> : null}</span>}
                    {waste > 0 && <span className="neg">{waste} expired</span>}
                    {today?.plan.order?.[p] ? <span className="pos">ordered {today.plan.order[p]}</span> : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="card">
          <h3>AI shopkeeper vs fixed restock rule</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={race} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="day" type="number" domain={[0, 30]} tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <YAxis tickFormatter={(v) => `₹${Math.round(v / 1000)}k`} tick={{ fontSize: 11, fill: "var(--muted)" }} width={56} />
              <Tooltip formatter={(v: number, k: string) => [rs(v), k === "ai" ? "AI shopkeeper" : "Fixed rule"]} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
              <Legend formatter={(k: string) => (k === "ai" ? "AI shopkeeper" : "Fixed restock rule")} wrapperStyle={{ fontSize: 12 }} />
              <Line dataKey="ai" stroke={agentColor("llm_multi")} strokeWidth={2.4} dot={false} isAnimationActive={false} />
              <Line dataKey="rule" stroke={agentColor("greedy")} strokeWidth={2.4} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
      </div>
      <div className="card">
          <MindFeed record={today ? ({ ...today, cost_usd: 0, profit: 0, sales: {} } as unknown as DayRecord) : undefined} animate={playing} stepMs={150} currency="₹" />
      </div>
    </div>
  );
}
