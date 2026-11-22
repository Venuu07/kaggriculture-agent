import { useEffect, useState } from "react";
import { ROLE, money } from "../constants";
import type { DayRecord, Plan, TraceStep } from "../types";
import { PlanChips } from "./PlanChips";

interface Props { record?: DayRecord; animate: boolean; stepMs?: number; currency?: string }

/** The agent's reasoning for one day: thought -> tool call -> result -> ... -> action, revealed step by step. */
export function MindFeed({ record, animate, stepMs = 450, currency = "$" }: Props) {
  const steps = record?.trace ?? [];
  const [shown, setShown] = useState(animate ? 0 : steps.length);

  useEffect(() => {
    if (!animate) { setShown(steps.length); return; }
    setShown(0);
    let i = 0;
    const t = setInterval(() => { i += 1; setShown(i); if (i >= steps.length) clearInterval(t); }, stepMs);
    return () => clearInterval(t);
  }, [record, animate, steps.length, stepMs]);

  if (!record) return <div className="empty">Press ▶ Play or Step to watch the agent think.</div>;
  const thinking = shown < steps.length;

  return (
    <div className="mind">
      <div className="mind-head">
        <div>
          <div className="eyebrow">Reasoning trace</div>
          <div className="title">Day {record.day}</div>
          <div className="mind-stats">
            <span>{steps.filter((s) => s.type === "tool").length} tool calls</span>
            {record.llm_calls > 0 && <span>{record.llm_calls} LLM calls</span>}
            {record.tokens > 0 && <span>{record.tokens.toLocaleString()} tokens</span>}
            {record.latency_s > 0 && <span>{record.latency_s.toFixed(1)}s</span>}
            <span className={record.reward >= 0 ? "pos" : "neg"}>day result {record.reward >= 0 ? "+" : ""}{money(record.reward).replace("$", currency)}</span>
          </div>
        </div>
        {record.fallback && <span className="badge red">Fallback plan used</span>}
      </div>
      <ol className="feed">
        {steps.slice(0, shown).map((s, i) => <Step key={i} step={s} />)}
        {thinking && <li className="typing"><span /><span /><span /></li>}
      </ol>
      {!thinking && (
        <div className="outcome fade-in">
          <div className="eyebrow">Executed after guardrails</div>
          <PlanChips plan={record.plan as Plan} />
          {record.rejected.length > 0 && (
            <ul className="rejected">{record.rejected.map((r, i) => <li key={i}>Guardrail: {r}</li>)}</ul>
          )}
        </div>
      )}
    </div>
  );
}

function Step({ step }: { step: TraceStep }) {
  const role = ROLE[step.agent] ?? ROLE.single;
  const who = (
    <div className={`who tone-${role.tone}`}>
      <span className="mono">{role.icon}</span>
      <span>{role.name}</span>
      <span className="kind">{KIND[step.type] ?? ""}</span>
    </div>
  );
  if (step.type === "thought") {
    return <li className={`step thought fade-in tone-${role.tone}`}>{who}<p>{step.text}</p></li>;
  }
  if (step.type === "tool") {
    return (
      <li className={`step tool fade-in tone-${role.tone}`}>
        {who}
        <details>
          <summary>
            <code className="fn">{step.name}()</code>
            <code className="args">{shortJson(step.args)}</code>
            {step.ms !== undefined && <span className="ms">{step.ms} ms</span>}
          </summary>
          <pre>{JSON.stringify(step.result, null, 2)}</pre>
        </details>
        <div className="result-line">→ {resultHeadline(step)}</div>
      </li>
    );
  }
  if (step.type === "action") {
    return (
      <li className={`step action fade-in tone-${role.tone}`}>
        {who}
        <div className="action-label">{["planner", "market", "agronomist"].includes(step.agent) ? "propose(plan)" : "take_action(plan)"}</div>
        <PlanChips plan={step.plan as Plan} />
      </li>
    );
  }
  return (
    <li className={`step warn fade-in tone-red`}>
      {who}
      <p>{step.text}</p>
    </li>
  );
}

const KIND: Record<string, string> = {
  thought: "thinks", tool: "calls a tool", action: "decides", error: "error", guardrail: "guardrail", fallback: "fallback",
};

function shortJson(v: unknown): string {
  const s = JSON.stringify(v ?? {});
  return s.length > 90 ? `${s.slice(0, 90)}…` : s;
}

function resultHeadline(step: TraceStep): string {
  const r = (step.result ?? {}) as Record<string, unknown>;
  if ("error" in r) return `error: ${String(r.error)}`;
  switch (step.name) {
    case "simulate_action":
      return `net worth ${fmtSigned(r.net_worth_change)} over ${r.days} days (cash ${fmtSigned(r.cash_change)})`;
    case "plan_crop_mix":
      return `mix ${JSON.stringify(r.mix)}`;
    case "get_weather_forecast": {
      const today = (r.today as Record<string, unknown>)?.weather;
      const fc = ((r.forecast as { weather: string }[]) ?? []).map((f) => f.weather).join(", ");
      return `today ${today ?? "?"}; next: ${fc || "–"}`;
    }
    case "estimate_sale":
      return `${r.qty} ${String(r.item).toLowerCase()} → ${money(r.total as number)} (price $${r.price_now} → $${r.price_after})`;
    case "estimate_crop_profit":
      return `${r.crop}: profit ${money(r.expected_profit as number)}, avg price $${r.avg_sale_price}`;
    case "estimate_animal_profit":
      return `${r.animal}: profit ${money(r.expected_profit as number)} by season end`;
    case "get_market_prices":
      return `${Object.keys((r.prices as object) ?? {}).length} prices, ${((r.town_shops as string[]) ?? []).length} town shops`;
    default:
      return shortJson(r);
  }
}

function fmtSigned(v: unknown): string {
  const n = Number(v);
  if (Number.isNaN(n)) return "?";
  return `${n >= 0 ? "+" : "−"}${money(Math.abs(n))}`;
}
