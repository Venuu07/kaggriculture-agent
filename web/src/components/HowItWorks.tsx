const LOOP = [
  { title: "Observe", text: "Farm state, weather forecast, market prices, last days (short-term memory)." },
  { title: "Think", text: "The LLM writes a thought and chooses ONE tool to call (ReAct)." },
  { title: "Act with tools", text: "Estimate crop profit, check a sale's price impact, simulate a plan on a copy of the farm." },
  { title: "Repeat", text: "Read the tool result, think again. Max 4 tool calls per day (guardrail)." },
  { title: "Commit", text: "take_action(plan) → validated → executed by the Foreman for 24 turns." },
  { title: "Reflect", text: "After the season, write lessons that are fed into the next season's prompt." },
];

const TOOLS = [
  ["get_farm_state", "cash, plots, animals, shed stock"],
  ["get_weather_forecast", "today + noisy 3-day forecast"],
  ["get_market_prices", "prices, history, town demand"],
  ["estimate_crop_profit", "profit incl. our own price impact"],
  ["estimate_animal_profit", "payback until season end"],
  ["estimate_sale", "walks the official price curve"],
  ["plan_crop_mix", "glut-aware mix per plot-day"],
  ["simulate_action", "look-ahead on a copy of the env"],
];

/** Architecture and agent design, explained for the panel. */
export function HowItWorks() {
  return (
    <div className="how">
      <div className="card">
        <h3>Architecture</h3>
        <div className="arch">
          <div className="layer ui"><b>React dashboard</b><span>live farm · agent's mind · results</span></div>
          <div className="arrow">⇅ REST API (FastAPI)</div>
          <div className="layer-row">
            <div className="layer agent">
              <b>Agentic AI (kagri/agents)</b>
              <div className="sub-row">
                <span className="pill">Planner</span><span className="pill">Market Analyst</span>
                <span className="pill">Agronomist</span><span className="pill">Manager</span>
              </div>
              <div className="sub-row">
                <span className="pill soft">ReAct loop</span><span className="pill soft">8 tools</span>
                <span className="pill soft">short-term memory</span><span className="pill soft">long-term lessons</span>
              </div>
            </div>
            <div className="side">
              <div className="layer llm"><b>LLM provider</b><span>Gemini · Groq · OpenAI · Claude</span><span className="muted">or offline reasoner (no key)</span></div>
              <div className="layer base"><b>Baselines</b><span>Random · Greedy heuristic</span></div>
            </div>
          </div>
          <div className="arrow">↓ daily plan (JSON)</div>
          <div className="layer guard"><b>Guardrails</b><span>schema + budget + feed reserve + timing checks; invalid parts rejected with a reason</span></div>
          <div className="arrow">↓ validated plan</div>
          <div className="layer foreman"><b>Foreman (executor)</b><span>walks farmer + hired hands; plants, waters, harvests, feeds, sells — 24 turns/day</span></div>
          <div className="arrow">↓ per-turn commands</div>
          <div className="layer engine"><b>Official Kaggriculture engine</b><span>vendored from kaggle-environments · + our weather & events layer</span></div>
        </div>
      </div>

      <div className="card">
        <h3>The agent loop, once per day</h3>
        <div className="loop">
          {LOOP.map((s, i) => (
            <div key={s.title} className="loop-step" style={{ animationDelay: `${i * 0.08}s` }}>
              <div className="n">{String(i + 1).padStart(2, "0")}</div><b>{s.title}</b><p>{s.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Tools the agent can call</h3>
          <table className="table"><tbody>{TOOLS.map(([n, d]) => <tr key={n}><td><code>{n}</code></td><td className="muted">{d}</td></tr>)}</tbody></table>
        </div>
        <div className="card">
          <h3>Why this is agentic, not just ML</h3>
          <ul className="why">
            <li><b>Goal-directed:</b> one objective, maximise cash by day 30, pursued over 30 decisions.</li>
            <li><b>Uses tools:</b> it gathers information and tests "what if" before acting.</li>
            <li><b>Plans ahead:</b> simulate_action shows delayed payoffs (melons take 10 days, animals pay back slowly).</li>
            <li><b>Remembers & reflects:</b> season log in the prompt, lessons across seasons.</li>
            <li><b>Collaborates:</b> specialists propose, the Manager resolves conflicts (e.g. not enough hands for new land).</li>
            <li><b>Safe:</b> every plan is validated; a bad LLM reply falls back to a safe plan.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
