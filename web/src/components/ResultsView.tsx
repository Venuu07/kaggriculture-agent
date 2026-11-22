import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ErrorBar, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { agentColor, money, shortLabel } from "../constants";
import type { MemoryFile, Results, Row } from "../types";

const num = (v: unknown) => (typeof v === "number" ? v : Number(v));

export function ResultsView() {
  const [res, setRes] = useState<Results | null>(null);
  const [mem, setMem] = useState<MemoryFile[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.results().then(setRes).catch((e) => setErr(String(e)));
    api.memory().then(setMem).catch(() => setMem([]));
  }, []);

  const bars = useMemo(() => (res?.summary ?? []).map((r) => ({
    agent: String(r.agent), label: String(r.label), mean: num(r.mean_profit), std: num(r.std_profit) || 0,
    min: num(r.min_profit), max: num(r.max_profit), tokens: num(r.mean_tokens), latency: num(r.latency_per_decision_s),
    tools: num(r.tool_calls),
  })), [res]);

  const curves = useMemo(() => {
    const by: Record<string, number[][]> = {};
    (res?.rows ?? []).forEach((r: Row) => {
      const k = String(r.agent);
      (by[k] ??= []).push((r.daily_cash as number[]) ?? []);
    });
    const days = Math.max(0, ...Object.values(by).map((c) => c[0]?.length ?? 0));
    return Array.from({ length: days }, (_, d) => {
      const pt: Record<string, number> = { day: d };
      Object.entries(by).forEach(([k, cs]) => { pt[k] = cs.reduce((a, c) => a + (c[d] ?? 0), 0) / cs.length - 3000; });
      return pt;
    });
  }, [res]);

  const refl = useMemo(() => {
    const m: Record<number, Record<string, number[]>> = {};
    (res?.reflection ?? []).forEach((r) => {
      const ep = num(r.episode);
      ((m[ep] ??= {})[String(r.agent)] ??= []).push(num(r.profit));
    });
    return Object.entries(m).map(([ep, ags]) => {
      const pt: Record<string, number> = { episode: Number(ep) };
      Object.entries(ags).forEach(([k, v]) => { pt[k] = v.reduce((a, b) => a + b, 0) / v.length; });
      return pt;
    });
  }, [res]);

  if (err) return <div className="empty">Could not load results: {err}. Run <code>python -m kagri.evaluate</code>.</div>;
  if (!res) return <div className="empty">Loading results…</div>;
  if (!bars.length) return <div className="empty">No results yet. Run <code>python -m kagri.evaluate</code>.</div>;

  const labelOf = (k: string) => bars.find((b) => b.agent === k)?.label ?? k;
  const greedy = bars.find((b) => b.agent === "greedy")?.mean ?? 0;
  const best = [...bars].sort((a, b) => b.mean - a.mean)[0];
  const seeds = new Set((res.rows ?? []).map((r) => r.seed)).size;
  const offline = bars.some((b) => b.label.includes("offline"));

  return (
    <div className="results">
      <div className="hero-row">
        <div className="hero card">
          <div className="eyebrow">Best agent</div>
          <div className="hero-num" style={{ color: agentColor(best.agent) }}>{money(best.mean, true)}</div>
          <div className="muted">{best.label} · mean profit over {seeds} seeds</div>
        </div>
        <div className="hero card">
          <div className="eyebrow">vs Greedy baseline</div>
          <div className="hero-num">{greedy ? `${(best.mean / greedy).toFixed(1)}×` : "–"}</div>
          <div className="muted">more profit than the classic heuristic</div>
        </div>
        <div className="hero card">
          <div className="eyebrow">Episodes evaluated</div>
          <div className="hero-num">{(res.rows ?? []).length + (res.reflection ?? []).length}</div>
          <div className="muted">full 30-day seasons on the official rules</div>
        </div>
      </div>
      {offline && (
        <div className="note">Note: LLM agents in these results ran with the <b>offline reasoner</b> (deterministic, no API key) through the same ReAct loop and tools. Record a real-LLM evaluation with <code>python -m kagri.evaluate --provider gemini --seeds 1</code>.</div>
      )}

      <div className="grid2">
        <div className="card">
          <h3>Profit per agent <span className="muted">mean ± std</span></h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={bars} margin={{ top: 12, right: 8, left: 8, bottom: 0 }} barCategoryGap="28%">
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="label" tickFormatter={shortLabel} tick={{ fontSize: 12, fill: "var(--muted)" }} interval={0} tickLine={false} />
              <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip formatter={(v: number) => money(v)} contentStyle={tooltipStyle} cursor={{ fill: "var(--hover)" }} />
              <Bar dataKey="mean" radius={[4, 4, 0, 0]} isAnimationActive>
                {bars.map((b) => <Cell key={b.agent} fill={agentColor(b.agent)} />)}
                <ErrorBar dataKey="std" stroke="var(--muted)" width={6} />
                <LabelList dataKey="mean" position="insideTop" offset={10} formatter={(v: number) => (v > 0.2 * best.mean ? money(v, true) : "")} style={{ fill: "#fff", fontSize: 12, fontWeight: 600 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h3>Profit over the season <span className="muted">mean over seeds</span></h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={curves} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "var(--muted)" }} ticks={[0, 5, 10, 15, 20, 25, 29]} tickLine={false} />
              <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip formatter={(v: number, k: string) => [money(v), shortLabel(labelOf(k))]} labelFormatter={(d) => `Day ${d}`} contentStyle={tooltipStyle} />
              <Legend formatter={(k: string) => shortLabel(labelOf(k))} wrapperStyle={{ fontSize: 12 }} />
              {bars.map((b) => <Line key={b.agent} dataKey={b.agent} stroke={agentColor(b.agent)} strokeWidth={2} dot={false} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Reflection: profit across seasons <span className="muted">lessons carried forward</span></h3>
          {refl.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={refl} margin={{ top: 16, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="episode" tickFormatter={(e) => `Season ${e}`} tick={{ fontSize: 11, fill: "var(--muted)" }} />
                <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} domain={["auto", "auto"]} />
                <Tooltip formatter={(v: number, k: string) => [money(v), shortLabel(labelOf(k))]} contentStyle={tooltipStyle} />
                <Legend formatter={(k: string) => shortLabel(labelOf(k))} wrapperStyle={{ fontSize: 12 }} />
                {Object.keys(refl[0]).filter((k) => k !== "episode").map((k) => (
                  <Line key={k} dataKey={k} stroke={agentColor(k)} strokeWidth={2} dot={{ r: 5 }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : <div className="empty">No reflection experiment yet.</div>}
          <p className="muted small">Same farm (seed) replayed with lessons from the previous seasons in the prompt. With the offline reasoner the lessons did not change profit; measuring the effect on a real LLM needs a real-LLM run.</p>
        </div>
        <div className="card">
          <h3>Lessons learned <span className="muted">long-term memory</span></h3>
          {mem.length ? mem.map((m) => (
            <div key={m.name} className="lessons">
              <div className="eyebrow">{m.name.replace("_", " · ")}</div>
              <ul>{Array.from(new Set(m.entries.flatMap((e) => e.lessons))).slice(0, 6).map((l, i) => <li key={i}>{l}</li>)}</ul>
            </div>
          )) : <div className="empty">No lessons stored yet.</div>}
        </div>
      </div>

      <div className="card">
        <h3>Numbers</h3>
        <table className="table">
          <thead><tr><th>Agent</th><th>Mean profit</th><th>Std</th><th>Min</th><th>Max</th><th>Tool calls / season</th><th>Tokens / season</th><th>s / decision</th></tr></thead>
          <tbody>{bars.map((b) => (
            <tr key={b.agent}>
              <td><i className="dot" style={{ background: agentColor(b.agent) }} />{b.label}</td>
              <td>{money(b.mean)}</td><td>{money(b.std)}</td><td>{money(b.min)}</td><td>{money(b.max)}</td>
              <td>{Math.round(b.tools)}</td><td>{Math.round(b.tokens).toLocaleString()}</td><td>{b.latency.toFixed(2)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>

    </div>
  );
}

const tooltipStyle = { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 };
