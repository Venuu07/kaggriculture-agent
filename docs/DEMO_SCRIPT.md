# Demo script (7-10 minutes)

The demo runs in the React dashboard served by one command:

```bash
python -m kagri.serve
```

It opens `http://localhost:8000`. Replay mode needs no internet and no API key.

---

## Pre-demo checklist (do this 30 minutes before)

On the Windows laptop, in Git Bash or PowerShell, from the project folder:

```bash
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

```bash
pip install -r requirements.txt
```

```bash
pytest -q
```

Expect `14 passed`.

```bash
python -m kagri.serve
```

Then:

1. Open `http://localhost:8000` in Chrome and check all four tabs load.
2. In the sidebar, select the run "LLM multi-agent (offline) · seed 0" and press Play for a few days. Then press the reset button (the first control) so you start the real demo from day 0.
3. Set the speed slider to about 2 seconds per day.
4. If you have a Gemini key in `.env`, test Live mode once (see segment 4). If it fails, you will use Plan B.
5. Close other apps, turn off notifications, set the display to "duplicate" on the projector and zoom the browser to 90-100% so the whole farm fits.
6. Keep `results/` open in a file explorer window as a backup for the charts.
7. Keep the terminal running `python -m kagri.serve` minimised. Do not close it.

---

## 0:00 - 1:00 · The problem

Open the **How it works** tab.

Say:
- "Kaggriculture is a Kaggle simulation competition. You run a farm for a 30-day season and the player with the most cash at the end wins."
- "It is hard because of delayed rewards (melons take 10 days), a market that crashes when you sell too much, and limited labour."
- "Our goal: an agentic AI that plans like a farm manager, using tools and memory, on the official game rules."

Point at the architecture diagram, top to bottom: dashboard, agent (Planner, Market Analyst, Agronomist, Manager), guardrails, Foreman, official engine.

Say: "The AI makes one economic decision per day. A deterministic Foreman carries it out turn by turn on the official engine."

## 1:00 - 3:30 · Watch the farm (replay)

Click the **Live farm** tab. In the sidebar, confirm **Replay** mode and the run "LLM multi-agent (offline) · seed 0".

Point at the badges under the title: agent, seed, REPLAY, "offline reasoner · no LLM".

Say: "This is a recorded season. To be transparent: these runs use our offline reasoner, a deterministic stand-in that speaks the same tool protocol as the LLM, so the demo works without internet."

Press **Play**.

While it plays, point at:
- The metrics row: day, cash, profit, today's change, lead over the opponent bot.
- The farm grid: sprouts grow, ripe tiles glow amber, cows appear on pastures, the second quadrant unlocks when land is bought.
- The weather card: heavy rain animation, droughts, the 3-day forecast.
- "Profit so far" chart: flat at first (investing), then a jump around day 10-11 when the first melons are sold.

Pause around **day 12-14**. Say: "Notice it did not plant only melons. It mixes strawberries and wheat, and it bought cows, because every animal also drops a fertiliser worth about $100 a day."

## 3:30 - 6:00 · Agent's mind (the wow moment)

Click **Agent's mind**. Use the Season log on the right to pick a busy day. Day 13 in this run is a good one: three Planner simulations, a Market Analyst sale check, a weather-based Agronomist plan, and a Manager approval.

Walk through it top to bottom:
1. **Planner thinks**, calls `plan_crop_mix`, then calls `simulate_action` three times: "expand", "no land", "crops only". Read the net-worth results aloud.
2. "It chose 'crops only' because the simulation showed it was worth more over the next 8 days. That is planning with a tool, not guessing."
3. **Market Analyst** checks prices, asks `estimate_sale` how far selling all melons would push the price, and holds some back.
4. **Agronomist** reads the forecast and sets fertiliser and the number of hands.
5. **Manager** merges the proposals, simulates the merged plan and approves it. If you find a day whose Manager thought says "Conflict: ... raising to N hands", show it: "This is the coordination step. The Agronomist didn't know the Planner was buying land, so the Manager fixed the labour."
6. At the bottom: "Executed by the Foreman (after guardrails)". Point out that any rejected part would be listed here with a reason.

