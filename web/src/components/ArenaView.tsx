import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { agentColor, money } from "../constants";
import type { ArenaMatch } from "../types";
import { FarmGrid } from "./FarmGrid";
import { PlanChips } from "./PlanChips";

/** Two farmers, one market: replay a recorded head-to-head season side by side. */
export function ArenaView({ speed }: { speed: number }) {
  const [names, setNames] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [match, setMatch] = useState<ArenaMatch | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.arenaMatches().then((n) => { setNames(n); if (n.length) setName(n[0]); }).catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => {
    if (!name) return;
    api.arenaMatch(name).then((m) => { setMatch(m); setCursor(0); setPlaying(false); }).catch((e) => setErr(String(e)));
  }, [name]);

  const total = match?.days.length ?? 0;
  useEffect(() => {
    if (!playing) return;
    if (cursor >= total) { setPlaying(false); return; }
    const t = setTimeout(() => setCursor((c) => c + 1), Math.max(300, speed * 0.6));
    return () => clearTimeout(t);
  }, [playing, cursor, total, speed]);

  const race = useMemo(() => {
    if (!match) return [];
    const pts = match.days.map((d) => ({ day: d.day, p0: d.players[0].before.profit, p1: d.players[1].before.profit }));
    pts.push({ day: total, p0: match.summary.profit0, p1: match.summary.profit1 });
    return pts.slice(0, cursor + 1);
  }, [match, cursor, total]);

  if (err) return <div className="empty">Could not load arena matches ({err}). Run <code>python -m kagri.arena</code>.</div>;
  if (!match) return <div className="empty">{names.length ? "Loading match…" : "No arena match recorded yet. Run python -m kagri.arena."}</div>;

  const players = match.header.players;
  const states = [0, 1].map((i) => (cursor < total ? match.days[cursor].players[i].before : match.summary.final[i]));
  const today = cursor > 0 ? match.days[cursor - 1] : undefined;
  const ended = cursor >= total;
  const lead = states[0].cash - states[1].cash;

  return (
    <div className="arena">
      <div className="arena-head card">
        <div>
          <div className="eyebrow">Head-to-head · shared market · seed {match.header.seed}</div>
          <h2 className="arena-title">
            <span style={{ color: agentColor(players[0].key) }}>{players[0].label}</span>
            <em> vs </em>
            <span style={{ color: agentColor(players[1].key) }}>{players[1].label}</span>
          </h2>
          <p className="muted small">Both farms sell into the same market: every melon one farmer sells lowers the price for the other.</p>
        </div>
        <div className="arena-ctl">
          {names.length > 1 && (
            <select value={name} onChange={(e) => setName(e.target.value)}>
              {names.map((n) => <option key={n} value={n}>{n.replace("arena_", "").replace(/_/g, " ")}</option>)}
            </select>
          )}
          <div className="controls compact">
            <button title="Back to day 0" onClick={() => { setPlaying(false); setCursor(0); }} disabled={cursor === 0}>⏮</button>
            <button className="primary play" onClick={() => setPlaying(!playing)} disabled={ended}>{playing ? "⏸ Pause" : ended ? "Season over" : "▶ Play"}</button>
            <button title="Next day" onClick={() => { setPlaying(false); setCursor((c) => Math.min(total, c + 1)); }} disabled={ended}>▶|</button>
            <span className="muted day-label">day {cursor} of {total}</span>
          </div>
        </div>
      </div>

      <div className="arena-grid">
        {[0, 1].map((i) => (
          <div key={i} className="card">
            <div className="card-head">
              <h3 style={{ color: agentColor(players[i].key) }}>{players[i].label}</h3>
              <span className="muted small">seat {i + 1}</span>
            </div>
            <div className="duo-metrics">
              <div><div className="eyebrow">Cash</div><div className="mval">{money(states[i].cash)}</div></div>
              <div><div className="eyebrow">Profit</div><div className={`mval ${states[i].profit >= 0 ? "pos" : "neg"}`}>{money(states[i].profit)}</div></div>
              <div><div className="eyebrow">Farm</div><div className="mval">{Object.values(states[i].crops_growing).reduce((a, b) => a + b, 0)} · {Object.values(states[i].animals).reduce((a, b) => a + b, 0)}</div></div>
            </div>
            <FarmGrid state={states[i]} />
            <div className="duo-plan">
              <div className="eyebrow">Decision</div>
              {today ? <PlanChips plan={today.players[i].plan ?? undefined} /> : <span className="muted small">Press Play.</span>}
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-head">
          <h3>The race</h3>
          <span className="muted small">
            {ended ? `${lead >= 0 ? players[0].label : players[1].label} wins by ${money(Math.abs(lead))}` :
              `${lead >= 0 ? players[0].label : players[1].label} leads by ${money(Math.abs(lead))}`}
          </span>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={race} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="day" type="number" domain={[0, total]} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} />
            <YAxis tickFormatter={(v) => money(v, true)} tick={{ fontSize: 11, fill: "var(--muted)" }} width={60} />
            <Tooltip formatter={(v: number, k: string) => [money(v), k === "p0" ? players[0].label : players[1].label]}
              labelFormatter={(d) => `Day ${d}`} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }} />
            <Legend formatter={(k: string) => (k === "p0" ? players[0].label : players[1].label)} wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="p0" stroke={agentColor(players[0].key)} strokeWidth={2.2} dot={false} isAnimationActive={false} />
            <Line dataKey="p1" stroke={agentColor(players[1].key)} strokeWidth={2.2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
