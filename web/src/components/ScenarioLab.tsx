import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { agentColor, money } from "../constants";
import type { ScenarioInfo, ScenarioResult } from "../types";
import { PlanChips } from "./PlanChips";

const LABEL: Record<string, string> = { llm_multi: "AI team", greedy: "Greedy" };

/** Scenario Lab: pick a crisis, watch the AI and Greedy live through it. */
export function ScenarioLab() {
  const [list, setList] = useState<ScenarioInfo[]>([]);
  const [cached, setCached] = useState<Record<string, ScenarioResult>>({});
  const [pick, setPick] = useState("melon_crash");
  const [seed, setSeed] = useState(0);
  const [res, setRes] = useState<ScenarioResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState(30);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.scenarios().then((r) => { setList(r.scenarios); setCached(r.results); }).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    const hit = seed === 0 ? cached[pick] : undefined;
    if (hit) { setRes(hit); animate(); return; }
    if (!list.length) return;
    setBusy(true); setErr("");
    api.scenarioRun(pick, seed).then((r) => { setRes(r); animate(); }).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  }, [pick, seed, cached, list.length]);

  const animate = () => {
    setShown(0);
    let d = 0;
    const t = setInterval(() => { d += 1; setShown(d); if (d >= 30) clearInterval(t); }, 70);
  };

  const data = useMemo(() => {
    if (!res) return [];
    return Array.from({ length: 31 }, (_, d) => {
      const pt: Record<string, number | null> = { day: d };
      res.runs.forEach((r) => { pt[r.agent] = d === 0 ? 0 : d <= shown ? r.daily_profit[d - 1] : null; });
      return pt;
    });
  }, [res, shown]);

  const bands = useMemo(() => {
    const out: [number, number][] = [];
    (res?.event_days ?? []).forEach((d) => {
      const last = out[out.length - 1];
      if (last && last[1] === d) last[1] = d + 1; else out.push([d, d + 1]);
    });
    return out;
  }, [res]);

  const ai = res?.runs.find((r) => r.agent === "llm_multi");
  const gr = res?.runs.find((r) => r.agent === "greedy");

  return (
    <div className="lab">
      <div className="paper-head">
        <div className="eyebrow">Scenario Lab</div>
        <h2>Throw a crisis at the farm. Does the AI hold up?</h2>
        <p className="muted">Each scenario is a controlled experiment: scripted weather, pests and market shocks, no random events.
          Both agents also play a calm season on the same farm, so we can measure what the crisis cost each of them.</p>
      </div>

      <div className="scen-cards">
        {list.map((s) => (
          <button key={s.id} className={`scen ${pick === s.id ? "on" : ""}`} onClick={() => setPick(s.id)}>
            <b>{s.title}</b><span>{s.blurb}</span>
          </button>
        ))}
      </div>

      {err && <div className="toast">{err}</div>}
      {res && ai && gr && (
        <>
          <div className="findings three">
            <div className="finding"><div className="f-n">AI team</div><div className="f-big" style={{ color: agentColor("llm_multi") }}>{money(ai.profit, true)}</div>
              <b>{ai.resilience_pct}% of its calm-season profit</b><p>Calm season on this farm: {money(ai.calm_profit, true)}</p></div>
            <div className="finding"><div className="f-n">Greedy</div><div className="f-big" style={{ color: agentColor("greedy") }}>{money(gr.profit, true)}</div>
              <b>{gr.resilience_pct}% of its calm-season profit</b><p>Calm season on this farm: {money(gr.calm_profit, true)}</p></div>
            <div className="finding"><div className="f-n">Advantage</div><div className="f-big">{money(ai.profit - gr.profit, true)}</div>
              <b>more profit for the AI in this crisis</b><p>{ai.profit - gr.profit > ai.calm_profit - gr.calm_profit ? "The gap widens under stress." : "The AI risks more (more crops, more animals), so a crisis can cost it more in absolute terms."}</p></div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3>{res.title} <span className="muted">shaded = crisis days</span></h3>
              <div className="lab-ctl">
                <label className="muted small">Farm (seed) <input type="number" min={0} value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)} /></label>
                <button className="ghost" onClick={animate}>Replay</button>
              </div>
            </div>
            {busy ? <div className="empty">Running the season for both agents…</div> : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={data} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  {bands.map(([a, b]) => <ReferenceArea key={a} x1={a} x2={b} fill="var(--terracotta)" fillOpacity={0.12} strokeOpacity={0} />)}
                  <XAxis dataKey="day" type="number" domain={[0, 30]} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} />
                  <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} width={60} />
                  <Tooltip formatter={(v: number, k: string) => [money(v), LABEL[k] ?? k]} labelFormatter={(d) => `Day ${d}`} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
                  <Legend formatter={(k: string) => LABEL[k] ?? k} wrapperStyle={{ fontSize: 12 }} />
                  {res.runs.map((r) => <Line key={r.agent} dataKey={r.agent} stroke={agentColor(r.agent)} strokeWidth={2.4} dot={false} isAnimationActive={false} connectNulls={false} />)}
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="card">
            <h3>How the AI reacted <span className="muted">its own reasoning on crisis days</span></h3>
            <ol className="reactions">
              {ai.notes.filter((n) => n.events.length).slice(0, 8).map((n) => (
                <li key={n.day}>
                  <div className="r-day">Day {n.day}</div>
                  <div>
                    {n.events.map((e, i) => <div key={i} className="event">{e}</div>)}
                    {n.thought && <p className="r-thought">{n.thought}</p>}
                    <PlanChips plan={n.plan} />
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </>
      )}
    </div>
  );
}
