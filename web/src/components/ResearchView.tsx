import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { agentColor, money } from "../constants";
import type { MemoryFile, RealRun, Research } from "../types";

const num = (v: unknown) => (typeof v === "number" ? v : v === "" || v === null || v === undefined ? NaN : Number(v));
const tip = { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 };

/** The research questions, the experiments that answer them, and what we found. */
export function ResearchView() {
  const [data, setData] = useState<Research | null>(null);
  const [lessons, setLessons] = useState<MemoryFile | null>(null);
  const [real, setReal] = useState<RealRun[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.research().then(setData).catch((e) => setErr(String(e)));
    api.memory().then((m) => setLessons(m.find((x) => x.name === "verified") ?? null)).catch(() => undefined);
    api.realLlm().then(setReal).catch(() => setReal([]));
  }, []);

  const abl = useMemo(() => (data?.ablation ?? []).filter((r) => r.variant !== "Full system").map((r) => ({
    name: String(r.variant), delta: num(r.mean_delta), pct: num(r.delta_pct), worse: num(r.seeds_worse),
  })).sort((a, b) => a.delta - b.delta), [data]);
  const full = num(data?.ablation.find((r) => r.variant === "Full system")?.mean_profit);
  const refl = (data?.reflection ?? []).map((r) => ({ season: num(r.season), profit: num(r.test_profit), adopted: String(r.adopted) }));
  const arena = (data?.arena ?? []).map((r) => ({
    agent: String(r.agent), label: String(r.label), rating: num(r.rating), win: num(r.win_rate),
    starter: num(r.vs_starter), itself: num(r.vs_itself), cost: num(r.competition_cost_pct),
  }));

  if (err) return <div className="empty">Could not load research results ({err}).</div>;
  if (!data) return <div className="empty">Loading research…</div>;

  const top = abl[0];
  const learnGain = refl.length > 1 ? (refl[refl.length - 1].profit / refl[0].profit - 1) * 100 : 0;
  const smart = arena.filter((a) => a.agent.startsWith("llm") && !Number.isNaN(a.cost));
  const compCost = smart.length ? smart.reduce((s, a) => s + a.cost, 0) / smart.length : 0;
  const h2h = arena.length ? arena[0] : undefined;

  return (
    <div className="research">
      <div className="paper-head">
        <div className="eyebrow">Research findings</div>
        <h2>What makes an AI farmer profitable, and what does competition cost?</h2>
        <p className="muted">Four experiments on the official Kaggriculture rules, all reproducible with one command each.
          LLM-agent numbers use the offline reasoner (same ReAct loop and tools, no API key).</p>
      </div>

      <div className="findings">
        {top && <Finding n="01" big={`${top.pct.toFixed(0)}%`} title={`${top.name.replace("No ", "").replace(/^./, (c) => c.toUpperCase())} matters most`}
          text={`Removing ${top.name.replace("No ", "").toLowerCase()} costs ${money(-top.delta, true)} per season. Simulating plans before acting is the agent's single most valuable skill.`} />}
        {refl.length > 1 && <Finding n="02" big={`+${learnGain.toFixed(0)}%`} title="Verified reflection learns"
          text="Starting as a novice, the agent tests its own lessons in simulation and keeps only those that win on unseen seasons." />}
        {smart.length > 0 && <Finding n="03" big={`${compCost.toFixed(0)}%`} title="The price of competition"
          text="A smart farmer facing a copy of itself on the same market loses almost half its profit: both chase the same crops and crash prices." />}
        {h2h && <Finding n="04" big={`${h2h.win.toFixed(0)}%`} title={`${h2h.label} wins head-to-head`}
          text="Higher average profit is not the same as winning: the multi-agent team's look-ahead assumes a naive rival, so it over-invests against a smart one." />}
      </div>

      <section className="card rq">
        <div className="rq-head"><span className="rq-n">RQ1</span><div><h3>Which component earns the money?</h3>
          <p className="muted small">Ablation: switch off one component at a time, 5 seeds each. Full system: {money(full)} mean profit. <code>python -m kagri.ablation</code></p></div></div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={abl} layout="vertical" margin={{ top: 4, right: 70, left: 10, bottom: 0 }}>
            <CartesianGrid horizontal={false} stroke="var(--grid)" />
            <XAxis type="number" tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} />
            <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 12, fill: "var(--ink-2)" }} tickLine={false} />
            <Tooltip formatter={(v: number) => money(v)} contentStyle={tip} cursor={{ fill: "var(--hover)" }} />
            <Bar dataKey="delta" fill="var(--terracotta)" radius={[4, 0, 0, 4]}>
              <LabelList dataKey="pct" position="left" formatter={(v: number) => `${v.toFixed(0)}%`} style={{ fill: "var(--ink)", fontSize: 12 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </section>

      <div className="grid2">
        <section className="card rq">
          <div className="rq-head"><span className="rq-n">RQ2</span><div><h3>Can the agent learn from its own seasons?</h3>
            <p className="muted small">Lessons are hypotheses; each is simulated on 4 validation seasons and kept only if it wins. Scored on 4 held-out seasons. <code>python -m kagri.reflection</code></p></div></div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={refl} margin={{ top: 20, right: 20, left: 8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="season" tickFormatter={(s) => (s === 0 ? "novice" : `season ${s}`)} tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} domain={["dataMin - 5000", "dataMax + 5000"]} width={60} />
              <Tooltip formatter={(v: number) => money(v)} labelFormatter={(s) => `After season ${s}`} contentStyle={tip} />
              <Line dataKey="profit" stroke={agentColor("llm_multi")} strokeWidth={2.4} dot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
          {lessons && lessons.entries.length > 0 && (
            <div className="lessons">
              <div className="eyebrow">Lessons adopted</div>
              <ul>{lessons.entries.flatMap((e) => e.lessons.map((l, i) => <li key={`${e.episode}-${i}`}>Season {e.episode}: {l}</li>))}</ul>
            </div>
          )}
        </section>

        <section className="card rq">
          <div className="rq-head"><span className="rq-n">RQ3</span><div><h3>What does a rival on the same market cost?</h3>
            <p className="muted small">Each agent vs Kaggle's starter bot, and vs a copy of itself. 3 seeds, both seats. <code>python -m kagri.arena</code></p></div></div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={arena.filter((a) => !Number.isNaN(a.itself))} margin={{ top: 22, right: 8, left: 8, bottom: 0 }} barGap={3}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="label" tickFormatter={(l: string) => l.replace(" heuristic", "").replace("-agent", "")} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} />
              <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} width={60} />
              <Tooltip formatter={(v: number, k: string) => [money(v), k === "starter" ? "vs Kaggle starter bot" : "vs a copy of itself"]} contentStyle={tip} cursor={{ fill: "var(--hover)" }} />
              <Bar dataKey="starter" radius={[4, 4, 0, 0]}>{arena.filter((a) => !Number.isNaN(a.itself)).map((a) => <Cell key={a.agent} fill={agentColor(a.agent)} />)}</Bar>
              <Bar dataKey="itself" radius={[4, 4, 0, 0]} fillOpacity={0.4}>
                {arena.filter((a) => !Number.isNaN(a.itself)).map((a) => <Cell key={a.agent} fill={agentColor(a.agent)} />)}
                <LabelList dataKey="cost" position="top" formatter={(v: number) => `${v.toFixed(0)}%`} style={{ fill: "var(--ink)", fontSize: 11 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="muted small">Solid: vs the starter bot. Faded: vs a copy of itself (label = profit change).</p>
        </section>
      </div>

      {real.some((r) => r.real) && (
        <section className="card rq">
          <div className="rq-head"><span className="rq-n">RQ5</span><div><h3>How does a real LLM behave?</h3>
            <p className="muted small">Real Gemini seasons on seed 0, next to the offline reasoner and the baselines on the same seed.
              Record more with <code>python -m kagri.record --provider gemini</code>.</p></div></div>
          <table className="table">
            <thead><tr><th>Agent</th><th>Profit</th><th /><th>LLM calls</th><th>Days using tools</th><th>Simulations</th><th>Guardrail fixes</th><th>Cost</th></tr></thead>
            <tbody>{real.map((r) => {
              const max = Math.max(...real.map((x) => x.profit || 0));
              return (
                <tr key={r.name} className={r.real ? "real-row" : ""}>
                  <td><i className="dot" style={{ background: agentColor(r.agent) }} />{r.label}{r.real && <span className="badge real-badge">real LLM</span>}</td>
                  <td className="serif-num">{money(r.profit)}</td>
                  <td className="bar-cell"><span style={{ width: `${Math.max(2, (100 * (r.profit || 0)) / max)}%`, background: agentColor(r.agent) }} /></td>
                  <td>{r.real ? r.llm_calls : "–"}</td>
                  <td>{r.agent.startsWith("llm") ? `${r.days_with_tools} / 30` : "–"}</td>
                  <td>{r.agent.startsWith("llm") ? r.simulations : "–"}</td>
                  <td>{r.agent.startsWith("llm") ? r.guardrails : "–"}</td>
                  <td>{r.real ? `$${r.cost_usd.toFixed(3)}` : "$0"}</td>
                </tr>
              );
            })}</tbody>
          </table>
          <p className="muted small">The real model rarely reached for its tools and never simulated a plan on its own: it behaves like the
            "no look-ahead" ablation. The test-before-act policy makes it simulate before every decision.</p>
        </section>
      )}

      <section className="card rq">
        <div className="rq-head"><span className="rq-n">RQ4</span><div><h3>Who wins when they meet?</h3>
          <p className="muted small">Round-robin tournament rated with Bradley-Terry, the rating method Kaggriculture used. Only wins count, not margins.</p></div></div>
        <table className="table">
          <thead><tr><th>#</th><th>Agent</th><th>Rating</th><th>Win rate</th><th>Mean profit</th><th>vs starter bot</th><th>vs itself</th></tr></thead>
          <tbody>{arena.map((a, i) => (
            <tr key={a.agent}>
              <td className="muted">{i + 1}</td>
              <td><i className="dot" style={{ background: a.agent === "kaggle_starter" ? "var(--muted)" : agentColor(a.agent) }} />{a.label}</td>
              <td className="serif-num">{a.rating.toFixed(0)}</td><td>{a.win.toFixed(0)}%</td>
              <td>{money(arena.length ? (data.arena[i].mean_profit as number) : 0)}</td>
              <td>{Number.isNaN(a.starter) ? "–" : money(a.starter)}</td><td>{Number.isNaN(a.itself) ? "–" : money(a.itself)}</td>
            </tr>
          ))}</tbody>
        </table>
      </section>
    </div>
  );
}

function Finding({ n, big, title, text }: { n: string; big: string; title: string; text: string }) {
  return (
    <div className="finding">
      <div className="f-n">{n}</div>
      <div className="f-big">{big}</div>
      <b>{title}</b>
      <p>{text}</p>
    </div>
  );
}