Press Play again from here to show thoughts appearing one by one.

## 6:00 - 7:30 · Compare with the baseline

In the sidebar, switch the recorded run to **Greedy heuristic · seed 0**, go to **Live farm** and press Play for a few days.

Say: "Greedy plants the highest-margin crop everywhere, which is melon. When 150 melons hit the market, the price collapses. It ends this season near $30k, while the multi-agent made about $98k on the same seed."

Click **Results**.

Say:
- "Over 5 seeds: Random $11k, Greedy $30k, our single agent $79k, multi-agent $89k, about 3 times Greedy."
- "The multi-agent beat Greedy on every seed."
- Point at "Profit over the season": "The agents invest early, so they look worse until day 10, then pull away."
- Reflection chart: "Honestly, reflection produced lessons but no measurable gain with the offline reasoner. Measuring it with a real LLM is our next step."

## 7:30 - 9:00 · Research: Arena and findings

Open the **Arena** tab and press Play (speed about 1 second per day).

Say:
- "Here two farmers share one market: our multi-agent team on the left, Greedy on the right.
  Every melon one sells lowers the price for the other."
- Around day 12: "Greedy jumps far ahead when its melons ripen, almost $20k up. Our agent looks
  like it is losing, because it has spent its cash on animals, land and strawberries."
- Days 23-29: "Now the investments pay off. Our agent overtakes on day 28 and wins
  $48.9k to $36.4k. That is delayed reward, which a greedy strategy cannot see."

Open the **Research** tab and walk through the four numbers at the top:
- "Look-ahead is worth 29% of profit: we proved it by switching it off."
- "Verified reflection: the agent tests its own lessons before trusting them. A novice gains 27% on unseen seasons."
- "Competition costs about 45%: two smart farmers crash each other's prices."
- "Our surprise result: the single agent wins head-to-head against the higher-earning team, because
  the team's simulator assumes a weak rival. Planning with the wrong opponent model is worse than planning less."

## 9:00 - 9:30 · Live mode (optional, if time allows)

In the sidebar click **Live**. Choose **LLM multi-agent**. For the provider, pick **Gemini** if your key works, otherwise the **Offline reasoner (no key)**. Seed 1, events on. Click **Start season**.

Press the step button (the "next day" control) two or three times, then open **Agent's mind**.

Say: "This is running now, not a recording. With Gemini, each day takes several seconds because the agent makes real model calls. You can see the token count and latency on top of the trace."

If you see the notice "GEMINI_API_KEY missing ... switched to the offline reasoner", say: "Without a key it switches safely to the offline reasoner. The demo never crashes."

## 9:30 - 10:30 · Wrap up

Toggle **Dark theme** once if you want a visual finish, then go back to **How it works**.

Say:
- "What makes it agentic: a goal, tools, look-ahead simulation, memory, multi-agent coordination, and guardrails on every action."
- "Limitations: real-LLM evaluation still to be done at scale, and the opponent is a simple bot."
- "Future work: real-LLM runs, an RL baseline, and packaging it as a Kaggle submission."

---

## Plan B (internet or API key fails)

Nothing in the main flow needs the internet.

1. Use **Replay** mode only. All recorded runs live in `runs/` and load from disk.
2. For live mode, choose the **Offline reasoner (no key)** provider. It runs the full loop locally.
3. If the browser UI fails, open the charts directly from the `results/` folder: `profit_by_agent.png`, `profit_over_time.png`, `reflection.png`, `action_distribution.png`, `cost_latency.png`.
4. If the server will not start because port 8000 is busy, run it on another port:

```bash
python -m kagri.serve --port 8050
```

5. Last resort: show `results/summary.csv` and walk through the screenshots in `docs/img/`.

## Likely live questions during the demo

- "Is this a real LLM?" The recorded runs use the offline reasoner. The same code path runs Gemini, Groq, OpenAI or Claude when a key is in `.env`, and `python -m kagri.record --agent llm_single --provider gemini` records such a run.
- "Why one decision per day?" 720 LLM decisions per game is too slow and too expensive. The Foreman executes the plan.
- "Are these the official rules?" Yes. The engine is vendored from Kaggle's environment package. Weather is our optional extension.
